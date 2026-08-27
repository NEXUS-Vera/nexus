# Nexus PlatformIO ESP32 firmware execution image (Phase 15E).
#
# Pre-installs PlatformIO Core and the espressif32 / Arduino toolchain for the
# fixed profile platformio-arduino-esp32-v1@1.0.0 ([env:nexus] / esp32dev).
# Network is disabled at runtime; dependencies must exist in the image.
#
# Build:
#   docker build -t nexus-firmware-platformio-esp32:1.0.0 .
#
# Pin reference (build time):
#   PlatformIO Core 6.x (pip pin below)
#   platform = espressif32 @ 6.8.1
#   framework = arduino @ 3.20017.241213

FROM python:3.13-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PLATFORMIO_CORE_DIR=/opt/platformio \
    PATH="/opt/platformio/penv/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        build-essential \
        g++ \
        make \
        cmake \
        libssl-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir "platformio==6.1.18" \
    && pio --version \
    && mkdir -p /workspace

WORKDIR /workspace

# Pre-fetch platform + framework for offline execution (network at build time only).
RUN printf '%s\n' \
    '[env:nexus]' \
    'platform = espressif32@6.8.1' \
    'board = esp32dev' \
    'framework = arduino' \
    'monitor_speed = 115200' \
    > /tmp/platformio.ini \
    && printf '%s\n' \
    '#include <Arduino.h>' \
    'void setup() {}' \
    'void loop() {}' \
    > /tmp/src/main.cpp \
    && mkdir -p /tmp/src \
    && cd /tmp \
    && pio run -e nexus \
    && rm -rf /tmp/.pio /tmp/platformio.ini /tmp/src

CMD ["pio", "--help"]
