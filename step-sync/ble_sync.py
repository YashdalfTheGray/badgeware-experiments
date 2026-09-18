# ble_sync.py — broadcast-only BLE sync between the two badges.
#
# No pairing, no GATT connection — each badge just advertises a small
# packet of status + steps, and scans for the other badge's packet.
# A missed packet just means the next one (a second or so later) catches
# up, which is the right trade-off in a crowded 2.4GHz show floor.
#
# Copy this file to the badge's /lib folder (both Tufty and Badger need
# their own copy — they're separate filesystems).

import bluetooth
import struct
import time

_IRQ_SCAN_RESULT = const(5)

# Preset status messages. Index into this list is what actually gets sent
# over BLE (as a single byte) — keep this list identical and in the same
# order on both badges, or the indices won't line up.
STATUSES = [
    "Here",
    "In line",
    "Grabbing food",
    "Bathroom break",
    "Lost you",
    "Let's meet up",
]

# Reserved-for-testing company ID (we don't have a real registered one),
# plus our own 2-byte tag, so we can reliably ignore every other BLE
# device broadcasting nearby.
_COMPANY_ID = struct.pack("<H", 0xFFFF)
_APP_MAGIC = b"PX"


def _build_adv_payload(badge_id, status_code, steps):
    mfg = _COMPANY_ID + _APP_MAGIC + struct.pack("<BBH", badge_id, status_code, steps)
    flags = bytes((2, 0x01, 0x06))  # general discoverable, BR/EDR not supported
    mfg_ad = bytes((len(mfg) + 1, 0xFF)) + mfg
    return flags + mfg_ad


def _parse_adv_data(adv_data):
    i = 0
    while i < len(adv_data):
        length = adv_data[i]
        if length == 0:
            break
        ad_type = adv_data[i + 1]
        data = adv_data[i + 2 : i + 1 + length]
        if ad_type == 0xFF and data[0:2] == _COMPANY_ID and data[2:4] == _APP_MAGIC:
            badge_id, status_code, steps = struct.unpack("<BBH", data[4:8])
            return badge_id, status_code, steps
        i += 1 + length
    return None


class BadgeSync:
    """
    my_id: 0 or 1 — must be different on the two badges, so each ignores
    its own advertisements and only picks up the other one's.
    """

    def __init__(self, my_id):
        self.my_id = my_id
        self.peer_status = None
        self.peer_steps = None
        self.peer_last_seen = None  # ticks_ms of the last packet we received

        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._on_irq)
        self._ble.gap_scan(0, 30000, 30000, True)  # continuous active scan

    def _on_irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            _addr_type, _addr, _adv_type, _rssi, adv_data = data
            parsed = _parse_adv_data(bytes(adv_data))
            if parsed:
                badge_id, status_code, steps = parsed
                if badge_id != self.my_id:
                    self.peer_status = status_code
                    self.peer_steps = steps
                    self.peer_last_seen = time.ticks_ms()

    def broadcast(self, status_code, steps):
        """Start advertising our current status + steps. Call stop() a
        second or two later — the caller's main loop owns that timing,
        since it depends on whether this is a periodic heartbeat or an
        immediate user-triggered send."""
        payload = _build_adv_payload(self.my_id, status_code, steps)
        self._ble.gap_advertise(100_000, adv_data=payload, connectable=False)

    def stop_broadcast(self):
        self._ble.gap_advertise(None)

    def seconds_since_peer_update(self):
        """None if we've never heard from the other badge yet."""
        if self.peer_last_seen is None:
            return None
        return time.ticks_diff(time.ticks_ms(), self.peer_last_seen) // 1000
