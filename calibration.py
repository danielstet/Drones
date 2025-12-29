import pyvjoy
import time
import math
import sys
import threading

# --- CONFIGURATION ---
DEVICE_ID = 1
MIN_VAL = 1
MAX_VAL = 32768
MID_VAL = 16384
RADIUS = 16000

# --- AXIS MAPPING ---
AXIS_LEFT_H = pyvjoy.HID_USAGE_RX  # Yaw (Left/Right)
AXIS_LEFT_V = pyvjoy.HID_USAGE_Z  # Throttle (Up/Down)
AXIS_RIGHT_H = pyvjoy.HID_USAGE_X  # Roll (Left/Right)
AXIS_RIGHT_V = pyvjoy.HID_USAGE_Y  # Pitch (Up/Down)

try:
    joystick = pyvjoy.VJoyDevice(DEVICE_ID)
except Exception as e:
    print(f"Error initializing vJoy: {e}")
    sys.exit(1)

# Global flag to control the background thread
keep_running = False


def set_axis(axis_id, value):
    val = int(max(MIN_VAL, min(MAX_VAL, value)))
    joystick.set_axis(axis_id, val)


def center_sticks():
    """Centers all sticks immediately."""
    set_axis(AXIS_LEFT_H, MID_VAL)
    set_axis(AXIS_LEFT_V, MID_VAL)
    set_axis(AXIS_RIGHT_H, MID_VAL)
    set_axis(AXIS_RIGHT_V, MID_VAL)
    print(" -> Sticks Centered.")


# --- WORKER 1: CIRCLES ---
def circles_worker():
    global keep_running
    angle = 0.0
    step = 0.1

    while keep_running:
        ls_x = math.cos(angle)
        ls_y = math.sin(angle)
        rs_x = math.cos(angle)
        rs_y = -math.sin(angle)

        set_axis(AXIS_LEFT_H, MID_VAL + (ls_x * RADIUS))
        set_axis(AXIS_LEFT_V, MID_VAL + (ls_y * RADIUS))
        set_axis(AXIS_RIGHT_H, MID_VAL + (rs_x * RADIUS))
        set_axis(AXIS_RIGHT_V, MID_VAL + (rs_y * RADIUS))

        angle += step
        time.sleep(0.01)


# --- WORKER 2: LEFT STICK UP (Throttle 100%) ---
def throttle_up_worker():
    global keep_running
    set_axis(AXIS_LEFT_H, MID_VAL)
    set_axis(AXIS_RIGHT_H, MID_VAL)
    set_axis(AXIS_RIGHT_V, MID_VAL)

    while keep_running:
        for i in range(MID_VAL, MAX_VAL, 1000):
            if not keep_running: break
            set_axis(AXIS_LEFT_V, i)
            time.sleep(0.01)

        set_axis(AXIS_LEFT_V, MAX_VAL)
        time.sleep(0.5)
        set_axis(AXIS_LEFT_V, MID_VAL)
        time.sleep(0.5)


# --- WORKER 3: RIGHT STICK UP (Pitch 100%) ---
def pitch_up_worker():
    global keep_running
    set_axis(AXIS_LEFT_H, MID_VAL)
    set_axis(AXIS_LEFT_V, MID_VAL)
    set_axis(AXIS_RIGHT_H, MID_VAL)

    while keep_running:
        for i in range(MID_VAL, MAX_VAL, 1000):
            if not keep_running: break
            set_axis(AXIS_RIGHT_V, i)
            time.sleep(0.01)

        set_axis(AXIS_RIGHT_V, MAX_VAL)
        time.sleep(0.5)
        set_axis(AXIS_RIGHT_V, MID_VAL)
        time.sleep(0.5)


# --- WORKER 4: RIGHT STICK RIGHT (Roll Right) ---
def roll_right_worker():
    global keep_running
    set_axis(AXIS_LEFT_H, MID_VAL)
    set_axis(AXIS_LEFT_V, MID_VAL)
    set_axis(AXIS_RIGHT_V, MID_VAL)

    while keep_running:
        for i in range(MID_VAL, MAX_VAL, 1000):
            if not keep_running: break
            set_axis(AXIS_RIGHT_H, i)
            time.sleep(0.01)

        set_axis(AXIS_RIGHT_H, MAX_VAL)
        time.sleep(0.5)
        set_axis(AXIS_RIGHT_H, MID_VAL)
        time.sleep(0.5)


# --- WORKER 5: LEFT STICK LEFT (Yaw Left) ---
def yaw_left_worker():
    global keep_running
    set_axis(AXIS_LEFT_V, MID_VAL)
    set_axis(AXIS_RIGHT_H, MID_VAL)
    set_axis(AXIS_RIGHT_V, MID_VAL)

    while keep_running:
        for i in range(MID_VAL, MIN_VAL, -1000):
            if not keep_running: break
            set_axis(AXIS_LEFT_H, i)
            time.sleep(0.01)

        set_axis(AXIS_LEFT_H, MIN_VAL)
        time.sleep(0.5)
        set_axis(AXIS_LEFT_H, MID_VAL)
        time.sleep(0.5)


# --- WORKER 6: LEFT STICK DOWN (Throttle 0%) ---
def throttle_down_worker():
    global keep_running
    # Center others
    set_axis(AXIS_LEFT_H, MID_VAL)
    set_axis(AXIS_RIGHT_H, MID_VAL)
    set_axis(AXIS_RIGHT_V, MID_VAL)

    while keep_running:
        # Ramp Down (Decreasing Value) from Mid to Min
        for i in range(MID_VAL, MIN_VAL, -1000):
            if not keep_running: break
            set_axis(AXIS_LEFT_V, i)
            time.sleep(0.01)

        set_axis(AXIS_LEFT_V, MIN_VAL)  # Hold Max Down (0%)
        time.sleep(0.5)
        set_axis(AXIS_LEFT_V, MID_VAL)  # Reset
        time.sleep(0.5)


def start_thread(target_func):
    global keep_running

    keep_running = True
    t = threading.Thread(target=target_func)
    t.start()

    print("\n" + "=" * 40)
    print(" [RUNNING] Test Pattern Active")
    print(" PRESS [ENTER] TO STOP AND RECENTER")
    print("=" * 40 + "\n")

    input()

    keep_running = False
    t.join()
    center_sticks()


def main_menu():
    center_sticks()
    while True:
        print("\n--- Liftoff Calibration Helper ---")
        print("1. Calibration Circles (L: CCW / R: CW)")
        print("2. Left Stick UP (Throttle 100%)")
        print("3. Right Stick UP (Pitch 100%)")
        print("4. Right Stick RIGHT (Roll Right)")
        print("5. Left Stick LEFT (Yaw Left)")
        print("6. Left Stick DOWN (Throttle 0%)")
        print("7. Force Recenter")
        print("8. Exit")

        choice = input("Select option: ").strip()

        if choice == '1':
            start_thread(circles_worker)
        elif choice == '2':
            start_thread(throttle_up_worker)
        elif choice == '3':
            start_thread(pitch_up_worker)
        elif choice == '4':
            start_thread(roll_right_worker)
        elif choice == '5':
            start_thread(yaw_left_worker)
        elif choice == '6':
            start_thread(throttle_down_worker)
        elif choice == '7':
            center_sticks()
        elif choice == '8':
            center_sticks()
            break
        else:
            print("Invalid selection.")


if __name__ == "__main__":
    main_menu()