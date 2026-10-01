"""Local serial receiver and persistent reward ledger for the Smart Shower prototype."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

WINDOW_SECONDS = 12 * 60 * 60


def parse_event(line: str) -> tuple[str, int, int]:
    """Read the original Arduino DATA,UID,seconds,penalty protocol strictly."""
    parts = line.strip().split(',')
    if len(parts) != 4 or parts[0] != 'DATA':
        raise ValueError('Expected DATA,UID,seconds,penalty')
    _, uid, seconds, penalty = parts
    # Adafruit PN532 supports 4- or 7-byte ISO14443A UIDs here.
    if not re.fullmatch(r'(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{14})', uid):
        raise ValueError('UID must be 4 or 7 bytes of hexadecimal')
    if not seconds.isdecimal() or not penalty in ('0', '1'):
        raise ValueError('Duration must be a nonnegative integer; penalty must be 0 or 1')
    duration = int(seconds)
    if duration > 5999:
        raise ValueError('Duration exceeds firmware limit of 99:59')
    return uid.upper(), duration, int(penalty)


def score(duration: int, penalty: int, mode: str = 'normal') -> tuple[int, str]:
    if mode not in ('normal', 'demo'):
        raise ValueError('Unknown mode')
    if duration < 0 or penalty not in (0, 1):
        raise ValueError('Invalid duration or penalty')
    unit = 60 if mode == 'normal' else 1
    if penalty:
        return 0, 'Handover: previous user did not scan out'
    if duration < 3 * unit:
        return 0, 'Below minimum duration'
    if duration < 10 * unit:
        return 2, 'Short shower'
    if duration < 15 * unit:
        return 1, 'Moderate shower'
    return 0, 'At or above maximum reward duration'


class Ledger:
    """Persistent balances, session history, and first-session window anchors."""
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          mode TEXT NOT NULL, uid TEXT NOT NULL, balance INTEGER NOT NULL DEFAULT 0,
          window_start REAL, last_start REAL, PRIMARY KEY(mode, uid));
        CREATE TABLE IF NOT EXISTS sessions (
          id INTEGER PRIMARY KEY, mode TEXT NOT NULL, uid TEXT NOT NULL,
          received_at REAL NOT NULL, started_at REAL NOT NULL, duration INTEGER NOT NULL,
          penalty INTEGER NOT NULL, earned INTEGER NOT NULL, reason TEXT NOT NULL);
        ''')

    def record(self, uid: str, duration: int, penalty: int,
               mode: str = 'normal', now: float | None = None) -> dict:
        uid, duration, penalty = parse_event(f'DATA,{uid},{duration},{penalty}')
        earned, reason = score(duration, penalty, mode)
        now = time.time() if now is None else now
        started = now - duration
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO users(mode, uid) VALUES (?, ?)', (mode, uid))
            balance, anchor, last = self.db.execute(
                'SELECT balance, window_start, last_start FROM users WHERE mode=? AND uid=?',
                (mode, uid)).fetchone()
            if mode == 'normal':
                if last is not None and started < last:
                    raise ValueError('Out-of-order session or computer clock moved backward')
                if anchor is not None and started < anchor + WINDOW_SECONDS:
                    earned, reason = 0, 'First shower in this 12-hour window already recorded'
                else:
                    # First shower consumes the window even for 0-point / handover outcomes.
                    anchor = started
            balance += earned
            self.db.execute('UPDATE users SET balance=?, window_start=?, last_start=? WHERE mode=? AND uid=?',
                            (balance, anchor, started, mode, uid))
            self.db.execute('INSERT INTO sessions(mode,uid,received_at,started_at,duration,penalty,earned,reason) '
                            'VALUES (?,?,?,?,?,?,?,?)',
                            (mode, uid, now, started, duration, penalty, earned, reason))
        return dict(uid=uid, duration_seconds=duration, mode=mode, earned=earned,
                    total_points=balance, result=reason)

    def close(self):
        self.db.close()


def consume(line: str, ledger: Ledger, mode: str):
    if not line:
        return
    if not line.startswith('DATA,'):
        print(line, file=sys.stderr)
        return
    try:
        uid, seconds, penalty = parse_event(line)
        print(json.dumps(ledger.record(uid, seconds, penalty, mode)), flush=True)
    except ValueError as exc:
        print(f'Ignored invalid event: {exc}', file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--port', help='Arduino serial port, e.g. COM3')
    source.add_argument('--stdin', action='store_true', help='Read synthetic DATA lines without hardware')
    parser.add_argument('--mode', choices=['normal', 'demo'], default='normal')
    parser.add_argument('--db', help='Local SQLite file (default: data/<mode>.sqlite3)')
    args = parser.parse_args()
    path = Path(args.db or f'data/{args.mode}.sqlite3')
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(str(path))
    print(f'Mode: {args.mode}; ledger: {path}. Card UIDs are identifiers, not authenticated student IDs.', file=sys.stderr)
    try:
        if args.stdin:
            for line in sys.stdin:
                consume(line.strip(), ledger, args.mode)
        else:
            try:
                import serial
            except ImportError:
                print('Install requirements: python -m pip install -r requirements.txt', file=sys.stderr)
                return 1
            try:
                # Opening this port may reset the Arduino. Connect before starting a session.
                with serial.Serial(args.port, 115200, timeout=1) as port:
                    buffer = bytearray()
                    while True:
                        chunk = port.read(1)
                        if not chunk:
                            continue
                        if chunk == b'\n':
                            consume(buffer.decode('ascii', errors='replace').strip(), ledger, args.mode)
                            buffer.clear()
                        else:
                            buffer.extend(chunk)
                            if len(buffer) > 256:
                                raise ValueError('Oversized serial frame; reconnect and inspect the device')
            except (serial.SerialException, ValueError) as exc:
                print(f'Serial connection stopped: {exc}. Close Serial Monitor and verify port/wiring.', file=sys.stderr)
                return 1
    except KeyboardInterrupt:
        print('\nStopped. Completed sessions remain saved.', file=sys.stderr)
    finally:
        ledger.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
