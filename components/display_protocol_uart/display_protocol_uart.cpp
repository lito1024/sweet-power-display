#include "display_protocol_uart.h"

#include <cmath>

#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace esphome {
namespace display_protocol_uart {

static const char *const TAG = "display_protocol_uart";
static constexpr uint8_t kControllerSystemDeviceId = 3;
static constexpr uint32_t kDisplayStatusIntervalMs = 5000;

void DisplayProtocolUARTComponent::setup() {
  this->check_uart_settings(230400, 1, uart::UART_CONFIG_PARITY_NONE, 8);
  this->set_rx_full_threshold(64);
  this->set_rx_timeout(2);
  ESP_LOGI(TAG, "Display UART receiver started");
  ESP_LOGI(TAG, "RX GPIO: %u", static_cast<unsigned int>(this->rx_gpio_));
  ESP_LOGI(TAG, "TX GPIO: %u", static_cast<unsigned int>(this->tx_gpio_));
  ESP_LOGI(TAG, "Baud: 230400");
  ESP_LOGI(TAG,
           "Protocol versions: v%u snapshot, v%u grouped telemetry",
           static_cast<unsigned int>(ESPTelemetry::kVersion),
           static_cast<unsigned int>(ESPTelemetry::kVersionV2));
}

void DisplayProtocolUARTComponent::loop() {
  const uint32_t now = millis();

  uint8_t byte = 0;
  ESPTelemetry::Frame frame{};
  while (this->available() > 0) {
    if (!this->read_byte(&byte)) {
      break;
    }

    const ESPTelemetry::DecodeResult result = this->decoder_.feed(byte, now, frame);
    this->handle_decode_result_(result, frame, now);
  }

  this->decoder_.resetIfTimedOut(now, 1000);
  this->update_stale_state_(now);
  this->send_display_status_(now);

  if (this->last_publish_ms_ == 0 || now - this->last_publish_ms_ >= 1000) {
    this->last_publish_ms_ = now;
    this->publish_diagnostics_(now);
  }
}

void DisplayProtocolUARTComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "Display Protocol UART Receiver");
  ESP_LOGCONFIG(TAG, "  Stale timeout: %u ms", static_cast<unsigned int>(this->stale_timeout_ms_));
  ESP_LOGCONFIG(TAG, "  Trace frames: %s", YESNO(this->trace_frames_));
}

bool DisplayProtocolUARTComponent::send_raw_frame(const uint8_t *data, size_t length) {
  if (data == nullptr || length == 0) {
    return false;
  }
  this->write_array(data, length);
  return true;
}

int8_t DisplayProtocolUARTComponent::device_index_for_id_(uint8_t device_id) {
  if (device_id == 1) return 0;
  if (device_id == 2) return 1;
  return -1;  // unknown sender or the reserved aggregate id 0 (not published in Stage 32)
}

void DisplayProtocolUARTComponent::handle_decode_result_(ESPTelemetry::DecodeResult result,
                                                         const ESPTelemetry::Frame &frame, uint32_t now) {
  switch (result) {
    case ESPTelemetry::DecodeResult::None:
      return;
    case ESPTelemetry::DecodeResult::FrameReady:
      this->handle_snapshot_frame_(frame, now);
      return;
    case ESPTelemetry::DecodeResult::SequenceGap:
      // The protocol decoder reports this only after a valid CRC. The snapshot remains usable.
      // Stage 32: the decoder itself now tracks sequence state per (version,
      // messageType, deviceId), so this can no longer be a false conflation
      // between two devices -- it is a genuine gap on whichever device sent
      // this frame. This counter stays a whole-link total (see kept-global
      // note on the member declarations).
      this->sequence_gaps_++;
      ESP_LOGW(TAG, "SEQUENCE GAP detected by decoder");
      this->handle_snapshot_frame_(frame, now);
      return;
    case ESPTelemetry::DecodeResult::BadCrc:
      this->crc_errors_++;
      ESP_LOGW(TAG, "CRC ERROR");
      return;
    case ESPTelemetry::DecodeResult::UnsupportedVersion:
      this->decode_errors_++;
      ESP_LOGW(TAG, "UNSUPPORTED VERSION");
      return;
    case ESPTelemetry::DecodeResult::PayloadTooLarge:
      this->decode_errors_++;
      ESP_LOGW(TAG, "DECODE ERROR payload too large");
      return;
  }
}

