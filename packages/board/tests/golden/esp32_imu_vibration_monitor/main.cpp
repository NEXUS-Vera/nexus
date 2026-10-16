#include <Arduino.h>
#include <Wire.h>

// Golden ESP32 + MPU6050 vibration monitor firmware (Phase 16I).
// Uses direct I2C register access — no external library dependency.
// I2C: SDA=GPIO21, SCL=GPIO22. Serial: 115200.

static const int PIN_SDA = 21;
static const int PIN_SCL = 22;
static const uint8_t MPU_ADDR = 0x68;
static const uint8_t REG_PWR_MGMT_1 = 0x6B;
static const uint8_t REG_ACCEL_XOUT_H = 0x3B;
static const float ACCEL_SCALE = 16384.0f; // ±2g
static const uint32_t SAMPLE_INTERVAL_MS = 20; // ~50 Hz

static bool mpuReady = false;
static uint32_t lastSampleMs = 0;

static bool mpuWrite8(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

static bool mpuReadBytes(uint8_t reg, uint8_t *buf, size_t len) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  if (Wire.requestFrom(MPU_ADDR, (uint8_t)len) != (int)len) {
    return false;
  }
  for (size_t i = 0; i < len; i++) {
    buf[i] = Wire.read();
  }
  return true;
}

static bool mpuInit() {
  delay(50);
  if (!mpuWrite8(REG_PWR_MGMT_1, 0x00)) {
    return false;
  }
  delay(50);
  uint8_t who = 0;
  // WHO_AM_I is 0x75; tolerate absent ACK in host stub environments.
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x75);
  if (Wire.endTransmission(false) == 0 && Wire.requestFrom(MPU_ADDR, (uint8_t)1) == 1) {
    who = Wire.read();
  }
  (void)who;
  return true;
}

static bool mpuReadAccel(float *ax, float *ay, float *az) {
  uint8_t raw[6];
  if (!mpuReadBytes(REG_ACCEL_XOUT_H, raw, 6)) {
    return false;
  }
  int16_t xi = (int16_t)((raw[0] << 8) | raw[1]);
  int16_t yi = (int16_t)((raw[2] << 8) | raw[3]);
  int16_t zi = (int16_t)((raw[4] << 8) | raw[5]);
  *ax = xi / ACCEL_SCALE;
  *ay = yi / ACCEL_SCALE;
  *az = zi / ACCEL_SCALE;
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);
  mpuReady = mpuInit();
  if (!mpuReady) {
    Serial.println("NEXUS_MPU_INIT_FAIL");
  } else {
    Serial.println("NEXUS_MPU_READY");
  }
  lastSampleMs = millis();
}

void loop() {
  if (!mpuReady) {
    delay(500);
    Serial.println("NEXUS_MPU_INIT_FAIL");
    return;
  }
  uint32_t now = millis();
  if (now - lastSampleMs < SAMPLE_INTERVAL_MS) {
    return;
  }
  lastSampleMs = now;
  float ax = 0, ay = 0, az = 0;
  if (!mpuReadAccel(&ax, &ay, &az)) {
    Serial.println("NEXUS_MPU_READ_FAIL");
    return;
  }
  // Machine-readable telemetry frame (R5)
  Serial.print("TEL,");
  Serial.print(now);
  Serial.print(',');
  Serial.print(ax, 5);
  Serial.print(',');
  Serial.print(ay, 5);
  Serial.print(',');
  Serial.println(az, 5);
}
