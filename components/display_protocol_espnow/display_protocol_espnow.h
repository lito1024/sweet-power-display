#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/core/component.h"

#include "ESPTelemetry.h"
#include "TelemetryPeerManager.h"
#include "TelemetryESPNowTransport.h"
#include "display_protocol_entity_metadata.generated.h"

namespace esphome {
namespace display_protocol_espnow {

class DisplayProtocolESPNowComponent : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;

  void set_stale_timeout(uint32_t timeout_ms) {
    this->stale_timeout_ms_ = timeout_ms;
    this->peer_manager_.setStaleTimeout(timeout_ms);
  }
  void set_trace_frames(bool trace_frames) { this->trace_frames_ = trace_frames; }
  void add_device_peer(uint8_t device_id,
                       uint8_t mac0,
                       uint8_t mac1,
                       uint8_t mac2,
                       uint8_t mac3,
                       uint8_t mac4,
                       uint8_t mac5);

  void set_pv1_power_sensor(sensor::Sensor *sensor) { this->pv1_power_sensor_ = sensor; }
  void set_pv2_power_sensor(sensor::Sensor *sensor) { this->pv2_power_sensor_ = sensor; }
  void set_battery_soc_sensor(sensor::Sensor *sensor) { this->battery_soc_sensor_ = sensor; }
  void set_battery_charge_power_sensor(sensor::Sensor *sensor) { this->battery_charge_power_sensor_ = sensor; }
  void set_battery_discharge_power_sensor(sensor::Sensor *sensor) { this->battery_discharge_power_sensor_ = sensor; }
  void set_pv1_energy_total_sensor(sensor::Sensor *sensor) { this->pv1_energy_total_sensor_ = sensor; }
  void set_gateway_snapshot_age_sensor(sensor::Sensor *sensor) { this->gateway_snapshot_age_sensor_ = sensor; }
  void set_gateway_sequence_sensor(sensor::Sensor *sensor) { this->gateway_sequence_sensor_ = sensor; }
  void set_espnow_received_packets_sensor(sensor::Sensor *sensor) { this->espnow_received_packets_sensor_ = sensor; }
  void set_espnow_crc_errors_sensor(sensor::Sensor *sensor) { this->espnow_crc_errors_sensor_ = sensor; }
  void set_espnow_decode_errors_sensor(sensor::Sensor *sensor) { this->espnow_decode_errors_sensor_ = sensor; }
  void set_espnow_sequence_gaps_sensor(sensor::Sensor *sensor) { this->espnow_sequence_gaps_sensor_ = sensor; }
  void set_espnow_duplicate_frames_sensor(sensor::Sensor *sensor) { this->espnow_duplicate_frames_sensor_ = sensor; }
  void set_espnow_rssi_sensor(sensor::Sensor *sensor) { this->espnow_rssi_sensor_ = sensor; }
  void set_espnow_unknown_sender_rejects_sensor(sensor::Sensor *sensor) {
    this->espnow_unknown_sender_rejects_sensor_ = sensor;
  }
  void set_espnow_device_id_mismatches_sensor(sensor::Sensor *sensor) {
    this->espnow_device_id_mismatches_sensor_ = sensor;
  }

  void set_gateway_data_fresh_sensor(binary_sensor::BinarySensor *sensor) { this->gateway_data_fresh_sensor_ = sensor; }
  void set_gateway_link_connected_sensor(binary_sensor::BinarySensor *sensor) { this->gateway_link_connected_sensor_ = sensor; }
  void set_luxpower_tcp_connected_sensor(binary_sensor::BinarySensor *sensor) {
    this->luxpower_tcp_connected_sensor_ = sensor;
  }
  void set_input_cache_valid_sensor(binary_sensor::BinarySensor *sensor) { this->input_cache_valid_sensor_ = sensor; }
  void set_holding_cache_valid_sensor(binary_sensor::BinarySensor *sensor) { this->holding_cache_valid_sensor_ = sensor; }
  void set_snapshot_values_valid_sensor(binary_sensor::BinarySensor *sensor) {
    this->snapshot_values_valid_sensor_ = sensor;
  }
  void set_feed_in_grid_enabled_sensor(binary_sensor::BinarySensor *sensor) {
    this->feed_in_grid_enabled_sensor_ = sensor;
  }

