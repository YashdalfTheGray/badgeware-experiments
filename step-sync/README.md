# step-sync

MicroPython code for two badges that sync a step count and a status message with each other over Bluetooth. One badge is a Badger, with an e-ink display. The other is a Tufty, with a color display. Each badge reads its own step count from a Multi-Sensor Stick's accelerometer and sends it, together with a status message, to the other badge.

## How it works

Each badge advertises a small Bluetooth Low Energy packet with its badge ID, its current status, and its step count. There is no pairing and no BLE connection, only advertising and scanning, so a missed packet is not a problem. The next packet, about a second later, catches up.

Button A and button C cycle through a short list of status messages. Button B sends the selected status, together with the current step count, right away. Each badge also resends its last status periodically, so the other badge always has a recent value even with no button presses.

The screen shows a bar comparing the two step counts, a short log of the last status from each badge and how long ago it arrived, and the currently selected status for sending.

## Files

| File | Purpose |
| --- | --- |
| `sync_app.py` | The shared app: drawing, button handling, and the BLE send and receive logic. Both badges import this. |
| `ble_sync.py` | The Bluetooth advertising and scanning, the packet format, and the list of status messages. |
| `steps.py` | Reads the step count from the Multi-Sensor Stick's accelerometer. |
| `badger_init.py` | The entry point for the Badger. Rename it to `__init__.py` before you install it. |
| `tufty_init.py` | The entry point for the Tufty. Rename it to `__init__.py` before you install it. |

## Setup

1. Copy `sync_app.py`, `ble_sync.py`, and `steps.py` to `/lib` on both badges. Use Thonny's file panel, not disk mode.
2. Rename `badger_init.py` to `__init__.py` and copy it to `/apps/step_sync/` on the Badger.
3. Rename `tufty_init.py` to `__init__.py` and copy it to `/apps/step_sync/` on the Tufty.
4. Turn on both badges. Each one starts advertising and scanning right away.