void DisplayProtocolUARTComponent::handle_snapshot_frame_(const ESPTelemetry::Frame &frame, uint32_t now) {
  if (frame.version == ESPTelemetry::kVersionV2 && ESPTelemetry::messageTypeIsV2Telemetry(frame.messageType)) {
    this->handle_telemetry_frame_(frame, now);
    return;
  }

  if (frame.messageType != ESPTelemetry::kMessageTypeSnapshot) {
    this->decode_errors_++;
    ESP_LOGW(TAG, "DECODE ERROR unsupported message type %u", static_cast<unsigned int>(frame.messageType));
    return;
  }

  ESPTelemetry::SnapshotPayload payload{};
  if (!ESPTelemetry::decodeSnapshotPayload(frame, payload)) {
    this->decode_errors_++;
    ESP_LOGW(TAG, "DECODE ERROR invalid snapshot payload");
    return;
  }

  // Transport-level counter: this frame decoded fine regardless of which
  // device it claims to be from.
  this->valid_frames_++;

  const int8_t device_index = device_index_for_id_(ESPTelemetry::snapshotDeviceId(payload));
  if (device_index < 0) {
    ESP_LOGD(TAG, "Ignoring v1 snapshot from unrecognized device_id %u",
             static_cast<unsigned int>(ESPTelemetry::snapshotDeviceId(payload)));
    return;
  }

  this->last_sequence_[device_index] = frame.sequence;
  this->have_last_sequence_[device_index] = true;
  this->latest_[device_index] = payload;
  this->have_snapshot_[device_index] = true;
  this->last_frame_ms_[device_index] = now;

  // Stage 38: this frame's own flags say whether the Gateway that sent it
  // currently considers its LuxPower source valid -- a Gateway that is
  // alive but has lost its source keeps sending frames (the transport
  // link stays up), so "a frame arrived" is deliberately NOT treated as
  // "the data in it is fresh". Both bits are required (input AND holding
  // block), matching the Gateway's own combined computation.
  const bool source_fresh =
      (payload.flags & (ESPTelemetry::SnapshotFlagInputCacheValid | ESPTelemetry::SnapshotFlagHoldingCacheValid)) ==
      (ESPTelemetry::SnapshotFlagInputCacheValid | ESPTelemetry::SnapshotFlagHoldingCacheValid);
  const bool was_fresh = this->data_fresh_[device_index];

  if (!this->link_connected_[device_index]) {
    ESP_LOGI(TAG, "UART LINK ESTABLISHED device_id=%u", static_cast<unsigned int>(device_index + 1));
    ESP_LOGI(TAG,
             "sequence: %u frame size: %u",
             static_cast<unsigned int>(frame.sequence),
             static_cast<unsigned int>(ESPTelemetry::kHeaderSize + frame.payloadLength + ESPTelemetry::kCrcSize));
  } else if (source_fresh && !was_fresh) {
    ESP_LOGI(TAG, "SOURCE DATA RESTORED device_id=%u", static_cast<unsigned int>(device_index + 1));
  }
  this->link_connected_[device_index] = true;
  if (source_fresh) {
    this->values_marked_stale_[device_index] = false;
  }
  this->set_device_freshness_(static_cast<uint8_t>(device_index), source_fresh);
  this->update_connection_status_(static_cast<uint8_t>(device_index));

  this->trace_frame_(frame);
  this->publish_snapshot_(static_cast<uint8_t>(device_index), now);
}

void DisplayProtocolUARTComponent::handle_telemetry_frame_(const ESPTelemetry::Frame &frame, uint32_t now) {
  ESPTelemetry::TelemetryPayload payload{};
  if (!ESPTelemetry::decodeTelemetryPayload(frame, payload)) {
    this->decode_errors_++;
    ESP_LOGW(TAG, "DECODE ERROR invalid v2 telemetry payload");
    return;
  }

  this->valid_frames_++;

  if (payload.deviceId == kControllerSystemDeviceId) {
    this->handle_system_telemetry_frame_(payload, frame, now);
    return;
  }

  const int8_t device_index_signed = device_index_for_id_(payload.deviceId);
  if (device_index_signed < 0) {
    ESP_LOGD(TAG, "Ignoring v2 telemetry from unrecognized device_id %u",
             static_cast<unsigned int>(payload.deviceId));
    return;
  }
  const uint8_t device_index = static_cast<uint8_t>(device_index_signed);

  this->last_sequence_[device_index] = frame.sequence;
  this->have_last_sequence_[device_index] = true;
  this->have_snapshot_[device_index] = true;
  this->last_frame_ms_[device_index] = now;

  if (payload.group == ESPTelemetry::TelemetryGroup::Status) {
    if ((payload.flags & ESPTelemetry::TelemetryGroupFlagCacheValid) != 0)
      this->latest_[device_index].flags |= ESPTelemetry::SnapshotFlagHoldingCacheValid;
    else
      this->latest_[device_index].flags &= static_cast<uint16_t>(~ESPTelemetry::SnapshotFlagHoldingCacheValid);
  } else {
    if ((payload.flags & ESPTelemetry::TelemetryGroupFlagCacheValid) != 0)
      this->latest_[device_index].flags |= ESPTelemetry::SnapshotFlagInputCacheValid;
    else
      this->latest_[device_index].flags &= static_cast<uint16_t>(~ESPTelemetry::SnapshotFlagInputCacheValid);
  }

  for (uint8_t i = 0; i < payload.fieldCount; ++i) {
    this->publish_telemetry_field_(device_index, payload.fields[i].fieldId, payload.fields[i].value, now);
  }

  // Stage 38: same "trust the Gateway's own source-validity signal, not
  // frame arrival" rule as handle_snapshot_frame_ -- but a single V2
  // frame only ever carries one group's bit (Status -> holding,
  // everything else -> input; see the accumulator update above), so this
  // checks the running latest-known state of BOTH bits, not just this
  // one frame's bit.
  const bool source_fresh =
      (this->latest_[device_index].flags &
       (ESPTelemetry::SnapshotFlagInputCacheValid | ESPTelemetry::SnapshotFlagHoldingCacheValid)) ==
      (ESPTelemetry::SnapshotFlagInputCacheValid | ESPTelemetry::SnapshotFlagHoldingCacheValid);
  const bool was_fresh = this->data_fresh_[device_index];

  if (!this->link_connected_[device_index]) {
    ESP_LOGI(TAG, "UART LINK ESTABLISHED device_id=%u", static_cast<unsigned int>(device_index + 1));
    ESP_LOGI(TAG,
             "sequence: %u frame size: %u",
             static_cast<unsigned int>(frame.sequence),
             static_cast<unsigned int>(ESPTelemetry::kHeaderSize + frame.payloadLength + ESPTelemetry::kCrcSize));
  } else if (source_fresh && !was_fresh) {
    ESP_LOGI(TAG, "SOURCE DATA RESTORED device_id=%u", static_cast<unsigned int>(device_index + 1));
  }
  this->link_connected_[device_index] = true;
  if (source_fresh) {
    this->values_marked_stale_[device_index] = false;
  }
  this->set_device_freshness_(device_index, source_fresh);
  this->update_connection_status_(device_index);

  this->publish_float_(this->gateway_snapshot_age_sensor_[device_index], static_cast<float>(now - this->last_frame_ms_[device_index]));
  this->publish_float_(this->gateway_sequence_sensor_[device_index], static_cast<float>(this->last_sequence_[device_index]));
  this->publish_binary_(this->gateway_link_connected_sensor_[device_index], this->link_connected_[device_index]);
  this->trace_frame_(frame);
  this->recompute_derived_(device_index);
}

