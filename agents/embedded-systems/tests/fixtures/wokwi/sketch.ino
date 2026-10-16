#include <Arduino.h>
#include <Wire.h>

namespace {
constexpr uint8_t kMpu6050Address = 0x68;
constexpr int kSdaPin = 21;
constexpr int kSclPin = 22;
}  // namespace

void setup() {
  Serial.begin(115200);
  Wire.begin(kSdaPin, kSclPin);

  Wire.beginTransmission(kMpu6050Address);
  const uint8_t probe_result = Wire.endTransmission();
  if (probe_result == 0) {
    Serial.println("NEXUS_WOKWI_READY");
    return;
  }

  Serial.println("NEXUS_WOKWI_FAILURE MPU6050_NOT_FOUND");
}

void loop() {
  delay(1000);
}
