// Display 3A (owner-approved 2026-10-25): screen layout helpers.
//
// Layout (800x480): title + status icons; 4 KPI tiles (Solar, Battery,
// Load, Grid with the export limit in the tile's top-right corner and an
// export-use bar); per-inverter table (LXP1 / LXP2 rows with their
// On / Stale / Offline status); source strip (Stabilizer, Zegor, KS with
// run time and oil-change counters).
//
// Every value comes from a display_protocol_uart sensor (NAN = invalid or
// stale -> "--"). The thresholds below are the owner thresholds already
// used by the Stage 56b screen; only the presentation changed.
#pragma once

#include <cmath>
#include <cstdio>
#include <cstring>

#include "esphome/components/lvgl/lvgl_esphome.h"

namespace display_hmi {

// ---- colours ----
static constexpr uint32_t WHITE = 0xFFFFFF;
static constexpr uint32_t GREEN = 0x00E676;
static constexpr uint32_t YELLOW = 0xFFD600;
static constexpr uint32_t RED = 0xFF3B30;
static constexpr uint32_t BLUE = 0x4FA3FF;
static constexpr uint32_t GREY = 0x7B8796;
static constexpr uint32_t AMBER = 0xFFB020;

// HMI-only "output present" level for the stabilizer tile. Absent-AC noise
// stays below 65 V on V1-V4 (10-hour observation, Stage 48L); mains is
// >= 180 V. This is a display rule, NOT the Stage 48L validity threshold.
static constexpr float STABILIZER_PRESENT_V = 150.0f;

// Export limit register is a percentage of 12 kW (both inverters in parallel).
static constexpr float EXPORT_LIMIT_W_PER_PERCENT = 120.0f;

inline void set_text(lv_obj_t *obj, const char *text) {
  const char *current = lv_label_get_text(obj);
  if (current == nullptr || strcmp(current, text) != 0) {
    lv_label_set_text(obj, text);
  }
}

inline void set_color(lv_obj_t *obj, uint32_t color) {
  lv_obj_set_style_text_color(obj, lv_color_hex(color), 0);
}

inline void set_bar(lv_obj_t *bar, float percent, uint32_t color) {
  int32_t v = std::isnan(percent) ? 0 : static_cast<int32_t>(lroundf(percent));
  v = v < 0 ? 0 : (v > 100 ? 100 : v);
  lv_bar_set_value(bar, v, LV_ANIM_OFF);
  lv_obj_set_style_bg_color(bar, lv_color_hex(color), LV_PART_INDICATOR);
}

// "3.42 kW" / "-4.82 kW" / "--".
inline void fmt_kw(char *buf, size_t len, float watts) {
  if (std::isnan(watts)) {
    snprintf(buf, len, "--");
  } else {
    snprintf(buf, len, "%.2f kW", watts / 1000.0f);
  }
}

// ---- owner thresholds (unchanged from Stage 56b) ----
// System output (load) power: < 3 kW white, 3-4.5 kW yellow, > 4.5 kW red,
// > 5 kW red and blinking.
inline uint32_t load_color(float w) {
  if (std::isnan(w) || w < 3000.0f) return WHITE;
  if (w <= 4500.0f) return YELLOW;
  return RED;
}
inline bool load_blink(float w) { return !std::isnan(w) && w > 5000.0f; }

// Eastron grid power: import (> 0) yellow, export (< 0) green, 0 white.
inline uint32_t grid_power_color(float w) {
  if (std::isnan(w) || w == 0.0f) return WHITE;
  return w > 0.0f ? YELLOW : GREEN;
}

// Grid voltage: 190-230 green, 160-190 / 230-250 yellow, otherwise red.
inline uint32_t grid_voltage_color(float v) {
  if (std::isnan(v)) return WHITE;
  if (v >= 190.0f && v <= 230.0f) return GREEN;
  if ((v >= 160.0f && v < 190.0f) || (v > 230.0f && v <= 250.0f)) return YELLOW;
  return RED;
}

// Grid current: < 20 A green, 20-25 A yellow, >= 25 A red.
inline uint32_t grid_current_color(float a) {
  if (std::isnan(a)) return WHITE;
  if (a < 20.0f) return GREEN;
  if (a < 25.0f) return YELLOW;
  return RED;
}

// Export limit: "50% | 6kW" (one decimal when not a whole kW).
inline void fmt_export_limit(char *buf, size_t len, float percent) {
  if (std::isnan(percent)) {
    snprintf(buf, len, "LIMIT --");
    return;
  }
  const float kw = percent * EXPORT_LIMIT_W_PER_PERCENT / 1000.0f;
  if (fabsf(kw - roundf(kw)) < 0.05f) {
    snprintf(buf, len, "LIMIT %.0f%% | %.0fkW", percent, kw);
  } else {
    snprintf(buf, len, "LIMIT %.0f%% | %.1fkW", percent, kw);
  }
}

// Share of the export limit currently used (0-100 %, NAN if unknown).
inline float export_use_percent(float grid_w, float limit_percent) {
  if (std::isnan(grid_w) || std::isnan(limit_percent) || limit_percent <= 0.0f) return NAN;
  const float export_w = grid_w < 0.0f ? -grid_w : 0.0f;
  return 100.0f * export_w / (limit_percent * EXPORT_LIMIT_W_PER_PERCENT);
}

// Oil counter colour: green < 80 %, amber >= 80 %, red >= 95 %.
inline uint32_t oil_color(float hours, float interval) {
  if (std::isnan(hours) || std::isnan(interval) || interval <= 0.0f) return GREY;
  const float used = hours / interval;
  if (used >= 0.95f) return RED;
  if (used >= 0.80f) return AMBER;
  return GREEN;
}

// ---- tiles ----

inline void refresh_solar(lv_obj_t *value, lv_obj_t *sub, float total_w, float pv1_a, float pv1_b, float pv2_a,
                          float pv2_b) {
  char buf[48];
  fmt_kw(buf, sizeof(buf), total_w);
  set_text(value, buf);
  const float pv1 = pv1_a + pv1_b;  // NAN if either inverter is unavailable
  const float pv2 = pv2_a + pv2_b;
  if (std::isnan(pv1) || std::isnan(pv2)) {
    snprintf(buf, sizeof(buf), "PV1 --  PV2 --");
  } else {
    snprintf(buf, sizeof(buf), "PV1 %.2f  PV2 %.2f", pv1 / 1000.0f, pv2 / 1000.0f);
  }
  set_text(sub, buf);
}

inline void refresh_battery(lv_obj_t *value, lv_obj_t *sub, lv_obj_t *bar, float soc1, float soc2, float net_w) {
  char buf[48];
  float soc = NAN;
  if (!std::isnan(soc1) && !std::isnan(soc2)) {
    soc = (soc1 + soc2) / 2.0f;
  } else if (!std::isnan(soc1)) {
    soc = soc1;
  } else if (!std::isnan(soc2)) {
    soc = soc2;
  }
  if (std::isnan(soc)) {
    snprintf(buf, sizeof(buf), "--");
  } else {
    snprintf(buf, sizeof(buf), "%.0f%%", soc);
  }
  set_text(value, buf);
  set_bar(bar, soc, BLUE);
  uint32_t color = GREY;
  if (std::isnan(net_w)) {
    snprintf(buf, sizeof(buf), "--");
  } else if (net_w > 0.0f) {
    snprintf(buf, sizeof(buf), "+%.2f kW in", net_w / 1000.0f);
    color = GREEN;
  } else if (net_w < 0.0f) {
    snprintf(buf, sizeof(buf), "%.2f kW out", net_w / 1000.0f);
    color = RED;
  } else {
    snprintf(buf, sizeof(buf), "0.00 kW");
  }
  set_text(sub, buf);
  set_color(sub, color);
}

// Returns true when the load value must blink (> 5 kW).
inline bool refresh_load(lv_obj_t *value, lv_obj_t *sub, float load_w, float voltage) {
  char buf[48];
  fmt_kw(buf, sizeof(buf), load_w);
  set_text(value, buf);
  if (std::isnan(voltage)) {
    snprintf(buf, sizeof(buf), "output -- V");
  } else {
    snprintf(buf, sizeof(buf), "output %.1f V", voltage);
  }
  set_text(sub, buf);
  return load_blink(load_w);
}

inline void refresh_grid(lv_obj_t *value, lv_obj_t *limit, lv_obj_t *sub, lv_obj_t *bar, float grid_w,
                         float voltage, float current, float limit_percent, int export_state) {
  char buf[96];
  fmt_kw(buf, sizeof(buf), grid_w);
  set_text(value, buf);
  set_color(value, grid_power_color(grid_w));
  fmt_export_limit(buf, sizeof(buf), limit_percent);
  set_text(limit, buf);
  // export_state: -1 unknown, 0 Off, 1 On (zero-export register of LXP1).
  char v[24], a[24];
  if (std::isnan(voltage)) {
    snprintf(v, sizeof(v), "-- V");
  } else {
    snprintf(v, sizeof(v), "#%06X %.0f V#", static_cast<unsigned int>(grid_voltage_color(voltage)), voltage);
  }
  if (std::isnan(current)) {
    snprintf(a, sizeof(a), "-- A");
  } else {
    snprintf(a, sizeof(a), "#%06X %.1f A#", static_cast<unsigned int>(grid_current_color(current)), current);
  }
  const char *exp = export_state < 0 ? "EXP --" : (export_state ? "EXP #00E676 ON#" : "EXP #FF3B30 OFF#");
  snprintf(buf, sizeof(buf), "%s | %s | %s", v, a, exp);
  set_text(sub, buf);
  const float use = export_use_percent(grid_w, limit_percent);
  set_bar(bar, use, !std::isnan(use) && use >= 80.0f ? AMBER : GREEN);
}

inline void refresh_stabilizer(lv_obj_t *value, lv_obj_t *sub, float quant9_v, float elex_v) {
  char buf[64];
  const bool q = !std::isnan(quant9_v) && quant9_v >= STABILIZER_PRESENT_V;
  const bool e = !std::isnan(elex_v) && elex_v >= STABILIZER_PRESENT_V;
  if (std::isnan(quant9_v) && std::isnan(elex_v)) {
    set_text(value, "--");
    set_color(value, GREY);
  } else if (q && e) {
    set_text(value, "QUANT9 + ELEX");
    set_color(value, AMBER);
  } else if (q) {
    set_text(value, "QUANT9");
    set_color(value, GREEN);
  } else if (e) {
    set_text(value, "ELEX");
    set_color(value, AMBER);
  } else {
    set_text(value, "NO OUTPUT");
    set_color(value, RED);
  }
  char qs[16], es[16];
  if (std::isnan(quant9_v)) snprintf(qs, sizeof(qs), "--"); else snprintf(qs, sizeof(qs), "%.0f V", quant9_v);
  if (std::isnan(elex_v)) snprintf(es, sizeof(es), "--"); else snprintf(es, sizeof(es), "%.0f V", elex_v);
  snprintf(buf, sizeof(buf), "Quant9 %s | Elex %s", qs, es);
  set_text(sub, buf);
}

// run_start_ms: 0 while stopped; set when the generator starts.
inline void refresh_generator(lv_obj_t *tile, lv_obj_t *status, lv_obj_t *value, lv_obj_t *oil, lv_obj_t *bar,
                              float power_w, float oil_hours, float oil_interval, uint32_t &run_start_ms,
                              uint32_t now) {
  char buf[64];
  const bool link = !std::isnan(oil_hours) || !std::isnan(oil_interval);
  const bool running = !std::isnan(power_w);
  if (running && run_start_ms == 0) {
    run_start_ms = now == 0 ? 1 : now;
  } else if (!running) {
    run_start_ms = 0;
  }
  if (running) {
    const uint32_t s = (now - run_start_ms) / 1000;
    snprintf(buf, sizeof(buf), "RUNNING %u:%02u", static_cast<unsigned int>(s / 3600),
             static_cast<unsigned int>((s / 60) % 60));
    set_text(status, buf);
    set_color(status, GREEN);
    fmt_kw(buf, sizeof(buf), power_w);
    set_text(value, buf);
    set_color(value, WHITE);
    lv_obj_set_style_border_color(tile, lv_color_hex(GREEN), 0);
  } else {
    set_text(status, link ? "OFF" : "NO DATA");
    set_color(status, GREY);
    set_text(value, "--");
    set_color(value, GREY);
    lv_obj_set_style_border_color(tile, lv_color_hex(0x243041), 0);
  }
  const uint32_t oc = oil_color(oil_hours, oil_interval);
  if (std::isnan(oil_hours) || std::isnan(oil_interval)) {
    snprintf(buf, sizeof(buf), "oil -- / -- h");
  } else if (oil_hours >= oil_interval) {
    snprintf(buf, sizeof(buf), "oil %.1f / %.0f h  #FF3B30 OIL CHANGE#", oil_hours, oil_interval);
  } else {
    snprintf(buf, sizeof(buf), "oil %.1f / %.0f h | %.0f h left", oil_hours, oil_interval,
             oil_interval - oil_hours);
  }
  set_text(oil, buf);
  set_bar(bar, (std::isnan(oil_hours) || std::isnan(oil_interval) || oil_interval <= 0.0f)
                   ? NAN
                   : 100.0f * oil_hours / oil_interval,
          oc);
}

}  // namespace display_hmi