 protected:
  bool wifi_ready_() const;
  bool begin_transport_if_ready_();
  void stop_transport_();
  void handle_decode_result_(ESPTelemetry::DecodeResult result,
                             const ESPTelemetry::Frame &frame,
                             const uint8_t *sender_mac,
                             int8_t rssi,
                             uint32_t now);
  void handle_snapshot_frame_(const ESPTelemetry::Frame &frame, const uint8_t *sender_mac, int8_t rssi, uint32_t now);
  void handle_telemetry_frame_(const ESPTelemetry::Frame &frame, const uint8_t *sender_mac, int8_t rssi, uint32_t now);
  bool validate_peer_identity_(const uint8_t *sender_mac,
                               uint8_t device_id,
                               uint8_t version,
                               uint8_t message_type,
                               uint16_t sequence,
                               int8_t rssi,
                               uint32_t now);
  void publish_snapshot_(uint32_t now);
  void publish_telemetry_field_(uint16_t field_id, int32_t value, uint32_t now);
  void publish_diagnostics_(uint32_t now);
  void update_stale_state_(uint32_t now);
  void publish_binary_(binary_sensor::BinarySensor *sensor, bool value);
  void publish_float_(sensor::Sensor *sensor, float value);
  void trace_frame_(const ESPTelemetry::Frame &frame);

  ESPTelemetry::Decoder decoder_;
  ESPTelemetry::TelemetryPeerManager peer_manager_;
  ESPTelemetry::ESPNowTransport transport_;
  ESPTelemetry::SnapshotPayload latest_{};
  bool have_snapshot_ = false;
  bool data_fresh_ = false;
  bool link_connected_ = false;
  bool have_last_sequence_ = false;
  uint16_t last_sequence_ = 0;
  uint32_t last_frame_ms_ = 0;
  uint32_t last_publish_ms_ = 0;
  uint32_t stale_timeout_ms_ = 5000;
  bool trace_frames_ = false;
  bool transport_ready_ = false;
  bool identity_warning_logged_ = false;
  bool config_conflict_warning_logged_ = false;

  uint32_t valid_frames_ = 0;
  uint32_t crc_errors_ = 0;
  uint32_t decode_errors_ = 0;
  uint32_t sequence_gaps_ = 0;
  uint32_t duplicate_frames_ = 0;
  uint32_t identity_mismatches_ = 0;
  uint32_t config_conflicts_ = 0;

  sensor::Sensor *pv1_power_sensor_ = nullptr;
  sensor::Sensor *pv2_power_sensor_ = nullptr;
  sensor::Sensor *battery_soc_sensor_ = nullptr;
  sensor::Sensor *battery_charge_power_sensor_ = nullptr;
  sensor::Sensor *battery_discharge_power_sensor_ = nullptr;
  sensor::Sensor *pv1_energy_total_sensor_ = nullptr;
  sensor::Sensor *gateway_snapshot_age_sensor_ = nullptr;
  sensor::Sensor *gateway_sequence_sensor_ = nullptr;
  sensor::Sensor *espnow_received_packets_sensor_ = nullptr;
  sensor::Sensor *espnow_crc_errors_sensor_ = nullptr;
  sensor::Sensor *espnow_decode_errors_sensor_ = nullptr;
  sensor::Sensor *espnow_sequence_gaps_sensor_ = nullptr;
  sensor::Sensor *espnow_duplicate_frames_sensor_ = nullptr;
  sensor::Sensor *espnow_rssi_sensor_ = nullptr;
  sensor::Sensor *espnow_unknown_sender_rejects_sensor_ = nullptr;
  sensor::Sensor *espnow_device_id_mismatches_sensor_ = nullptr;

  binary_sensor::BinarySensor *gateway_data_fresh_sensor_ = nullptr;
  binary_sensor::BinarySensor *gateway_link_connected_sensor_ = nullptr;
  binary_sensor::BinarySensor *luxpower_tcp_connected_sensor_ = nullptr;
  binary_sensor::BinarySensor *input_cache_valid_sensor_ = nullptr;
  binary_sensor::BinarySensor *holding_cache_valid_sensor_ = nullptr;
  binary_sensor::BinarySensor *snapshot_values_valid_sensor_ = nullptr;
  binary_sensor::BinarySensor *feed_in_grid_enabled_sensor_ = nullptr;
};

}  // namespace display_protocol_espnow
}  // namespace esphome