void DisplayProtocolUARTComponent::handle_system_telemetry_frame_(const ESPTelemetry::TelemetryPayload &payload,
                                                                  const ESPTelemetry::Frame &frame, uint32_t now) {
  this->last_system_frame_ms_ = now;
  this->have_system_frame_ = true;

  if (!this->system_link_fresh_) {
    ESP_LOGI(TAG, "UART LINK ESTABLISHED device_id=%u",
             static_cast<unsigned int>(kControllerSystemDeviceId));
    ESP_LOGI(TAG,
             "sequence: %u frame size: %u",
             static_cast<unsigned int>(frame.sequence),
             static_cast<unsigned int>(ESPTelemetry::kHeaderSize + frame.payloadLength + ESPTelemetry::kCrcSize));
  }
  this->system_link_fresh_ = true;

  for (uint8_t i = 0; i < payload.fieldCount; ++i) {
    this->publish_system_telemetry_field_(payload.fields[i].fieldId, payload.fields[i].value);
  }

  this->trace_frame_(frame);
}

void DisplayProtocolUARTComponent::publish_snapshot_(uint8_t device_index, uint32_t now) {
  if (!this->have_snapshot_[device_index]) {
    return;
  }
  const ESPTelemetry::SnapshotPayload &latest = this->latest_[device_index];

  if (latest.pv1PowerW != static_cast<int32_t>(ESPTelemetry::kInvalidI32))
    this->publish_float_(this->pv1_power_sensor_[device_index], static_cast<float>(latest.pv1PowerW));
  if (latest.pv2PowerW != static_cast<int32_t>(ESPTelemetry::kInvalidI32))
    this->publish_float_(this->pv2_power_sensor_[device_index], static_cast<float>(latest.pv2PowerW));
  if (latest.batterySocX10 != ESPTelemetry::kInvalidU16)
    this->publish_float_(this->battery_soc_sensor_[device_index], static_cast<float>(latest.batterySocX10) / 10.0f);
  if (latest.batteryChargePowerW != static_cast<int32_t>(ESPTelemetry::kInvalidI32))
    this->publish_float_(this->battery_charge_power_sensor_[device_index], static_cast<float>(latest.batteryChargePowerW));
  if (latest.batteryDischargePowerW != static_cast<int32_t>(ESPTelemetry::kInvalidI32))
    this->publish_float_(this->battery_discharge_power_sensor_[device_index], static_cast<float>(latest.batteryDischargePowerW));
  if (latest.pv1EnergyWh != ESPTelemetry::kInvalidU32)
    this->publish_float_(this->pv1_energy_total_sensor_[device_index], static_cast<float>(latest.pv1EnergyWh) / 1000.0f);

  this->publish_float_(this->gateway_snapshot_age_sensor_[device_index], static_cast<float>(now - this->last_frame_ms_[device_index]));
  this->publish_float_(this->gateway_sequence_sensor_[device_index], static_cast<float>(this->last_sequence_[device_index]));

  this->publish_binary_(this->gateway_data_fresh_sensor_[device_index], this->data_fresh_[device_index]);
  this->publish_binary_(this->gateway_link_connected_sensor_[device_index], this->link_connected_[device_index]);
  this->publish_binary_(this->luxpower_tcp_connected_sensor_[device_index],
                        (latest.flags & ESPTelemetry::SnapshotFlagTcpConnected) != 0);
  this->publish_binary_(this->input_cache_valid_sensor_[device_index],
                        (latest.flags & ESPTelemetry::SnapshotFlagInputCacheValid) != 0);
  this->publish_binary_(this->holding_cache_valid_sensor_[device_index],
                        (latest.flags & ESPTelemetry::SnapshotFlagHoldingCacheValid) != 0);
  this->publish_binary_(this->snapshot_values_valid_sensor_[device_index],
                        (latest.flags & (ESPTelemetry::SnapshotFlagInputCacheValid |
                                         ESPTelemetry::SnapshotFlagHoldingCacheValid)) != 0);
  this->publish_binary_(this->feed_in_grid_enabled_sensor_[device_index],
                        (latest.flags & ESPTelemetry::SnapshotFlagFeedInEnabled) != 0);
  this->recompute_derived_(device_index);
}

