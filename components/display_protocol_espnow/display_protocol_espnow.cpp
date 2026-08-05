#include "display_protocol_espnow.h"

#include "esphome/components/wifi/wifi_component.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"

#include <esp_wifi.h>

namespace esphome {
namespace display_protocol_espnow {

static const char *const TAG = "display_protocol_espnow";

void DisplayProtocolESPNowComponent::add_device_peer(uint8_t device_id,
                                                     uint8_t mac0,
                                                     uint8_t mac1,
                                                     uint8_t mac2,
                                                     uint8_t mac3,
                                                     uint8_t mac4,
                                                     uint8_t mac5) {
  const uint8_t mac[6] = {mac0, mac1, mac2, mac3, mac4, mac5};
  const ESPTelemetry::PeerRegisterResult result = this->peer_manager_.addTrustedPeer(mac, device_id);
  if (result != ESPTelemetry::PeerRegisterResult::Added) {
    this->config_conflicts_++;
  }
}

void DisplayProtocolESPNowComponent::setup() {
  this->transport_.setPeerManager(&this->peer_manager_);
  ESP_LOGI(TAG, "Display ESP-NOW receiver started");
  ESP_LOGI(TAG,
           "Trusted peers configured: %u/%u",
           static_cast<unsigned int>(this->peer_manager_.count()),
           static_cast<unsigned int>(this->peer_manager_.capacity()));
  ESP_LOGI(TAG,
           "Protocol versions: v%u snapshot, v%u grouped telemetry",
           static_cast<unsigned int>(ESPTelemetry::kVersion),
           static_cast<unsigned int>(ESPTelemetry::kVersionV2));
}

void DisplayProtocolESPNowComponent::loop() {
  const uint32_t now = millis();

  if (!this->wifi_ready_()) {
    this->stop_transport_();
    this->update_stale_state_(now);
    return;
  }

  if (!this->transport_ready_ && !this->begin_transport_if_ready_()) {
    this->update_stale_state_(now);
    return;
  }

  ESPTelemetry::Frame frame{};
  ESPTelemetry::ESPNowReceivedPacket packet{};
  while (this->transport_.receivePacket(packet)) {
    for (size_t i = 0; i < packet.length; ++i) {
      const ESPTelemetry::DecodeResult result = this->decoder_.feed(packet.data[i], now, frame);
      this->handle_decode_result_(result, frame, packet.senderMac, packet.rssi, now);
    }
  }

  this->decoder_.resetIfTimedOut(now, 1000);
  this->update_stale_state_(now);

  if (this->last_publish_ms_ == 0 || now - this->last_publish_ms_ >= 1000) {
    this->last_publish_ms_ = now;
    this->publish_diagnostics_(now);
  }
}

void DisplayProtocolESPNowComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "Display Protocol ESP-NOW Receiver");
  ESP_LOGCONFIG(TAG, "  Stale timeout: %u ms", static_cast<unsigned int>(this->stale_timeout_ms_));
  ESP_LOGCONFIG(TAG, "  Trace frames: %s", YESNO(this->trace_frames_));
  ESP_LOGCONFIG(TAG, "  Trusted peers: %u", static_cast<unsigned int>(this->peer_manager_.count()));
  ESP_LOGCONFIG(TAG, "  Peer config conflict: %s", YESNO(this->peer_manager_.configConflict()));
}

void DisplayProtocolESPNowComponent::handle_decode_result_(ESPTelemetry::DecodeResult result,
                                                           const ESPTelemetry::Frame &frame,
                                                           const uint8_t *sender_mac,
                                                           int8_t rssi,
                                                           uint32_t now) {
  switch (result) {
    case ESPTelemetry::DecodeResult::None:
      return;
    case ESPTelemetry::DecodeResult::FrameReady:
      this->handle_snapshot_frame_(frame, sender_mac, rssi, now);
      return;
    case ESPTelemetry::DecodeResult::SequenceGap:
      // Per-peer sequence accounting happens after device_id/MAC validation.
      this->handle_snapshot_frame_(frame, sender_mac, rssi, now);
      return;
    case ESPTelemetry::DecodeResult::BadCrc:
      this->crc_errors_++;
      this->peer_manager_.recordMalformedForMac(sender_mac);
      ESP_LOGW(TAG, "CRC ERROR");
      return;
    case ESPTelemetry::DecodeResult::UnsupportedVersion:
      this->decode_errors_++;
      this->peer_manager_.recordMalformedForMac(sender_mac);
      ESP_LOGW(TAG, "UNSUPPORTED VERSION");
      return;
    case ESPTelemetry::DecodeResult::PayloadTooLarge:
      this->decode_errors_++;
      this->peer_manager_.recordMalformedForMac(sender_mac);
      ESP_LOGW(TAG, "DECODE ERROR payload too large");
      return;
  }
}

