# steps.py — thin wrapper around the Multi-Sensor Stick's LSM6DS3 accelerometer.
#
# The LSM6DS3 has a hardware pedometer built into the chip itself: it counts
# steps continuously and autonomously, with or without anything reading it.
# So there's no sampling loop or peak-detection algorithm needed here — we
# just ask it for its current running total whenever we want a number.
#
# Copy this file to the badge's /lib folder (both Tufty and Badger need
# their own copy — they're separate filesystems).

from machine import I2C
from lsm6ds3 import LSM6DS3, NORMAL_MODE_104HZ

_imu = LSM6DS3(I2C(), mode=NORMAL_MODE_104HZ)


def get_steps():
    """Current step count since the last reset."""
    return _imu.get_step_count()


def reset_steps():
    """Zero the step counter (e.g. at the start of the day)."""
    _imu.reset_step_count()
