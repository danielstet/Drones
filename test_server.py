import cv2
import socket
import struct
import dxcam
import pyvjoy
import threading
import time

# --- CONFIGURATION ---
CLIENT_IP = "127.0.0.1"    # Client's IP (Where to send video)
VIDEO_PORT = 9001          # Port to SEND video to
CONTROL_PORT = 9000        # Port to LISTEN for controls on
VJOY_DEVICE_ID = 1

# --- SETUP VJOY ---
try:
    joystick = pyvjoy.VJoyDevice(VJOY_DEVICE_ID)
    print(f"vJoy Device {VJOY_DEVICE_ID} loaded successfully.")
except Exception as e:
    print(f"vJoy Error: {e}")
    exit()

# --- SETUP SCREEN CAPTURE ---
camera = dxcam.create(output_color="RGB") 
camera.start(target_fps=120, video_mode=True)

# --- SETUP UDP SOCKETS ---
# Socket 1: Video Sender (Outbound)
video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Socket 2: Control Receiver (Inbound)
drone_inputs_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# THIS WAS MISSING BEFORE: We must bind to listen!
drone_inputs_socket.bind(("0.0.0.0", CONTROL_PORT))
drone_inputs_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
drone_inputs_socket.setblocking(False) # Non-blocking mode

print(f"Server Ready.")
print(f" -> Listening for controls on Port {CONTROL_PORT}")
print(f" -> Sending video to {CLIENT_IP}:{VIDEO_PORT}")

running = True

def receive_controls():
    """
    Listens for control packets and moves vJoy axes.
    """
    global running
    print("Control listener thread started...")
    
    while running:
        try:
            # Try to get data
            try:
                data, addr = drone_inputs_socket.recvfrom(1024)
            except BlockingIOError:
                # No data waiting, sleep a tiny bit to save CPU
                time.sleep(0.001)
                continue
            except ConnectionResetError:
                continue

            if len(data) == 16:
                roll, pitch, yaw, throttle = struct.unpack('iiii', data)
                
                # Update vJoy
                joystick.set_axis(pyvjoy.HID_USAGE_X, roll)       
                joystick.set_axis(pyvjoy.HID_USAGE_Y, pitch)      
                joystick.set_axis(pyvjoy.HID_USAGE_RX, yaw)       
                joystick.set_axis(pyvjoy.HID_USAGE_Z, throttle)   
                
                # DEBUG: Print every 60th packet so we don't spam the console
                # or just print if throttle is high to verify
                if throttle > 1000:
                    # using \r overwrites the line so it looks clean
                    print(f"\rRecv: R={roll} P={pitch} Y={yaw} T={throttle}    ", end="")
                
        except Exception as e:
            print(f"Control Error: {e}")

# Start control thread
drone_inputs_thread = threading.Thread(target=receive_controls)
drone_inputs_thread.daemon = True
drone_inputs_thread.start()

# --- MAIN LOOP: SEND VIDEO ---
try:
    while True:
        frame = camera.get_latest_frame()
        
        if frame is not None:
            frame = cv2.resize(frame, (480, 360))
            encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            
            if len(buffer) < 65000:
                try:
                    video_socket.sendto(buffer, (CLIENT_IP, VIDEO_PORT))
                except Exception:
                    pass

except KeyboardInterrupt:
    print("\nStopping...")
    running = False
    camera.stop()
    video_socket.close()
    drone_inputs_socket.close()