bool DisplayProtocolESPNowComponent::wifi_ready_() const {
  return wifi::global_wifi_component != nullptr && wifi::global_wifi_component->is_connected();
}

bool DisplayProtocolESPNowComponent::begin_transport_if_ready_() {
  if (!this->wifi_ready_()) {
    return false;
  }

  wifi_ap_record_t ap_info{};
  if (esp_wifi_sta_get_ap_info(&ap_info) != ESP_OK) {
    return false;
  }

  ESP_LOGI(TAG, "WiFi channel confirmed: %u", static_cast<unsigned int>(ap_info.primary));
  this->transport_ready_ = this->transport_.begin();
  ESP_LOGI(TAG, "ESP-NOW init: %s", this->transport_ready_ ? "OK" : "FAILED");
  if (this->transport_ready_) {
    ESP_LOGI(TAG, "ESP-NOW transport ready with %u trusted peer(s)", static_cast<unsigned int>(this->peer_manager_.count()));
  }
  return this->transport_ready_;
}

void DisplayProtocolESPNowComponent::stop_transport_() {
  if (!this->transport_ready_ && !this->transport_.initialized()) {
    return;
  }
  this->transport_.end();
  this->transport_ready_ = false;
  ESP_LOGW(TAG, "ESP-NOW stopped because WiFi is disconnected");
}

bool DisplayProtocolESPNowComponent::validate_peer_identity_(const uint8_t *sender_mac,
                                                             uint8_t device_id,
                                                             uint8_t version,
                                                             uint8_t message_type,
                                                             uint16_t sequence,
                                                             int8_t rssi,
                                                             uint32_t now) {
  uint16_t previous_sequence = 0;
  const ESPTelemetry::PeerPacketResult result = this->peer_manager_.recordReceivedPacket(
      sender_mac, device_id, version, message_type, sequence, now, rssi, previous_sequence);
  switch (result) {
    case ESPTelemetry::PeerPacketResult::Accepted:
      this->identity_warning_logged_ = false;
      this->config_conflict_warning_logged_ = false;
      return true;
    case ESPTelemetry::PeerPacketResult::DuplicateSequence:
      this->duplicate_frames_++;
      ESP_LOGW(TAG,
               "Duplicate frame for device_id %u version %u message_type %u previous_sequence %u sequence %u",
               static_cast<unsigned int>(device_id),
               static_cast<unsigned int>(version),
               static_cast<unsigned int>(message_type),
               static_cast<unsigned int>(previous_sequence),
               static_cast<unsigned int>(sequence));
      return false;
    case ESPTelemetry::PeerPacketResult::SequenceGap:
      this->sequence_gaps_++;
      ESP_LOGW(TAG,
               "Sequence gap for device_id %u version %u message_type %u previous_sequence %u sequence %u",
               static_cast<unsigned int>(device_id),
               static_cast<unsigned int>(version),
               static_cast<unsigned int>(message_type),
               static_cast<unsigned int>(previous_sequence),
               static_cast<unsigned int>(sequence));
      return true;
    case ESPTelemetry::PeerPacketResult::SenderReboot:
      ESP_LOGI(TAG, "Sequence reset for device_id %u", static_cast<unsigned int>(device_id));
      return true;
    case ESPTelemetry::PeerPacketResult::UnknownSender:
      ESP_LOGW(TAG, "Rejected ESP-NOW packet from unknown sender");
      return false;
    case ESPTelemetry::PeerPacketResult::DeviceIdMismatch:
    case ESPTelemetry::PeerPacketResult::InvalidDeviceId:
      this->identity_mismatches_++;
      if (!this->identity_warning_logged_) {
        this->identity_warning_logged_ = true;
        ESP_LOGW(TAG, "Rejected ESP-NOW packet with device_id mismatch");
      }
      return false;
    case ESPTelemetry::PeerPacketResult::ConfigConflict:
      this->config_conflicts_++;
      if (!this->config_conflict_warning_logged_) {
        this->config_conflict_warning_logged_ = true;
        ESP_LOGW(TAG, "Rejected ESP-NOW packet because peer configuration is conflicting");
      }
      return false;
  }
  return false;
}

