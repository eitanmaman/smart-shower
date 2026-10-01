#pragma once
#include <stdint.h>
#include <string.h>

// Platform-independent state logic; exercised by tests/firmware_test.cpp.
struct Session {
  bool open = false;
  uint32_t started = 0;
  uint8_t uid[7] = {0};
  uint8_t length = 0;
  bool same(const uint8_t *other, uint8_t size) const {
    return open && size == length && memcmp(uid, other, size) == 0;
  }
  void begin(const uint8_t *other, uint8_t size, uint32_t now) {
    memcpy(uid, other, size); length = size; started = now; open = true;
  }
  uint32_t seconds(uint32_t now) const { return (uint32_t)(now - started) / 1000UL; }
};

struct ScanGate {
  bool armed = true;
  bool sawAbsence = false;
  uint32_t absentSince = 0;
  // Card must leave the field for 750 ms before ANY subsequent scan is accepted.
  bool update(bool present, uint32_t now) {
    if (present) {
      sawAbsence = false;
      if (!armed) return false;
      armed = false;
      return true;
    }
    if (!sawAbsence) { sawAbsence = true; absentSince = now; }
    if ((uint32_t)(now - absentSince) >= 750UL) armed = true;
    return false;
  }
};
