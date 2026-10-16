# fixtures

Deterministic source fixtures for embedded-systems tests.

`wokwi/sketch.ino` is the golden ESP32/MPU6050 smoke-test firmware source. It
uses I2C on GPIO21/GPIO22 and emits `NEXUS_WOKWI_READY` only after the sensor
responds at address `0x68`. Build products are intentionally excluded; provide
an externally compiled ELF through `NEXUS_WOKWI_FIRMWARE_ELF` when opting in to
the real Wokwi integration test.