void DisplayProtocolESPNowComponent::handle_snapshot_frame_(const ESPTelemetry::Frame &frame,
                                                            const uint8_t *sender_mac,
                                                            int8_t rssi,
                                                            uint32_t now) {
  if (frame.version == ESPTelemetry::kVersionV2 && ESPTelemetry::messageTypeIsV2Telemetry(frame.messageType)) {
    this->handle_telemetry_frame_(frame, sender_mac, rssi, now);
    return;
  }

  if (frame.messageType != ESPTelemetry::kMessageTypeSnapshot) {
    this->decode_errors_++;
    this->peer_manager_.recordMalformedForMac(sender_mac);
    ESP_LOGW(TAG, "DECODE ERROR unsupported message type %u", static_cast<unsigned int>(frame.messageType));
    return;
  }

  ESPTelemetry::SnapshotPayload payload{};
  if (!ESPTelemetry::decodeSnapshotPayload(frame, payload)) {
    this->decode_errors_++;
    this->peer_manager_.recordMalformedForMac(sender_mac);
    ESP_LOGW(TAG, "DECODE ERROR invalid snapshot payload");
    return;
  }

  const uint8_t device_id = ESPTelemetry::snapshotDeviceId(payload);
  if (!this->validate_peer_identity_(sender_mac, device_id, frame.version, frame.messageType, frame.sequence, rssi,
                                     now)) {
    return;
  }

  this->last_sequence_ = frame.sequence;
  this->have_last_sequence_ = true;
  this->latest_ = payload;
  this->have_snapshot_ = true;
  this->last_frame_ms_ = now;
  this->valid_frames_++;

  if (!this->link_connected_) {
    ESP_LOGI(TAG, "ESP-NOW LINK ESTABLISHED");
    ESP_LOGI(TAG,
             "sequence: %u frame size: %u",
             static_cast<unsigned int>(frame.sequence),
             static_cast<unsigned int>(ESPTelemetry::kHeaderSize + frame.payloadLength + ESPTelemetry::kCrcSize));
  } else if (!this->data_fresh_) {
    ESP_LOGI(TAG, "ESP-NOW LINK RESTORED");
  }
  this->link_connected_ = true;
  this->data_fresh_ = true;

  this->trace_frame_(frame);
  this->publish_snapshot_(now);
}

void DisplayProtocolESPNowComponent::handle_telemetry_frame_(const ESPTelemetry::Frame &frame,
                                                             const uint8_t *sender_mac,
                                                             int8_t rssi,
                                                             uint32_t now) {
  ESPTelemetry::TelemetryPayload payload{};
  if (!ESPTelemetry::decodeTelemetryPayload(frame, payload)) {
    this->decode_errors_++;
    this->peer_manager_.recordMalformedForMac(sender_mac);
    ESP_LOGW(TAG, "DECODE ERROR invalid v2 telemetry payload");
    return;
  }

  if (!this->validate_peer_identity_(sender_mac, payload.deviceId, frame.version, frame.messageType, frame.sequence,
                                     rssi, now)) {
    return;
  }

  this->last_sequence_ = frame.sequence;
  this->have_last_sequence_ = true;
  this->have_snapshot_ = true;
  this->last_frame_ms_ = now;
  this->valid_frames_++;

  if (payload.group == ESPTelemetry::TelemetryGroup::Status) {
    if ((payload.flags & ESPTelemetry::TelemetryGroupFlagCacheValid) != 0)
      this->latest_.flags |= ESPTelemetry::SnapshotFlagHoldingCacheValid;
    else
      this->latest_.flags &= static_cast<uint16_t>(~ESPTelemetry::SnapshotFlagHoldingCacheValid);
  } else {
    if ((payload.flags & ESPTelemetry::TelemetryGroupFlagCacheValid) != 0)
      this->latest_.flags |= ESPTelemetry::SnapshotFlagInputCacheValid;
    else
      this->latest_.flags &= static_cast<uint16_t>(~ESPTelemetry::SnapshotFlagInputCacheValid);
  }

  for (uint8_t i = 0; i < payload.fieldCount; ++i) {
    this->publish_telemetry_field_(payload.fields[i].fieldId, payload.fields[i].value, now);
  }

  if (!this->link_connected_) {
    ESP_LOGI(TAG, "ESP-NOW LINK ESTABLISHED");
    ESP_LOGI(TAG,
             "sequence: %u frame size: %u",
             static_cast<unsigned int>(frame.sequence),
             static_cast<unsigned int>(ESPTelemetry::kHeaderSize + frame.payloadLength + ESPTelemetry::kCrcSize));
  } else if (!this->data_fresh_) {
    ESP_LOGI(TAG, "ESP-NOW LINK RESTORED");
  }
  this->link_connected_ = true;
  this->data_fresh_ = true;

  this->publish_float_(this->gateway_snapshot_age_sensor_, static_cast<float>(now - this->last_frame_ms_));
  this->publish_float_(this->gateway_sequence_sensor_, static_cast<float>(this->last_sequence_));
  this->publish_binary_(this->gateway_data_fresh_sensor_, this->data_fresh_);
  this->publish_binary_(this->gateway_link_connected_sensor_, this->link_connected_);
  this->trace_frame_(frame);
}

