# Validation record

## Verified in this revision

- 12 Python unit tests passed: normal and demo cutoff boundaries, handover penalty, strict frame parsing, invalid frames, 12-hour boundary, zero-point first-session eligibility, abandoned first-session eligibility, separate cards, isolated demo balances, clock/order rejection, and persistence after reopening SQLite.
- Native C++ test passed for session timing, UID switching, millis rollover, held-card suppression, and removal/re-scan gating.

- Full Arduino UNO sketch compiled successfully with Arduino AVR core 1.8.8, Adafruit PN532 1.3.4, Adafruit BusIO 1.17.4, and TM1637 1.2.0. Build used 9,976 bytes of flash (30%) and 563 bytes of global RAM (27%).
- Synthetic stdin integration exercised accepted sessions, a repeated session blocked by the cooldown, the 1-point tier, handover penalty, and an invalid frame.

## Not verified

No physical Arduino, PN532, TM1637 display, relay, valve, or water-flow test was available for this revision. Compilation and software tests do not establish physical operation. All hardware acceptance steps below remain required; compile again if your board or dependencies differ. No water-saving outcome was measured.

## Bench acceptance checklist

1. Compile for the actual Arduino board with Adafruit PN532, BusIO, and TM1637 libraries installed; record versions and compile result.
2. With the valve disconnected, verify the relay's active polarity, startup state, and response to normal scan-out. Reconcile the actuator's wiring with the firmware's open/close assumption.
3. Confirm the PN532 uses I2C; verify reader IRQ/reset and display CLK/DIO occupy distinct pins.
4. Confirm an NFC scan opens a session, holding the card does not scan out, removal for at least 0.75 s rearms, and a second same-card scan closes the session.
5. Confirm card B after card A produces a penalized event for A and begins B at zero without commanding the valve closed.
6. Check the inverted display orientation, colon, 00:59 to 01:00 rollover, and idle 00:00.
7. In demo mode verify 2 s → 0 points, 3 s → 2, 9 s → 2, 10 s → 1, 14 s → 1, and 15 s → 0. Repeat scores without a cooldown.
8. In normal mode verify 179/180, 599/600, and 899/900-second boundaries using synthetic input or timed sessions. Verify the first zero-point shower consumes eligibility.
9. Restart Python and confirm prior balances and cooldown anchors remain. Verify a board reset and a disconnected serial receiver are reported as limitations, not recovered events.
10. Disconnect the NFC reader while idle and during a session; characterize loop delay and relay behavior. A failed read can appear to be card removal.
11. Test the session-duration cap with a temporary lower constant, then restore 5,999 seconds before committing. Confirm the cap commands close and normal-mode score is zero at 99:59.
12. Only after electrical checks, evaluate a supervised bench water test with suitable isolation and enclosure. Record measured behavior, not inferred valve movement.
