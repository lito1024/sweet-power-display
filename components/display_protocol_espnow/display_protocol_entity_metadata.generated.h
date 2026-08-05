// AUTO-GENERATED - DO NOT EDIT MANUALLY
#pragma once

#include <stdint.h>

namespace esphome {
namespace display_protocol_espnow {

struct DisplayProtocolEntityMetadata {
  uint16_t field_id;
  const char *key;
  const char *name;
  const char *unit;
  uint8_t accuracy_decimals;
};

static constexpr DisplayProtocolEntityMetadata kDisplayProtocolEntityMetadata[] = {
  {1001, "pv1_power", "PV1 Power", "W", 0},
  {1002, "pv2_power", "PV2 Power", "W", 0},
  {2001, "battery_soc", "Battery SOC", "%", 1},
  {2002, "battery_charge_power", "Battery Charge Power", "W", 0},
  {2003, "battery_discharge_power", "Battery Discharge Power", "W", 0},
  {5001, "pv1_energy_total", "PV1 Energy Total", "kWh", 3},
  {7001, "feed_in_grid_enabled", "Feed-In Grid Enabled", "", 0},
};

}  // namespace display_protocol_espnow
}  // namespace esphome