void DisplayProtocolESPNowComponent::publish_snapshot_(uint32_t now) {
  if (!this->have_snapshot_) {
    return;
  }

  if (this->latest_.pv1PowerW != static_cast<int32_t>(ESPTelemetry::kInvalidI32))
    this->publish_float_(this->pv1_power_sensor_, static_cast<float>(this->latest_.pv1PowerW));
  if (this->latest_.pv2PowerW != static_cast<int32_t>(ESPTelemetry::kInvalidI32))
    this->publish_float_(this->pv2_power_sensor_, static_cast<float>(this->latest_.pv2PowerW));
  if (this->latest_.batterySocX10 != ESPTelemetry::kInvalidU16)
    this->publish_float_(this->battery_soc_sensor_, static_cast<float>(this->latest_.batterySocX10) / 10.0f);
  if (this->latest_.batteryChargePowerW != static_cast<int32_t>(ESPTelemetry::kInvalidI32))
    this->publish_float_(this->battery_charge_power_sensor_, static_cast<float>(this->latest_.batteryChargePowerW));
  if (this->latest_.batteryDischargePowerW != static_cast<int32_t>(ESPTelemetry::kInvalidI32))
    this->publish_float_(this->battery_discharge_power_sensor_, static_cast<float>(this->latest_.batteryDischargePowerW));
  if (this->latest_.pv1EnergyWh != ESPTelemetry::kInvalidU32)
    this->publish_float_(this->pv1_energy_total_sensor_, static_cast<float>(this->latest_.pv1EnergyWh) / 1000.0f);

  this->publish_float_(this->gateway_snapshot_age_sensor_, static_cast<float>(now - this->last_frame_ms_));
  this->publish_float_(this->gateway_sequence_sensor_, static_cast<float>(this->last_sequence_));

  this->publish_binary_(this->gateway_data_fresh_sensor_, this->data_fresh_);
  this->publish_binary_(this->gateway_link_connected_sensor_, this->link_connected_);
  this->publish_binary_(this->luxpower_tcp_connected_sensor_,
                        (this->latest_.flags & ESPTelemetry::SnapshotFlagTcpConnected) != 0);
  this->publish_binary_(this->input_cache_valid_sensor_,
                        (this->latest_.flags & ESPTelemetry::SnapshotFlagInputCacheValid) != 0);
  this->publish_binary_(this->holding_cache_valid_sensor_,
                        (this->latest_.flags & ESPTelemetry::SnapshotFlagHoldingCacheValid) != 0);
  this->publish_binary_(this->snapshot_values_valid_sensor_,
                        (this->latest_.flags & (ESPTelemetry::SnapshotFlagInputCacheValid |
                                                ESPTelemetry::SnapshotFlagHoldingCacheValid)) != 0);
  this->publish_binary_(this->feed_in_grid_enabled_sensor_,
                        (this->latest_.flags & ESPTelemetry::SnapshotFlagFeedInEnabled) != 0);
}

