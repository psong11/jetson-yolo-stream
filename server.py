"""
YOLO Inference Server — runs on the Jetson Orin Nano.

Listens on a TCP socket for image frames sent by the client (MacBook).
For each frame:
  1. Receives the raw image bytes
  2. Decodes it into a numpy array
  3. Runs YOLO object detection on the GPU
  4. Sends back the detection results as JSON

Protocol (simple length-prefixed messages):
  - Sender first sends 4 bytes: the message length as a big-endian integer
  - Then sends that many bytes of data
  - Receiver reads the 4-byte length, then reads exactly that many bytes

This way both sides always know how much data to expect.
"""

import socket
import struct
import json
import time
import numpy as np
import cv2
from ultralytics import YOLO

# --- Config ---
HOST = "0.0.0.0"  # Listen on all network interfaces (WiFi, USB, etc.)
PORT = 9999        # Arbitrary port number — just needs to match the client
MODEL = "yolo11n.pt"

def recv_exact(sock, num_bytes):
    """Receive exactly num_bytes from a socket.

    TCP doesn't guarantee that one send() arrives as one recv().
    A 500KB image might arrive in several chunks. This function
    keeps reading until we have all the bytes we asked for.
    """
    data = b""
    while len(data) < num_bytes:
        chunk = sock.recv(num_bytes - len(data))
        if not chunk:
            return None  # Connection closed
        data += chunk
    return data

def send_msg(sock, data):
    """Send a length-prefixed message.

    First sends 4 bytes containing the message length,
    then sends the actual message. This way the receiver
    knows exactly how many bytes to read.
    """
    length = len(data)
    sock.sendall(struct.pack(">I", length))  # >I = big-endian unsigned int (4 bytes)
    sock.sendall(data)

def recv_msg(sock):
    """Receive a length-prefixed message.

    Reads the 4-byte length header first, then reads that
    many bytes of actual data.
    """
    header = recv_exact(sock, 4)
    if header is None:
        return None
    length = struct.unpack(">I", header)[0]
    return recv_exact(sock, length)

def main():
    # Load YOLO model — this downloads the weights on first run
    print(f"Loading YOLO model: {MODEL}")
    model = YOLO(MODEL)

    # Warm up the model with a dummy image.
    # The first inference is always slow because CUDA needs to initialize
    # and allocate GPU memory. By doing it here, actual frames will be fast.
    print("Warming up model (first inference is slow)...")
    dummy = np.zeros((480, 640, 3), dtype=np.uint8)
    model(dummy, verbose=False)
    print("Model ready.")

    # Create a TCP socket
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # SO_REUSEADDR lets us restart the server immediately without waiting
    # for the OS to release the port (otherwise you get "Address already in use")
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(1)  # Accept 1 connection at a time

    print(f"Listening on {HOST}:{PORT} — waiting for client...")

    while True:
        # Wait for a client to connect
        conn, addr = server_sock.accept()
        print(f"Client connected: {addr}")

        try:
            while True:
                # 1. Receive a JPEG-encoded frame from the client
                frame_data = recv_msg(conn)
                if frame_data is None:
                    print("Client disconnected.")
                    break

                # 2. Decode JPEG bytes into a numpy array (BGR image)
                # The client compressed the frame as JPEG to reduce network traffic.
                # Now we decompress it back into a full image for YOLO.
                t_decode = time.time()
                frame = cv2.imdecode(
                    np.frombuffer(frame_data, dtype=np.uint8),
                    cv2.IMREAD_COLOR
                )
                decode_ms = (time.time() - t_decode) * 1000

                if frame is None:
                    continue

                # 3. Run YOLO inference
                t_infer = time.time()
                results = model(frame, verbose=False)
                infer_ms = (time.time() - t_infer) * 1000

                # 4. Extract detections into a simple list of dicts
                detections = []
                for box in results[0].boxes:
                    detections.append({
                        "class_id": int(box.cls[0]),
                        "class_name": model.names[int(box.cls[0])],
                        "confidence": round(float(box.conf[0]), 3),
                        "bbox": [round(float(x), 1) for x in box.xyxy[0]],
                    })

                # 5. Send results back as JSON
                response = json.dumps(detections).encode("utf-8")
                send_msg(conn, response)

                # Print timing every frame
                print(f"decode: {decode_ms:.1f}ms | infer: {infer_ms:.1f}ms | detections: {len(detections)}")

        except (ConnectionResetError, BrokenPipeError):
            print("Client connection lost.")
        finally:
            conn.close()
            print("Waiting for next client...")

if __name__ == "__main__":
    main()
