import pyvjoy
import time
import sys
import math
import threading

# --- CONFIGURATION ---
DEVICE_ID = 1 # <--V JoyDevice (check at vJoy config and set manually)
joystick = pyvjoy.VJoyDevice(DEVICE_ID)

# Constants
AXIS_THROTTLE = pyvjoy.HID_USAGE_Z  # Left Stick Vertical
MIN_VAL = 1
MID_VAL = 16384
MAX_VAL = 32768


def set_throttle(value):
    """Helper to set Z axis safely"""
    val = int(max(MIN_VAL, min(MAX_VAL, value)))
    joystick.set_axis(AXIS_THROTTLE, val)


def gradual_throttle_drop():
    print("Starting gradual drop to 0%...")

    # We start from MID_VAL (50%) and go down to MIN_VAL (0%)
    # step = -100 controls the speed (larger number = faster drop)
    for i in range(MID_VAL, MIN_VAL, -100):
        set_throttle(i)
        time.sleep(0.01)  # Controls smoothness (10ms delay)

    # Ensure we clamp exactly to the minimum at the end
    set_throttle(MIN_VAL)
    print("Throttle is now at 0% (Holding).")


if __name__ == "__main__":
    # 1. First, let's center it so we have a known starting point
    set_throttle(MID_VAL)
    time.sleep(1)

    # 2. Perform the drop
    gradual_throttle_drop()

    # 3. The script ends here, but vJoy will KEEP the value at 0.