void DisplayProtocolESPNowComponent::publish_telemetry_field_(uint16_t field_id, int32_t value, uint32_t now) {
  (void) now;
  if (value == static_cast<int32_t>(ESPTelemetry::kInvalidI32)) {
    return;
  }

  switch (field_id) {
    case ESPTelemetry::FieldIdPv1Power:
      this->latest_.pv1PowerW = value;
      this->publish_float_(this->pv1_power_sensor_, static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdPv2Power:
      this->latest_.pv2PowerW = value;
      this->publish_float_(this->pv2_power_sensor_, static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBatterySoc:
      this->latest_.batterySocX10 = static_cast<uint16_t>(value);
      this->publish_float_(this->battery_soc_sensor_, static_cast<float>(value) / 10.0f);
      return;
    case ESPTelemetry::FieldIdBatteryChargePower:
      this->latest_.batteryChargePowerW = value;
      this->publish_float_(this->battery_charge_power_sensor_, static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdBatteryDischargePower:
      this->latest_.batteryDischargePowerW = value;
      this->publish_float_(this->battery_discharge_power_sensor_, static_cast<float>(value));
      return;
    case ESPTelemetry::FieldIdPv1EnergyTotal:
      this->latest_.pv1EnergyWh = static_cast<uint32_t>(value);
      this->publish_float_(this->pv1_energy_total_sensor_, static_cast<float>(value) / 1000.0f);
      return;
    case ESPTelemetry::FieldIdFeedInGridEnabled:
      if (value != 0)
        this->latest_.flags |= ESPTelemetry::SnapshotFlagFeedInEnabled;
      else
        this->latest_.flags &= static_cast<uint16_t>(~ESPTelemetry::SnapshotFlagFeedInEnabled);
      this->publish_binary_(this->feed_in_grid_enabled_sensor_, value != 0);
      return;
    default:
      ESP_LOGD(TAG, "Ignoring unknown v2 field id %u", static_cast<unsigned int>(field_id));
      return;
  }
}

void DisplayProtocolESPNowComponent::publish_diagnostics_(uint32_t now) {
  const ESPTelemetry::TelemetryTransportStatistics stats = this->transport_.statistics();
  this->peer_manager_.updateStaleStates(now);
  if (this->have_snapshot_) {
    this->publish_float_(this->gateway_snapshot_age_sensor_, static_cast<float>(now - this->last_frame_ms_));
  }
  this->publish_float_(this->espnow_received_packets_sensor_, static_cast<float>(stats.packetsReceived));
  this->publish_float_(this->espnow_crc_errors_sensor_, static_cast<float>(this->crc_errors_));
  this->publish_float_(this->espnow_decode_errors_sensor_, static_cast<float>(this->decode_errors_));
  this->publish_float_(this->espnow_sequence_gaps_sensor_, static_cast<float>(this->sequence_gaps_));
  this->publish_float_(this->espnow_duplicate_frames_sensor_, static_cast<float>(this->duplicate_frames_));
  this->publish_float_(this->espnow_rssi_sensor_, static_cast<float>(stats.lastRssi));
  this->publish_float_(this->espnow_unknown_sender_rejects_sensor_, static_cast<float>(stats.unknownSenderRejects));
  this->publish_float_(this->espnow_device_id_mismatches_sensor_, static_cast<float>(this->identity_mismatches_));

  for (size_t i = 0; i < this->peer_manager_.count(); ++i) {
    const ESPTelemetry::TelemetryPeer *peer = this->peer_manager_.peerAt(i);
    if (peer == nullptr) continue;
    for (size_t j = 0; j < ESPTelemetry::kMaxTelemetryStreamsPerPeer; ++j) {
      const ESPTelemetry::TelemetryStreamState &stream = peer->streams[j];
      if (!stream.used) continue;
      ESP_LOGD(TAG,
               "stream device_id=%u version=%u message_type=%u last_seq=%u gaps=%u dup=%u reboots=%u",
               static_cast<unsigned int>(peer->device_id),
               static_cast<unsigned int>(stream.version),
               static_cast<unsigned int>(stream.messageType),
               static_cast<unsigned int>(stream.last_sequence),
               static_cast<unsigned int>(stream.sequence_gaps),
               static_cast<unsigned int>(stream.duplicate_packets),
               static_cast<unsigned int>(stream.reboot_resets));
    }
  }
}

void DisplayProtocolESPNowComponent::update_stale_state_(uint32_t now) {
  if (!this->have_snapshot_) {
    return;
  }

  const bool fresh = (now - this->last_frame_ms_) <= this->stale_timeout_ms_;
  if (fresh == this->data_fresh_) {
    return;
  }

  this->data_fresh_ = fresh;
  this->publish_binary_(this->gateway_data_fresh_sensor_, this->data_fresh_);
  if (!fresh) {
    ESP_LOGW(TAG, "ESP-NOW DATA STALE");
  } else {
    ESP_LOGI(TAG, "ESP-NOW LINK RESTORED");
  }
}

void DisplayProtocolESPNowComponent::publish_binary_(binary_sensor::BinarySensor *sensor, bool value) {
  if (sensor == nullptr) {
    return;
  }
  if (sensor->has_state() && sensor->state == value) {
    return;
  }
  sensor->publish_state(value);
}

void DisplayProtocolESPNowComponent::publish_float_(sensor::Sensor *sensor, float value) {
  if (sensor == nullptr) {
    return;
  }
  sensor->publish_state(value);
}

void DisplayProtocolESPNowComponent::trace_frame_(const ESPTelemetry::Frame &frame) {
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

}  // namespace display_protocol_espnow
}  // namespace esphome
