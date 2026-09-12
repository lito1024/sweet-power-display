#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/text_sensor/text_sensor.h"
#include "esphome/components/uart/uart.h"
#include "esphome/core/component.h"

#include "ESPTelemetry.h"
#include "TelemetryPeerManager.h"
#include "display_protocol_entity_metadata.generated.h"

namespace esphome {
namespace display_protocol_uart {

class DisplayProtocolUARTComponent : public Component, public uart::UARTDevice {
 public:
  // Stage 32: exactly two LuxPower inverter telemetry sources (device_id 1 =
  // inverter 1, device_id 2 = inverter 2), indexed 0/1 in every per-inverter
  // array below. Stage 39B adds Controller/system measurements at device_id 3,
  // kept separate so they never masquerade as "LXP3".
  static constexpr uint8_t kDeviceCount = 2;

  void setup() override;
  void loop() override;
  void dump_config() override;

  void set_stale_timeout(uint32_t timeout_ms) { this->stale_timeout_ms_ = timeout_ms; }
  void set_trace_frames(bool trace_frames) { this->trace_frames_ = trace_frames; }
  void set_rx_gpio(uint8_t gpio) { this->rx_gpio_ = gpio; }
  void set_tx_gpio(uint8_t gpio) { this->tx_gpio_ = gpio; }

