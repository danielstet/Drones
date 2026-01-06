import socket
import cv2
import numpy as np
import struct
import threading
import time
import math
import sys

# --- CONFIGURATION ---
TARGET_IP = "127.0.0.1"    # Server IP
VIDEO_PORT = 9001          # Listen for Video here
CONTROL_PORT = 9000        # Send Controls here

# --- CONSTANTS ---
MIN_VAL = 1
MAX_VAL = 32768
MID_VAL = 16384
RADIUS = 16000

stick_state = {'roll': MID_VAL, 'pitch': MID_VAL, 'yaw': MID_VAL, 'throttle': 0}
keep_running = False
udp_lock = threading.Lock()

# --- SOCKET SETUP ---
# Socket for Sending Controls
sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Socket for Receiving Video
sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_in.bind(("0.0.0.0", VIDEO_PORT))
sock_in.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)

print(f"Client Connected.")
print(f" -> Sending controls to {TARGET_IP}:{CONTROL_PORT}")
print(f" -> Listening for video on Port {VIDEO_PORT}")

# --- HELPER FUNCTIONS ---
def send_packet():
    try:
        packet = struct.pack('iiii', 
                             int(stick_state['roll']), 
                             int(stick_state['pitch']), 
                             int(stick_state['yaw']), 
                             int(stick_state['throttle']))
        with udp_lock:
            sock_out.sendto(packet, (TARGET_IP, CONTROL_PORT))
    except Exception as e:
        print(f"Send Error: {e}")

def update_axis(axis_name, value):
    val = int(max(MIN_VAL, min(MAX_VAL, value)))
    stick_state[axis_name] = val
    send_packet()

def center_sticks():
    stick_state['roll'] = MID_VAL
    stick_state['pitch'] = MID_VAL
    stick_state['yaw'] = MID_VAL
    stick_state['throttle'] = MID_VAL 
    send_packet()
    print(" -> Sticks Centered.")

# --- TEST PATTERNS ---
def circles_worker():
    global keep_running
    angle = 0.0
    while keep_running:
        stick_state['yaw'] = MID_VAL + (math.cos(angle) * RADIUS)
        stick_state['throttle'] = MID_VAL + (math.sin(angle) * RADIUS)
        stick_state['roll'] = MID_VAL + (math.cos(angle) * RADIUS)
        stick_state['pitch'] = MID_VAL + (-math.sin(angle) * RADIUS)
        send_packet()
        angle += 0.1
        time.sleep(0.01)

def throttle_up_worker():
    global keep_running
    center_sticks()
    while keep_running:
        for i in range(MID_VAL, MAX_VAL, 1000):
            if not keep_running: break
            update_axis('throttle', i)
            time.sleep(0.01)
        update_axis('throttle', MAX_VAL)
        time.sleep(0.5)
        update_axis('throttle', MID_VAL)
        time.sleep(0.5)

# --- VIDEO THREAD ---
def video_receiver_thread():
    print("Video Receiver Started...")
    while True:
        try:
            data, addr = sock_in.recvfrom(65536)
            np_data = np.frombuffer(data, dtype=np.uint8)
            frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
            if frame is not None:
                cv2.putText(frame, f"THR: {stick_state['throttle']}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow("Drone Feed", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'): break
        except Exception: pass

# --- MAIN ---
def start_pattern(target_func):
    global keep_running
    keep_running = True
    t = threading.Thread(target=target_func)
    t.daemon = True
    t.start()
    input("\n[RUNNING PATTERN] Press Enter to Stop...")
    keep_running = False
    t.join()
    center_sticks()

if __name__ == "__main__":
    vid_thread = threading.Thread(target=video_receiver_thread)
    vid_thread.daemon = True
    vid_thread.start()
    center_sticks()
    
    while True:
        print("\n--- REMOTE Calibration ---")
        print("1. Circles (All Sticks)")
        print("2. Throttle Up")
        print("8. Exit")
        choice = input("Select: ")
        if choice == '1': start_pattern(circles_worker)
        elif choice == '2': start_pattern(throttle_up_worker)
        elif choice == '8': break
    
    sock_in.close()
    sock_out.close()
    sys.exit()