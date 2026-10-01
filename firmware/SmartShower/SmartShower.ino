#include <Wire.h>
#include <Adafruit_PN532.h>
#include <TM1637Display.h>
#include "Session.h"

// Proposed UNO/Nano ATmega328P pin assignment. Rewire display from D3/D2 to D5/D4.
constexpr uint8_t RELAY_PIN = 9;
constexpr uint8_t CLK_PIN = 5;
constexpr uint8_t DIO_PIN = 4;
constexpr uint8_t PN532_IRQ = 2;
constexpr uint8_t PN532_RESET = 3;
constexpr bool RELAY_ACTIVE_HIGH = true; // Verify the actual relay/valve before connecting it.
constexpr bool DISPLAY_INVERTED = true;
constexpr uint32_t MAX_SESSION_SECONDS = 5999; // 99:59 bench-prototype limit, not a brochure requirement.
static_assert(RELAY_PIN != CLK_PIN && RELAY_PIN != DIO_PIN && CLK_PIN != DIO_PIN,
              "Relay and display pins must be distinct");
static_assert(CLK_PIN != PN532_IRQ && CLK_PIN != PN532_RESET &&
              DIO_PIN != PN532_IRQ && DIO_PIN != PN532_RESET,
              "Display and NFC pins must be distinct");

Adafruit_PN532 nfc(PN532_IRQ, PN532_RESET);
TM1637Display display(CLK_PIN, DIO_PIN);
Session session;
ScanGate scanGate;
uint32_t lastDisplay = 0;

void setValve(bool open) {
  digitalWrite(RELAY_PIN, (open == RELAY_ACTIVE_HIGH) ? HIGH : LOW);
}

uint8_t flipSegment(uint8_t b) {
  return ((b & 0x01) << 3) | ((b & 0x02) << 3) | ((b & 0x04) << 3) |
         ((b & 0x08) >> 3) | ((b & 0x10) >> 3) | ((b & 0x20) >> 3) |
         (b & 0x40) | (b & 0x80);
}

void showTime(uint32_t seconds) {
  if (seconds > MAX_SESSION_SECONDS) seconds = MAX_SESSION_SECONDS;
  const uint8_t digits[] = {uint8_t(seconds / 600), uint8_t((seconds / 60) % 10),
                            uint8_t((seconds % 60) / 10), uint8_t(seconds % 10)};
  uint8_t segments[4];
  for (uint8_t i = 0; i < 4; ++i) {
    segments[i] = display.encodeDigit(digits[DISPLAY_INVERTED ? 3 - i : i]);
    if (DISPLAY_INVERTED) segments[i] = flipSegment(segments[i]);
  }
  segments[1] |= 0x80; // Center colon; check physical orientation on your display.
  display.setSegments(segments);
}

void sendData(uint32_t seconds, uint8_t penalty) {
  if (seconds > MAX_SESSION_SECONDS) seconds = MAX_SESSION_SECONDS;
  Serial.print(F("DATA,"));
  for (uint8_t i = 0; i < session.length; ++i) {
    if (session.uid[i] < 0x10) Serial.print('0');
    Serial.print(session.uid[i], HEX);
  }
  Serial.print(','); Serial.print(seconds); Serial.print(','); Serial.println(penalty);
}

void fail(const __FlashStringHelper *message) {
  setValve(false);
  Serial.println(message);
  const uint8_t dash[] = {0x40, 0x40, 0x40, 0x40};
  display.setSegments(dash);
  while (true) {} // Restart after fixing the reader. Output remains in the close-command state.
}

void setup() {
  // Set output latch before switching to OUTPUT to reduce startup relay glitches.
  setValve(false); pinMode(RELAY_PIN, OUTPUT);
  Serial.begin(115200);
  display.setBrightness(7); showTime(0);
  nfc.begin();
  if (!nfc.getFirmwareVersion()) fail(F("SYS_ERROR: PN532 missing"));
  if (!nfc.SAMConfig() || !nfc.setPassiveActivationRetries(0x00))
    fail(F("SYS_ERROR: NFC setup failed"));
  Serial.println(F("SYS_READY: Smart Shower prototype; scoring mode selected in Python"));
}

void loop() {
  uint32_t now = millis();
  if (session.open && session.seconds(now) >= MAX_SESSION_SECONDS) {
    setValve(false);
    sendData(MAX_SESSION_SECONDS, 0); // Normal mode awards 0 at this duration.
    session.open = false;
    Serial.println(F("SYS_EVENT: Session time limit; close commanded"));
  }

  uint8_t uid[10] = {0}; // Allow a 10-byte ISO14443 UID response; accept only 4/7 below.
  uint8_t length = 0;
  // Finite PN532 retries avoid leaving an infinite target request pending after timeout.
  // This is a bounded blocking read, not real-time/nonblocking firmware.
  bool present = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &length, 200);
  now = millis();
  if (present && length != 4 && length != 7) return;
  if (scanGate.update(present, now)) {
    if (!session.open) {
      session.begin(uid, length, now); setValve(true);
      Serial.println(F("SYS_EVENT: Valve open commanded"));
    } else if (session.same(uid, length)) {
      setValve(false); sendData(session.seconds(now), 0); session.open = false;
      Serial.println(F("SYS_EVENT: Valve close commanded"));
    } else {
      sendData(session.seconds(now), 1); // Previous user is ineligible for points.
      session.begin(uid, length, now); // Keep valve open; new user starts at zero.
      Serial.println(F("SYS_EVENT: Handover"));
    }
  }
  if ((uint32_t)(now - lastDisplay) >= 100UL) {
    showTime(session.open ? session.seconds(now) : 0);
    lastDisplay = now;
  }
}