  void set_pv1_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv1_power_sensor_[device_index] = sensor; }
  void set_pv2_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv2_power_sensor_[device_index] = sensor; }
  void set_battery_soc_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->battery_soc_sensor_[device_index] = sensor; }
  void set_battery_charge_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->battery_charge_power_sensor_[device_index] = sensor; }
  void set_battery_discharge_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->battery_discharge_power_sensor_[device_index] = sensor; }
  void set_pv1_energy_total_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv1_energy_total_sensor_[device_index] = sensor; }
  void set_gateway_snapshot_age_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->gateway_snapshot_age_sensor_[device_index] = sensor; }
  void set_gateway_sequence_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->gateway_sequence_sensor_[device_index] = sensor; }
  void set_uart_valid_frames_sensor(sensor::Sensor *sensor) { this->uart_valid_frames_sensor_ = sensor; }
  void set_uart_crc_errors_sensor(sensor::Sensor *sensor) { this->uart_crc_errors_sensor_ = sensor; }
  void set_uart_decode_errors_sensor(sensor::Sensor *sensor) { this->uart_decode_errors_sensor_ = sensor; }
  void set_uart_sequence_gaps_sensor(sensor::Sensor *sensor) { this->uart_sequence_gaps_sensor_ = sensor; }
  void set_uart_duplicate_frames_sensor(sensor::Sensor *sensor) { this->uart_duplicate_frames_sensor_ = sensor; }

  void set_battery_capacity_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->battery_capacity_sensor_[device_index] = sensor; }
  void set_bms_max_cell_temperature_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_max_cell_temperature_sensor_[device_index] = sensor; }
  void set_power_to_grid_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->power_to_grid_sensor_[device_index] = sensor; }
  void set_power_from_grid_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->power_from_grid_sensor_[device_index] = sensor; }
  void set_grid_flow_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->grid_flow_sensor_[device_index] = sensor; }

  // Stage 30: 79 additional production entities, sourced from the
  // upstream luxpower-ha-integration register map (see
  // FULL_ENTITY_COVERAGE.md), all inside the Gateway's already-polled
  // input 0..124 block. Same raw-passthrough wire convention as the five
  // entities above.
  void set_pv1_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv1_voltage_sensor_[device_index] = sensor; }
  void set_pv2_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv2_voltage_sensor_[device_index] = sensor; }
  void set_pv3_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv3_voltage_sensor_[device_index] = sensor; }
  void set_pv3_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv3_power_sensor_[device_index] = sensor; }
  void set_pv1_energy_today_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv1_energy_today_sensor_[device_index] = sensor; }
  void set_pv2_energy_today_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv2_energy_today_sensor_[device_index] = sensor; }
  void set_pv3_energy_today_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv3_energy_today_sensor_[device_index] = sensor; }
  void set_pv2_energy_total_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv2_energy_total_sensor_[device_index] = sensor; }
  void set_pv3_energy_total_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv3_energy_total_sensor_[device_index] = sensor; }
  void set_battery_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->battery_voltage_sensor_[device_index] = sensor; }
  void set_battery_soh_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->battery_soh_sensor_[device_index] = sensor; }
  void set_battery_temperature_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->battery_temperature_sensor_[device_index] = sensor; }
  void set_battery_parallel_number_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->battery_parallel_number_sensor_[device_index] = sensor; }
  void set_battery_type_and_brand_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->battery_type_and_brand_sensor_[device_index] = sensor; }
  void set_bms_max_charge_current_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_max_charge_current_sensor_[device_index] = sensor; }
  void set_bms_max_discharge_current_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_max_discharge_current_sensor_[device_index] = sensor; }
  void set_bms_charge_voltage_reference_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_charge_voltage_reference_sensor_[device_index] = sensor; }
  void set_bms_discharge_cutoff_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_discharge_cutoff_voltage_sensor_[device_index] = sensor; }
  void set_bms_battery_current_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_battery_current_sensor_[device_index] = sensor; }
  void set_bms_fault_code_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_fault_code_sensor_[device_index] = sensor; }
  void set_bms_warning_code_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_warning_code_sensor_[device_index] = sensor; }
  void set_bms_max_cell_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_max_cell_voltage_sensor_[device_index] = sensor; }
  void set_bms_min_cell_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_min_cell_voltage_sensor_[device_index] = sensor; }
  void set_bms_min_cell_temperature_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_min_cell_temperature_sensor_[device_index] = sensor; }
  void set_bms_firmware_update_state_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_firmware_update_state_sensor_[device_index] = sensor; }
  void set_bms_cycle_count_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_cycle_count_sensor_[device_index] = sensor; }
  void set_inverter_battery_voltage_sample_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->inverter_battery_voltage_sample_sensor_[device_index] = sensor; }
  void set_charge_energy_today_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->charge_energy_today_sensor_[device_index] = sensor; }
  void set_discharge_energy_today_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->discharge_energy_today_sensor_[device_index] = sensor; }
  void set_charge_energy_total_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->charge_energy_total_sensor_[device_index] = sensor; }
  void set_discharge_energy_total_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->discharge_energy_total_sensor_[device_index] = sensor; }
  void set_grid_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->grid_voltage_sensor_[device_index] = sensor; }
  void set_grid_voltage_s_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->grid_voltage_s_sensor_[device_index] = sensor; }
  void set_grid_voltage_t_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->grid_voltage_t_sensor_[device_index] = sensor; }
  void set_grid_frequency_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->grid_frequency_sensor_[device_index] = sensor; }
  void set_inverter_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->inverter_power_sensor_[device_index] = sensor; }
  void set_ac_charging_rectification_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->ac_charging_rectification_power_sensor_[device_index] = sensor; }
  void set_inverter_current_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->inverter_current_sensor_[device_index] = sensor; }
  void set_power_factor_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->power_factor_sensor_[device_index] = sensor; }
  void set_energy_to_grid_today_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->energy_to_grid_today_sensor_[device_index] = sensor; }
  void set_energy_from_grid_today_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->energy_from_grid_today_sensor_[device_index] = sensor; }
  void set_energy_to_grid_total_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->energy_to_grid_total_sensor_[device_index] = sensor; }
  void set_energy_from_grid_total_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->energy_from_grid_total_sensor_[device_index] = sensor; }
  void set_ongrid_load_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->ongrid_load_power_sensor_[device_index] = sensor; }
  void set_bus1_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bus1_voltage_sensor_[device_index] = sensor; }
  void set_bus2_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bus2_voltage_sensor_[device_index] = sensor; }
  void set_half_bus_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->half_bus_voltage_sensor_[device_index] = sensor; }
  void set_eps_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->eps_voltage_sensor_[device_index] = sensor; }
  void set_eps_voltage_s_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->eps_voltage_s_sensor_[device_index] = sensor; }
  void set_eps_voltage_t_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->eps_voltage_t_sensor_[device_index] = sensor; }
  void set_eps_frequency_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->eps_frequency_sensor_[device_index] = sensor; }
  void set_eps_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->eps_power_sensor_[device_index] = sensor; }
  void set_eps_apparent_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->eps_apparent_power_sensor_[device_index] = sensor; }
  void set_eps_energy_today_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->eps_energy_today_sensor_[device_index] = sensor; }
  void set_eps_energy_total_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->eps_energy_total_sensor_[device_index] = sensor; }
  void set_internal_temperature_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->internal_temperature_sensor_[device_index] = sensor; }
  void set_radiator_temperature_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->radiator_temperature_sensor_[device_index] = sensor; }
  void set_radiator_temperature_2_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->radiator_temperature_2_sensor_[device_index] = sensor; }
  void set_inverter_state_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->inverter_state_sensor_[device_index] = sensor; }
  void set_internal_fault_code_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->internal_fault_code_sensor_[device_index] = sensor; }
  void set_ac_input_type_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->ac_input_type_sensor_[device_index] = sensor; }
  void set_auto_test_status_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->auto_test_status_sensor_[device_index] = sensor; }
  void set_inverter_energy_today_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->inverter_energy_today_sensor_[device_index] = sensor; }
  void set_ac_charge_energy_today_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->ac_charge_energy_today_sensor_[device_index] = sensor; }
  void set_inverter_energy_total_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->inverter_energy_total_sensor_[device_index] = sensor; }
  void set_ac_charge_energy_total_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->ac_charge_energy_total_sensor_[device_index] = sensor; }
  void set_total_running_time_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->total_running_time_sensor_[device_index] = sensor; }
  void set_generator_voltage_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->generator_voltage_sensor_[device_index] = sensor; }
  void set_generator_frequency_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->generator_frequency_sensor_[device_index] = sensor; }
  void set_generator_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->generator_power_sensor_[device_index] = sensor; }
  void set_generator_energy_today_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->generator_energy_today_sensor_[device_index] = sensor; }
  void set_pv1_current_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv1_current_sensor_[device_index] = sensor; }
  void set_pv2_current_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv2_current_sensor_[device_index] = sensor; }
  void set_pv3_current_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->pv3_current_sensor_[device_index] = sensor; }
  void set_battery_flow_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->battery_flow_sensor_[device_index] = sensor; }
  void set_bms_cell_difference_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->bms_cell_difference_sensor_[device_index] = sensor; }
  void set_grid_connected_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->grid_connected_sensor_[device_index] = sensor; }
  void set_active_fault_code_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->active_fault_code_sensor_[device_index] = sensor; }
  void set_active_warning_code_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->active_warning_code_sensor_[device_index] = sensor; }
  // Stage 31: load_power (FieldId 9085), FAST class, via the new input block 2.
  void set_load_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->load_power_sensor_[device_index] = sensor; }

  void set_gateway_data_fresh_sensor(uint8_t device_index, binary_sensor::BinarySensor *sensor) { this->gateway_data_fresh_sensor_[device_index] = sensor; }
  void set_gateway_link_connected_sensor(uint8_t device_index, binary_sensor::BinarySensor *sensor) { this->gateway_link_connected_sensor_[device_index] = sensor; }
  void set_luxpower_tcp_connected_sensor(uint8_t device_index, binary_sensor::BinarySensor *sensor) { this->luxpower_tcp_connected_sensor_[device_index] = sensor; }
  void set_input_cache_valid_sensor(uint8_t device_index, binary_sensor::BinarySensor *sensor) { this->input_cache_valid_sensor_[device_index] = sensor; }
  void set_holding_cache_valid_sensor(uint8_t device_index, binary_sensor::BinarySensor *sensor) { this->holding_cache_valid_sensor_[device_index] = sensor; }
  void set_snapshot_values_valid_sensor(uint8_t device_index, binary_sensor::BinarySensor *sensor) { this->snapshot_values_valid_sensor_[device_index] = sensor; }
  void set_feed_in_grid_enabled_sensor(uint8_t device_index, binary_sensor::BinarySensor *sensor) { this->feed_in_grid_enabled_sensor_[device_index] = sensor; }
  // Stage 35: read-only, per stages/Stage35.md -- no write path exists here
  // or anywhere else in the Display.
  void set_zero_export_enabled_sensor(uint8_t device_index, binary_sensor::BinarySensor *sensor) { this->zero_export_enabled_sensor_[device_index] = sensor; }
  void set_max_backflow_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->max_backflow_power_sensor_[device_index] = sensor; }

  // Stage 33: derived entirely from the existing have_snapshot_/data_fresh_
  // state (no new timeout mechanism) -- see update_connection_status_.
  void set_connection_status_text_sensor(uint8_t device_index, text_sensor::TextSensor *sensor) { this->connection_status_text_sensor_[device_index] = sensor; }

  // Stage 37: presentation-layer derived values (Solar = PV1+PV2, Power =
  // Load+EPS, Grid = ToGrid-FromGrid, Battery = Charge-Discharge), computed
  // here from the existing per-device (device_id, FieldId) state -- see
  // recompute_derived_. Not a second telemetry pipeline: these sensors are
  // republished from the SAME raw values already decoded above, purely to
  // give LVGL a single up-to-date number instead of duplicating the
  // arithmetic in every YAML lambda. Unavailable/not-fresh inputs publish
  // NAN (never 0) so the display can render "--" instead of a misleading
  // value -- see update_stale_state_.
  void set_solar_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->solar_sensor_[device_index] = sensor; }
  void set_derived_power_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->derived_power_sensor_[device_index] = sensor; }
  void set_grid_net_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->grid_net_sensor_[device_index] = sensor; }
  void set_battery_net_sensor(uint8_t device_index, sensor::Sensor *sensor) { this->battery_net_sensor_[device_index] = sensor; }
  // TOTAL columns: sum of both inverters' derived value above, or NAN if
  // either inverter's own value is NAN/unavailable (never treat a missing
  // inverter as zero -- see combine_total_).
  void set_solar_total_sensor(sensor::Sensor *sensor) { this->solar_total_sensor_ = sensor; }
  void set_power_total_sensor(sensor::Sensor *sensor) { this->power_total_sensor_ = sensor; }
  void set_grid_total_sensor(sensor::Sensor *sensor) { this->grid_total_sensor_ = sensor; }
  void set_battery_total_sensor(sensor::Sensor *sensor) { this->battery_total_sensor_ = sensor; }

  void set_system_output_voltage_sensor(sensor::Sensor *sensor) { this->system_output_voltage_sensor_ = sensor; }
  void set_system_output_current_sensor(sensor::Sensor *sensor) { this->system_output_current_sensor_ = sensor; }
  void set_system_output_power_sensor(sensor::Sensor *sensor) { this->system_output_power_sensor_ = sensor; }
  void set_system_output_energy_sensor(sensor::Sensor *sensor) { this->system_output_energy_sensor_ = sensor; }
  void set_system_output_frequency_sensor(sensor::Sensor *sensor) { this->system_output_frequency_sensor_ = sensor; }
  void set_system_output_power_factor_sensor(sensor::Sensor *sensor) { this->system_output_power_factor_sensor_ = sensor; }
  void set_grid_input_voltage_sensor(sensor::Sensor *sensor) { this->grid_input_voltage_sensor_ = sensor; }
  void set_grid_input_current_sensor(sensor::Sensor *sensor) { this->grid_input_current_sensor_ = sensor; }
  void set_grid_input_power_sensor(sensor::Sensor *sensor) { this->grid_input_power_sensor_ = sensor; }
  void set_grid_input_energy_sensor(sensor::Sensor *sensor) { this->grid_input_energy_sensor_ = sensor; }
  void set_grid_input_frequency_sensor(sensor::Sensor *sensor) { this->grid_input_frequency_sensor_ = sensor; }
  void set_grid_input_power_factor_sensor(sensor::Sensor *sensor) { this->grid_input_power_factor_sensor_ = sensor; }
  void set_grid_raw_voltage_sensor(sensor::Sensor *sensor) { this->grid_raw_voltage_sensor_ = sensor; }
  void set_display_enabled_sensor(binary_sensor::BinarySensor *sensor) { this->display_enabled_sensor_ = sensor; }
  void set_display_maintenance_wifi_requested_sensor(binary_sensor::BinarySensor *sensor) { this->display_maintenance_wifi_requested_sensor_ = sensor; }
  // Exposes the existing internal system_link_fresh_ state (Controller System
  // device_id frames arriving over this UART link within stale_timeout_ms_) --
  // previously tracked but never published. Used for the top-right "SPC"
  // status icon.
  void set_system_link_connected_sensor(binary_sensor::BinarySensor *sensor) { this->system_link_connected_sensor_ = sensor; }
  // Stage 44H: effective Home Assistant status for the Display's "HA" icon --
  // see ha_reported_connected_/update_ha_connected_display_() for why this is
  // not simply the raw Controller-reported value.
  void set_ha_connected_sensor(binary_sensor::BinarySensor *sensor) { this->ha_connected_sensor_ = sensor; }
  void set_display_maintenance_wifi_actual(bool enabled);
  bool display_maintenance_wifi_actual() const { return this->display_maintenance_wifi_actual_; }

  bool send_raw_frame(const uint8_t *data, size_t length);

 protected:
  // Returns 0/1 for device_id 1/2, or -1 for any other device_id (unknown
  // sender or the reserved aggregate id 0 -- not published in Stage 32).
  static int8_t device_index_for_id_(uint8_t device_id);

  void handle_decode_result_(ESPTelemetry::DecodeResult result, const ESPTelemetry::Frame &frame, uint32_t now);
  void handle_snapshot_frame_(const ESPTelemetry::Frame &frame, uint32_t now);
  void handle_telemetry_frame_(const ESPTelemetry::Frame &frame, uint32_t now);
  void handle_system_telemetry_frame_(const ESPTelemetry::TelemetryPayload &payload, const ESPTelemetry::Frame &frame,
                                      uint32_t now);
  void publish_snapshot_(uint8_t device_index, uint32_t now);
  void publish_telemetry_field_(uint8_t device_index, uint16_t field_id, int32_t value, uint32_t now);
  void publish_system_telemetry_field_(uint16_t field_id, int32_t value);
  void publish_diagnostics_(uint32_t now);
  void send_display_status_(uint32_t now);
  void update_stale_state_(uint32_t now);
  // Stage 38 source-freshness still comes from the Gateway's own per-frame
  // cache-valid flags and is published as diagnostics. The offline HMI keeps
  // last valid readings during short source/cache gaps and blanks values only
  // when no packets arrive for stale_timeout_ms_ (the visible Off state).
  void set_device_freshness_(uint8_t device_index, bool fresh);
  void mark_device_stale_(uint8_t device_index);
  void mark_system_stale_();
  void publish_binary_(binary_sensor::BinarySensor *sensor, bool value);
  void publish_float_(sensor::Sensor *sensor, float value);
  void publish_text_(text_sensor::TextSensor *sensor, const char *value);
  // Stage 33: CONNECTED/STALE/DISCONNECTED, purely derived from
  // have_snapshot_[device_index]/data_fresh_[device_index] -- the same
  // freshness state update_stale_state_ and the frame handlers already
  // maintain. Called from those existing update points, not a new timer.
  void update_connection_status_(uint8_t device_index);
  void trace_frame_(const ESPTelemetry::Frame &frame);
  // Stage 37/39B: recomputes this device's Solar/Power/Grid/Battery from the
  // current state of the raw sensor objects. Short source/cache gaps keep the
  // last valid readings; transport Off blanks them to NAN.
  void recompute_derived_(uint8_t device_index);
  void recompute_totals_();
  static float combine_total_(sensor::Sensor *a, sensor::Sensor *b);
  static float scaled_or_nan_(int32_t value, float scale);

  ESPTelemetry::Decoder decoder_;
  // Stage 32: every per-source field below is indexed [0]=inverter1(device_id
  // 1), [1]=inverter2(device_id 2) -- independent values, freshness, and
  // link state per device, so one Gateway can never overwrite or mask the
  // other's entities (see stages/Stage32.md).
  ESPTelemetry::SnapshotPayload latest_[kDeviceCount]{};
  bool have_snapshot_[kDeviceCount] = {false, false};
  bool data_fresh_[kDeviceCount] = {false, false};
  bool link_connected_[kDeviceCount] = {false, false};
  bool values_marked_stale_[kDeviceCount] = {false, false};
  bool have_last_sequence_[kDeviceCount] = {false, false};
  uint16_t last_sequence_[kDeviceCount] = {0, 0};
  uint32_t last_frame_ms_[kDeviceCount] = {0, 0};
  bool have_system_frame_ = false;
  bool system_link_fresh_ = false;
  uint32_t last_system_frame_ms_ = 0;
  // Stage 44H: dedicated, independent freshness watchdog for the Display's
  // "SPC" status icon only -- deliberately NOT the same as system_link_fresh_
  // above (which stays governed by the existing stale_timeout_ms_/60s config
  // and continues to gate mark_system_stale_()'s NaN-blanking of
  // system_output_*/grid_input_* sensors, unchanged). The physical test
  // showed the icon needed to react in ~3s, but that timeout must not be
  // reused for -- or forced onto -- the existing, possibly-elsewhere-relied
  // on stale semantics. Reuses the same last_system_frame_ms_ timestamp
  // (both watchdogs measure "time since last Controller/System frame", just
  // with different thresholds/actions) rather than tracking a second,
  // redundant timestamp.
  bool spc_link_fresh_ = false;
  static constexpr uint32_t kSpcLinkTimeoutMs = 3000;
  // Raw value last reported by the Controller in FieldIdHomeAssistantConnected,
  // independent of whether the link itself is currently fresh. The actually
  // *displayed* HA state is the AND of this with spc_link_fresh_ (see
  // update_ha_connected_display_()) so a stale Controller link can never
  // continue showing a stale "HA connected" indication.
  bool ha_reported_connected_ = false;
  uint32_t last_publish_ms_ = 0;
  uint32_t last_display_status_tx_ms_ = 0;
  uint16_t next_display_status_sequence_ = 0;
  bool display_maintenance_wifi_actual_ = false;
  bool last_display_maintenance_wifi_request_ = true;
  uint32_t stale_timeout_ms_ = 5000;
  bool trace_frames_ = false;
  uint8_t rx_gpio_ = 44;
  uint8_t tx_gpio_ = 43;

  // Whole-UART-link transport diagnostics (Stage 32: kept global, not
  // per-device -- CRC errors and malformed frames occur before a device_id
  // can even be parsed, and both Gateways share this one physical wire via
  // the Bridge, so these counters describe the link itself, not a source).

  uint32_t valid_frames_ = 0;
  uint32_t crc_errors_ = 0;
  uint32_t decode_errors_ = 0;
  uint32_t sequence_gaps_ = 0;
  uint32_t duplicate_frames_ = 0;
  uint32_t display_status_frames_sent_ = 0;
  uint32_t display_status_send_failures_ = 0;

  sensor::Sensor *pv1_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv2_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *battery_soc_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *battery_charge_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *battery_discharge_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv1_energy_total_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *gateway_snapshot_age_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *gateway_sequence_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *uart_valid_frames_sensor_ = nullptr;
  sensor::Sensor *uart_crc_errors_sensor_ = nullptr;
  sensor::Sensor *uart_decode_errors_sensor_ = nullptr;
  sensor::Sensor *uart_sequence_gaps_sensor_ = nullptr;
  sensor::Sensor *uart_duplicate_frames_sensor_ = nullptr;

  sensor::Sensor *battery_capacity_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_max_cell_temperature_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *power_to_grid_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *power_from_grid_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *grid_flow_sensor_[kDeviceCount] = {nullptr, nullptr};

  sensor::Sensor *pv1_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv2_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv3_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv3_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv1_energy_today_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv2_energy_today_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv3_energy_today_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv2_energy_total_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv3_energy_total_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *battery_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *battery_soh_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *battery_temperature_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *battery_parallel_number_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *battery_type_and_brand_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_max_charge_current_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_max_discharge_current_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_charge_voltage_reference_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_discharge_cutoff_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_battery_current_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_fault_code_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_warning_code_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_max_cell_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_min_cell_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_min_cell_temperature_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_firmware_update_state_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_cycle_count_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *inverter_battery_voltage_sample_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *charge_energy_today_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *discharge_energy_today_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *charge_energy_total_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *discharge_energy_total_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *grid_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *grid_voltage_s_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *grid_voltage_t_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *grid_frequency_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *inverter_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *ac_charging_rectification_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *inverter_current_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *power_factor_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *energy_to_grid_today_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *energy_from_grid_today_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *energy_to_grid_total_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *energy_from_grid_total_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *ongrid_load_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bus1_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bus2_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *half_bus_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *eps_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *eps_voltage_s_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *eps_voltage_t_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *eps_frequency_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *eps_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *eps_apparent_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *eps_energy_today_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *eps_energy_total_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *internal_temperature_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *radiator_temperature_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *radiator_temperature_2_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *inverter_state_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *internal_fault_code_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *ac_input_type_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *auto_test_status_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *inverter_energy_today_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *ac_charge_energy_today_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *inverter_energy_total_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *ac_charge_energy_total_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *total_running_time_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *generator_voltage_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *generator_frequency_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *generator_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *generator_energy_today_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv1_current_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv2_current_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *pv3_current_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *battery_flow_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *bms_cell_difference_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *grid_connected_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *active_fault_code_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *active_warning_code_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *load_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *max_backflow_power_sensor_[kDeviceCount] = {nullptr, nullptr};

  binary_sensor::BinarySensor *gateway_data_fresh_sensor_[kDeviceCount] = {nullptr, nullptr};
  binary_sensor::BinarySensor *gateway_link_connected_sensor_[kDeviceCount] = {nullptr, nullptr};
  binary_sensor::BinarySensor *luxpower_tcp_connected_sensor_[kDeviceCount] = {nullptr, nullptr};
  binary_sensor::BinarySensor *input_cache_valid_sensor_[kDeviceCount] = {nullptr, nullptr};
  binary_sensor::BinarySensor *holding_cache_valid_sensor_[kDeviceCount] = {nullptr, nullptr};
  binary_sensor::BinarySensor *snapshot_values_valid_sensor_[kDeviceCount] = {nullptr, nullptr};
  binary_sensor::BinarySensor *feed_in_grid_enabled_sensor_[kDeviceCount] = {nullptr, nullptr};
  binary_sensor::BinarySensor *zero_export_enabled_sensor_[kDeviceCount] = {nullptr, nullptr};

  text_sensor::TextSensor *connection_status_text_sensor_[kDeviceCount] = {nullptr, nullptr};

  // Stage 37: see set_solar_sensor et al. above.
  sensor::Sensor *solar_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *derived_power_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *grid_net_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *battery_net_sensor_[kDeviceCount] = {nullptr, nullptr};
  sensor::Sensor *solar_total_sensor_ = nullptr;
  sensor::Sensor *power_total_sensor_ = nullptr;
  sensor::Sensor *grid_total_sensor_ = nullptr;
  sensor::Sensor *battery_total_sensor_ = nullptr;

  sensor::Sensor *system_output_voltage_sensor_ = nullptr;
  sensor::Sensor *system_output_current_sensor_ = nullptr;
  sensor::Sensor *system_output_power_sensor_ = nullptr;
  sensor::Sensor *system_output_energy_sensor_ = nullptr;
  sensor::Sensor *system_output_frequency_sensor_ = nullptr;
  sensor::Sensor *system_output_power_factor_sensor_ = nullptr;
  sensor::Sensor *grid_input_voltage_sensor_ = nullptr;
  sensor::Sensor *grid_input_current_sensor_ = nullptr;
  sensor::Sensor *grid_input_power_sensor_ = nullptr;
  sensor::Sensor *grid_input_energy_sensor_ = nullptr;
  sensor::Sensor *grid_input_frequency_sensor_ = nullptr;
  sensor::Sensor *grid_input_power_factor_sensor_ = nullptr;
  sensor::Sensor *grid_raw_voltage_sensor_ = nullptr;
  binary_sensor::BinarySensor *display_enabled_sensor_ = nullptr;
  binary_sensor::BinarySensor *display_maintenance_wifi_requested_sensor_ = nullptr;
  binary_sensor::BinarySensor *system_link_connected_sensor_ = nullptr;
  binary_sensor::BinarySensor *ha_connected_sensor_ = nullptr;
  // Stage 44H: recomputes and (if changed) publishes the effective HA state
  // (spc_link_fresh_ AND ha_reported_connected_). Called whenever either
  // input can change: a new Home Assistant field value arrives, or the SPC
  // link itself becomes fresh/stale.
  void update_ha_connected_display_();
};

}  // namespace display_protocol_uart
}  // namespace esphome