void DisplayProtocolUARTComponent::publish_telemetry_field_(uint8_t device_index, uint16_t field_id, int32_t value, uint32_t now) {
  (void) now;
  if (value == static_cast<int32_t>(ESPTelemetry::kInvalidI32)) {
    return;
  }
  ESPTelemetry::SnapshotPayload &latest = this->latest_[device_index];

  switch (field_id) {
    case ESPTelemetry::FieldIdPv1Power:
      latest.pv1PowerW = value;
      this->publish_float_(this->pv1_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdPv2Power:
      latest.pv2PowerW = value;
      this->publish_float_(this->pv2_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBatterySoc:
      latest.batterySocX10 = static_cast<uint16_t>(value);
      this->publish_float_(this->battery_soc_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdBatteryChargePower:
      latest.batteryChargePowerW = value;
      this->publish_float_(this->battery_charge_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBatteryDischargePower:
      latest.batteryDischargePowerW = value;
      this->publish_float_(this->battery_discharge_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdPv1EnergyTotal:
      latest.pv1EnergyWh = static_cast<uint32_t>(value);
      this->publish_float_(this->pv1_energy_total_sensor_[device_index], static_cast<float>(value) / 1000.0f);
      return;
    case ESPTelemetry::FieldIdFeedInGridEnabled:
      if (value != 0)
        latest.flags |= ESPTelemetry::SnapshotFlagFeedInEnabled;
      else
        latest.flags &= static_cast<uint16_t>(~ESPTelemetry::SnapshotFlagFeedInEnabled);
      this->publish_binary_(this->feed_in_grid_enabled_sensor_[device_index], value != 0);
      return;
    // Stage 35: experimentally confirmed via live diagnostic-mode discovery
    // on Inverter #2 -- see stages/Stage35.md. Read-only, same one-shot
    // publish-on-arrival pattern as the other Stage 30 fields below (no
    // legacy SnapshotFlag bookkeeping needed, unlike FeedInGridEnabled
    // above, since neither field is part of the legacy 6-field
    // SnapshotPayload).
    case ESPTelemetry::FieldIdMaxBackflowPower:
      this->publish_float_(this->max_backflow_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdZeroExportEnabled:
      this->publish_binary_(this->zero_export_enabled_sensor_[device_index], value != 0);
      return;
    case ESPTelemetry::FieldIdBatteryCapacity:
      this->publish_float_(this->battery_capacity_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBmsMaxCellTemperature:
      this->publish_float_(this->bms_max_cell_temperature_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdPowerToGrid:
      this->publish_float_(this->power_to_grid_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdPowerFromGrid:
      this->publish_float_(this->power_from_grid_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdGridFlow:
      this->publish_float_(this->grid_flow_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdPv1Voltage:
      this->publish_float_(this->pv1_voltage_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdPv2Voltage:
      this->publish_float_(this->pv2_voltage_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdPv3Voltage:
      this->publish_float_(this->pv3_voltage_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdPv3Power:
      this->publish_float_(this->pv3_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdPv1EnergyToday:
      this->publish_float_(this->pv1_energy_today_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdPv2EnergyToday:
      this->publish_float_(this->pv2_energy_today_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdPv3EnergyToday:
      this->publish_float_(this->pv3_energy_today_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdPv2EnergyTotal:
      this->publish_float_(this->pv2_energy_total_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdPv3EnergyTotal:
      this->publish_float_(this->pv3_energy_total_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdBatteryVoltage:
      this->publish_float_(this->battery_voltage_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdBatterySoh:
      this->publish_float_(this->battery_soh_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBatteryTemperature:
      this->publish_float_(this->battery_temperature_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBatteryParallelNumber:
      this->publish_float_(this->battery_parallel_number_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBatteryTypeAndBrand:
      this->publish_float_(this->battery_type_and_brand_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBmsMaxChargeCurrent:
      this->publish_float_(this->bms_max_charge_current_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdBmsMaxDischargeCurrent:
      this->publish_float_(this->bms_max_discharge_current_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdBmsChargeVoltageReference:
      this->publish_float_(this->bms_charge_voltage_reference_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdBmsDischargeCutoffVoltage:
      this->publish_float_(this->bms_discharge_cutoff_voltage_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdBmsBatteryCurrent:
      this->publish_float_(this->bms_battery_current_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdBmsFaultCode:
      this->publish_float_(this->bms_fault_code_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBmsWarningCode:
      this->publish_float_(this->bms_warning_code_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBmsMaxCellVoltage:
      this->publish_float_(this->bms_max_cell_voltage_sensor_[device_index], static_cast<float>(value) / 1000.0f);
      return;
    case ESPTelemetry::FieldIdBmsMinCellVoltage:
      this->publish_float_(this->bms_min_cell_voltage_sensor_[device_index], static_cast<float>(value) / 1000.0f);
      return;
    case ESPTelemetry::FieldIdBmsMinCellTemperature:
      this->publish_float_(this->bms_min_cell_temperature_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdBmsFirmwareUpdateState:
      this->publish_float_(this->bms_firmware_update_state_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBmsCycleCount:
      this->publish_float_(this->bms_cycle_count_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdInverterBatteryVoltageSample:
      this->publish_float_(this->inverter_battery_voltage_sample_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdChargeEnergyToday:
      this->publish_float_(this->charge_energy_today_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdDischargeEnergyToday:
      this->publish_float_(this->discharge_energy_today_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdChargeEnergyTotal:
      this->publish_float_(this->charge_energy_total_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdDischargeEnergyTotal:
      this->publish_float_(this->discharge_energy_total_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdGridVoltage:
      this->publish_float_(this->grid_voltage_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdGridVoltageS:
      this->publish_float_(this->grid_voltage_s_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdGridVoltageT:
      this->publish_float_(this->grid_voltage_t_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdGridFrequency:
      this->publish_float_(this->grid_frequency_sensor_[device_index], static_cast<float>(value) / 100.0f);
      return;
    case ESPTelemetry::FieldIdInverterPower:
      this->publish_float_(this->inverter_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdAcChargingRectificationPower:
      this->publish_float_(this->ac_charging_rectification_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdInverterCurrent:
      this->publish_float_(this->inverter_current_sensor_[device_index], static_cast<float>(value) / 100.0f);
      return;
    case ESPTelemetry::FieldIdPowerFactor:
      this->publish_float_(this->power_factor_sensor_[device_index], static_cast<float>(value) / 1000.0f);
      return;
    case ESPTelemetry::FieldIdEnergyToGridToday:
      this->publish_float_(this->energy_to_grid_today_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdEnergyFromGridToday:
      this->publish_float_(this->energy_from_grid_today_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdEnergyToGridTotal:
      this->publish_float_(this->energy_to_grid_total_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdEnergyFromGridTotal:
      this->publish_float_(this->energy_from_grid_total_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdOngridLoadPower:
      this->publish_float_(this->ongrid_load_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBus1Voltage:
      this->publish_float_(this->bus1_voltage_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdBus2Voltage:
      this->publish_float_(this->bus2_voltage_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdHalfBusVoltage:
      this->publish_float_(this->half_bus_voltage_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdEpsVoltage:
      this->publish_float_(this->eps_voltage_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdEpsVoltageS:
      this->publish_float_(this->eps_voltage_s_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdEpsVoltageT:
      this->publish_float_(this->eps_voltage_t_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdEpsFrequency:
      this->publish_float_(this->eps_frequency_sensor_[device_index], static_cast<float>(value) / 100.0f);
      return;
    case ESPTelemetry::FieldIdEpsPower:
      this->publish_float_(this->eps_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdEpsApparentPower:
      this->publish_float_(this->eps_apparent_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdEpsEnergyToday:
      this->publish_float_(this->eps_energy_today_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdEpsEnergyTotal:
      this->publish_float_(this->eps_energy_total_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdInternalTemperature:
      this->publish_float_(this->internal_temperature_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdRadiatorTemperature:
      this->publish_float_(this->radiator_temperature_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdRadiatorTemperature2:
      this->publish_float_(this->radiator_temperature_2_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdInverterState:
      this->publish_float_(this->inverter_state_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdInternalFaultCode:
      this->publish_float_(this->internal_fault_code_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdAcInputType:
      this->publish_float_(this->ac_input_type_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdAutoTestStatus:
      this->publish_float_(this->auto_test_status_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdInverterEnergyToday:
      this->publish_float_(this->inverter_energy_today_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdAcChargeEnergyToday:
      this->publish_float_(this->ac_charge_energy_today_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdInverterEnergyTotal:
      this->publish_float_(this->inverter_energy_total_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdAcChargeEnergyTotal:
      this->publish_float_(this->ac_charge_energy_total_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdTotalRunningTime:
      this->publish_float_(this->total_running_time_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdGeneratorVoltage:
      this->publish_float_(this->generator_voltage_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdGeneratorFrequency:
      this->publish_float_(this->generator_frequency_sensor_[device_index], static_cast<float>(value) / 100.0f);
      return;
    case ESPTelemetry::FieldIdGeneratorPower:
      this->publish_float_(this->generator_power_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdGeneratorEnergyToday:
      this->publish_float_(this->generator_energy_today_sensor_[device_index], static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdPv1Current:
      this->publish_float_(this->pv1_current_sensor_[device_index], static_cast<float>(value) / 100.0f);
      return;
    case ESPTelemetry::FieldIdPv2Current:
      this->publish_float_(this->pv2_current_sensor_[device_index], static_cast<float>(value) / 100.0f);
      return;
    case ESPTelemetry::FieldIdPv3Current:
      this->publish_float_(this->pv3_current_sensor_[device_index], static_cast<float>(value) / 100.0f);
      return;
    case ESPTelemetry::FieldIdBatteryFlow:
      this->publish_float_(this->battery_flow_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBmsCellDifference:
      this->publish_float_(this->bms_cell_difference_sensor_[device_index], static_cast<float>(value) / 1000.0f);
      return;
    case ESPTelemetry::FieldIdGridConnected:
      this->publish_float_(this->grid_connected_sensor_[device_index], value != 0 ? 1.0f : 0.0f);
      return;
    case ESPTelemetry::FieldIdActiveFaultCode:
      this->publish_float_(this->active_fault_code_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdActiveWarningCode:
      this->publish_float_(this->active_warning_code_sensor_[device_index], static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdLoadPower:
      this->publish_float_(this->load_power_sensor_[device_index], static_cast<float>(value));
      return;
    default:
      ESP_LOGD(TAG, "Ignoring unknown v2 field id %u", static_cast<unsigned int>(field_id));
      return;
  }
}

void DisplayProtocolUARTComponent::publish_system_telemetry_field_(uint16_t field_id, int32_t value) {
  switch (field_id) {
    case ESPTelemetry::FieldIdSystemOutputVoltage:
      this->publish_float_(this->system_output_voltage_sensor_, scaled_or_nan_(value, 10.0f));
      return;
    case ESPTelemetry::FieldIdSystemOutputCurrent:
      this->publish_float_(this->system_output_current_sensor_, scaled_or_nan_(value, 100.0f));
      return;
    case ESPTelemetry::FieldIdSystemOutputPower: {
      const float watts = scaled_or_nan_(value, 1.0f);
      this->publish_float_(this->system_output_power_sensor_, watts);
      this->publish_float_(this->power_total_sensor_, watts);
      return;
    }
    case ESPTelemetry::FieldIdSystemOutputEnergy:
      this->publish_float_(this->system_output_energy_sensor_, scaled_or_nan_(value, 100.0f));
      return;
    case ESPTelemetry::FieldIdSystemOutputFrequency:
      this->publish_float_(this->system_output_frequency_sensor_, scaled_or_nan_(value, 10.0f));
      return;
    case ESPTelemetry::FieldIdSystemOutputPowerFactor:
      this->publish_float_(this->system_output_power_factor_sensor_, scaled_or_nan_(value, 100.0f));
      return;
    case ESPTelemetry::FieldIdGridInputVoltage:
      this->publish_float_(this->grid_input_voltage_sensor_, scaled_or_nan_(value, 10.0f));
      return;
    case ESPTelemetry::FieldIdGridInputCurrent:
      this->publish_float_(this->grid_input_current_sensor_, scaled_or_nan_(value, 100.0f));
      return;
    case ESPTelemetry::FieldIdGridInputPower: {
      const float watts = scaled_or_nan_(value, 1.0f);
      this->publish_float_(this->grid_input_power_sensor_, watts);
      return;
    }
    case ESPTelemetry::FieldIdGridInputEnergy:
      this->publish_float_(this->grid_input_energy_sensor_, scaled_or_nan_(value, 100.0f));
      return;
    case ESPTelemetry::FieldIdGridInputFrequency:
      this->publish_float_(this->grid_input_frequency_sensor_, scaled_or_nan_(value, 10.0f));
      return;
    case ESPTelemetry::FieldIdGridInputPowerFactor:
      this->publish_float_(this->grid_input_power_factor_sensor_, scaled_or_nan_(value, 100.0f));
      return;
    case ESPTelemetry::FieldIdGridRawVoltage:
      this->publish_float_(this->grid_raw_voltage_sensor_, scaled_or_nan_(value, 10.0f));
      return;
    case ESPTelemetry::FieldIdDisplayEnabled:
      if (value != static_cast<int32_t>(ESPTelemetry::kInvalidI32)) {
        this->publish_binary_(this->display_enabled_sensor_, value != 0);
      }
      return;
    default:
      ESP_LOGD(TAG, "Ignoring unknown Controller/system field id %u", static_cast<unsigned int>(field_id));
      return;
  }
}

void DisplayProtocolUARTComponent::publish_diagnostics_(uint32_t now) {
  for (uint8_t device_index = 0; device_index < kDeviceCount; ++device_index) {
    if (this->have_snapshot_[device_index]) {
      this->publish_float_(this->gateway_snapshot_age_sensor_[device_index],
                           static_cast<float>(now - this->last_frame_ms_[device_index]));
    }
  }
  // Whole-UART-link counters -- see member declaration note.
  this->publish_float_(this->uart_valid_frames_sensor_, static_cast<float>(this->valid_frames_));
  this->publish_float_(this->uart_crc_errors_sensor_, static_cast<float>(this->crc_errors_));
  this->publish_float_(this->uart_decode_errors_sensor_, static_cast<float>(this->decode_errors_));
  this->publish_float_(this->uart_sequence_gaps_sensor_, static_cast<float>(this->sequence_gaps_));
  this->publish_float_(this->uart_duplicate_frames_sensor_, static_cast<float>(this->duplicate_frames_));
}

void DisplayProtocolUARTComponent::send_display_status_(uint32_t now) {
  if (this->last_display_status_tx_ms_ != 0 && now - this->last_display_status_tx_ms_ < kDisplayStatusIntervalMs) {
    return;
  }
  this->last_display_status_tx_ms_ = now;

  ESPTelemetry::TelemetryPayload status{};
  status.deviceId = ESPTelemetry::kDeviceIdDisplay;
  status.group = ESPTelemetry::TelemetryGroup::Status;
  status.flags = ESPTelemetry::TelemetryGroupFlagValuesValid | ESPTelemetry::TelemetryGroupFlagCacheValid;
  status.fieldCount = 1;
  status.fields[0] = {ESPTelemetry::FieldIdDisplayMaintenanceWifiActual, 0};

  uint8_t frame[ESPTelemetry::kMaxFrameSize];
  const size_t frame_length =
      ESPTelemetry::encodeTelemetry(status, ESPTelemetry::kMessageTypeStatus,
                                    this->next_display_status_sequence_++, now, frame, sizeof(frame));
  if (frame_length > 0 && this->send_raw_frame(frame, frame_length)) {
    ++this->display_status_frames_sent_;
    return;
  }
  ++this->display_status_send_failures_;
}

void DisplayProtocolUARTComponent::update_stale_state_(uint32_t now) {
  // Stage 32: independent per device -- powering one Gateway off/on must
  // never affect the other's freshness state.
  //
  // Transport-link fallback: no frame of any kind arrived within
  // stale_timeout_ms_ (Gateway/Bridge/ESP-NOW itself is unreachable). Short
  // Gateway source/cache gaps may set data_fresh_ false, but the offline HMI
  // keeps last valid readings until this transport timeout trips.
  for (uint8_t device_index = 0; device_index < kDeviceCount; ++device_index) {
    if (!this->have_snapshot_[device_index]) {
      continue;
    }
    const bool link_alive = (now - this->last_frame_ms_[device_index]) <= this->stale_timeout_ms_;
    if (link_alive) {
      continue;
    }
    this->link_connected_[device_index] = false;
    this->set_device_freshness_(device_index, false);
    if (!this->values_marked_stale_[device_index]) {
      this->values_marked_stale_[device_index] = true;
      this->mark_device_stale_(device_index);
    }
    this->update_connection_status_(device_index);
  }

  if (this->have_system_frame_ && this->system_link_fresh_ &&
      (now - this->last_system_frame_ms_) > this->stale_timeout_ms_) {
    this->system_link_fresh_ = false;
    this->mark_system_stale_();
  }
}

void DisplayProtocolUARTComponent::set_device_freshness_(uint8_t device_index, bool fresh) {
  const bool was_fresh = this->data_fresh_[device_index];
  this->data_fresh_[device_index] = fresh;
  this->publish_binary_(this->gateway_data_fresh_sensor_[device_index], fresh);
  (void) was_fresh;
}

void DisplayProtocolUARTComponent::mark_device_stale_(uint8_t device_index) {
  ESP_LOGW(TAG, "DATA STALE device_id=%u", static_cast<unsigned int>(device_index + 1));
  // The visible Off state means no packets arrived within stale_timeout_ms_.
  // Only then clear displayed readings. During shorter source/cache gaps the
  // HMI deliberately preserves the last valid values.
  this->publish_float_(this->pv1_power_sensor_[device_index], NAN);
  this->publish_float_(this->pv2_power_sensor_[device_index], NAN);
  this->publish_float_(this->battery_soc_sensor_[device_index], NAN);
  this->publish_float_(this->max_backflow_power_sensor_[device_index], NAN);
  this->recompute_derived_(device_index);
}

void DisplayProtocolUARTComponent::mark_system_stale_() {
  ESP_LOGW(TAG, "DATA STALE device_id=%u", static_cast<unsigned int>(kControllerSystemDeviceId));
  this->publish_float_(this->system_output_voltage_sensor_, NAN);
  this->publish_float_(this->system_output_current_sensor_, NAN);
  this->publish_float_(this->system_output_power_sensor_, NAN);
  this->publish_float_(this->system_output_energy_sensor_, NAN);
  this->publish_float_(this->system_output_frequency_sensor_, NAN);
  this->publish_float_(this->system_output_power_factor_sensor_, NAN);
  this->publish_float_(this->grid_input_voltage_sensor_, NAN);
  this->publish_float_(this->grid_input_current_sensor_, NAN);
  this->publish_float_(this->grid_input_power_sensor_, NAN);
  this->publish_float_(this->grid_input_energy_sensor_, NAN);
  this->publish_float_(this->grid_input_frequency_sensor_, NAN);
  this->publish_float_(this->grid_input_power_factor_sensor_, NAN);
  this->publish_float_(this->grid_raw_voltage_sensor_, NAN);
  this->publish_float_(this->power_total_sensor_, NAN);
}

void DisplayProtocolUARTComponent::update_connection_status_(uint8_t device_index) {
  // Stage 33: CONNECTED/STALE/DISCONNECTED, derived purely from the
  // existing have_snapshot_/data_fresh_ state -- no separate timeout.
  const char *status;
  if (!this->have_snapshot_[device_index]) {
    status = "DISCONNECTED";
  } else if (this->data_fresh_[device_index]) {
    status = "CONNECTED";
  } else {
    status = "STALE";
  }
  this->publish_text_(this->connection_status_text_sensor_[device_index], status);
}

void DisplayProtocolUARTComponent::publish_binary_(binary_sensor::BinarySensor *sensor, bool value) {
  if (sensor == nullptr) {
    return;
  }
  if (sensor->has_state() && sensor->state == value) {
    return;
  }
  sensor->publish_state(value);
}

void DisplayProtocolUARTComponent::publish_float_(sensor::Sensor *sensor, float value) {
  if (sensor == nullptr) {
    return;
  }
  sensor->publish_state(value);
}

void DisplayProtocolUARTComponent::publish_text_(text_sensor::TextSensor *sensor, const char *value) {
  if (sensor == nullptr) {
    return;
  }
  if (sensor->has_state() && sensor->state == value) {
    return;
  }
  sensor->publish_state(value);
}

void DisplayProtocolUARTComponent::recompute_derived_(uint8_t device_index) {
  const bool values_available = !this->values_marked_stale_[device_index];

  sensor::Sensor *pv1 = this->pv1_power_sensor_[device_index];
  sensor::Sensor *pv2 = this->pv2_power_sensor_[device_index];
  const bool solar_ok = values_available && pv1 != nullptr && pv1->has_state() && pv2 != nullptr && pv2->has_state();
  this->publish_float_(this->solar_sensor_[device_index], solar_ok ? (pv1->state + pv2->state) : NAN);

  sensor::Sensor *load = this->load_power_sensor_[device_index];
  sensor::Sensor *eps = this->eps_power_sensor_[device_index];
  const bool power_ok = values_available && load != nullptr && load->has_state() && eps != nullptr && eps->has_state();
  this->publish_float_(this->derived_power_sensor_[device_index], power_ok ? (load->state + eps->state) : NAN);

  sensor::Sensor *to_grid = this->power_to_grid_sensor_[device_index];
  sensor::Sensor *from_grid = this->power_from_grid_sensor_[device_index];
  const bool grid_ok =
      values_available && to_grid != nullptr && to_grid->has_state() && from_grid != nullptr && from_grid->has_state();
  this->publish_float_(this->grid_net_sensor_[device_index], grid_ok ? (to_grid->state - from_grid->state) : NAN);

  sensor::Sensor *charge = this->battery_charge_power_sensor_[device_index];
  sensor::Sensor *discharge = this->battery_discharge_power_sensor_[device_index];
  const bool battery_ok =
      values_available && charge != nullptr && charge->has_state() && discharge != nullptr && discharge->has_state();
  this->publish_float_(this->battery_net_sensor_[device_index], battery_ok ? (charge->state - discharge->state) : NAN);

  this->recompute_totals_();
}

void DisplayProtocolUARTComponent::recompute_totals_() {
  this->publish_float_(this->solar_total_sensor_, combine_total_(this->solar_sensor_[0], this->solar_sensor_[1]));
  this->publish_float_(this->grid_total_sensor_, combine_total_(this->grid_net_sensor_[0], this->grid_net_sensor_[1]));
  this->publish_float_(this->battery_total_sensor_, combine_total_(this->battery_net_sensor_[0], this->battery_net_sensor_[1]));
}

float DisplayProtocolUARTComponent::combine_total_(sensor::Sensor *a, sensor::Sensor *b) {
  // Never treat a missing/untrusted inverter as zero -- see set_solar_total_sensor.
  if (a == nullptr || b == nullptr || !a->has_state() || !b->has_state()) return NAN;
  if (std::isnan(a->state) || std::isnan(b->state)) return NAN;
  return a->state + b->state;
}

float DisplayProtocolUARTComponent::scaled_or_nan_(int32_t value, float scale) {
  if (value == static_cast<int32_t>(ESPTelemetry::kInvalidI32)) return NAN;
  return static_cast<float>(value) / scale;
}

void DisplayProtocolUARTComponent::trace_frame_(const ESPTelemetry::Frame &frame) {
  if (!this->trace_frames_) {
    return;
  }
  ESP_LOGD(TAG,
           "TRACE frame version=%u type=%u payload=%u sequence=%u timestamp=%u",
           static_cast<unsigned int>(frame.version),
           static_cast<unsigned int>(frame.messageType),
           static_cast<unsigned int>(frame.payloadLength),
           static_cast<unsigned int>(frame.sequence),
           static_cast<unsigned int>(frame.timestampMs));
}

}  // namespace display_protocol_uart
}  // namespace esphome
