"""
YOLO Streaming Client — runs on your MacBook.

Captures frames from the webcam, sends them to the Jetson for
YOLO inference, receives detection results, and displays the
annotated video feed.

The flow each frame:
  1. Capture a frame from the webcam (OpenCV)
  2. Compress it to JPEG (shrinks ~1MB raw frame to ~50KB for fast transfer)
  3. Send the JPEG bytes to the Jetson server over TCP
  4. Receive JSON detection results back
  5. Draw bounding boxes on the frame and display it
"""

import socket
import struct
import json
import time
import cv2
import numpy as np

# --- Config ---
JETSON_IP = "192.168.0.224"  # Your Jetson's WiFi IP address
PORT = 9999                   # Must match server.py
JPEG_QUALITY = 80             # 0-100. Higher = better image, bigger file, slower transfer

# Colors for bounding boxes (BGR format for OpenCV)
BOX_COLOR = (0, 255, 0)   # Green
TEXT_COLOR = (0, 255, 0)   # Green
TEXT_BG = (0, 0, 0)        # Black background for text readability

def recv_exact(sock, num_bytes):
    """Receive exactly num_bytes from a socket."""
    data = b""
    while len(data) < num_bytes:
        chunk = sock.recv(num_bytes - len(data))
        if not chunk:
            return None
        data += chunk
    return data

def send_msg(sock, data):
    """Send a length-prefixed message."""
    length = len(data)
    sock.sendall(struct.pack(">I", length))
    sock.sendall(data)

def recv_msg(sock):
    """Receive a length-prefixed message."""
    header = recv_exact(sock, 4)
    if header is None:
        return None
    length = struct.unpack(">I", header)[0]
    return recv_exact(sock, length)

def draw_detections(frame, detections):
    """Draw bounding boxes and labels on the frame.

    Each detection is a dict like:
      {"class_name": "person", "confidence": 0.89, "bbox": [x1, y1, x2, y2]}
    """
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        label = f"{det['class_name']} {det['confidence']:.2f}"

        # Draw the bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 2)

        # Draw label with background for readability
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
        cv2.rectangle(frame, (x1, y1 - text_size[1] - 10), (x1 + text_size[0], y1), TEXT_BG, -1)
        cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 1)

    return frame

def main():
    # Open the webcam
    print("Opening webcam...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return

    # Connect to the Jetson server
    print(f"Connecting to Jetson at {JETSON_IP}:{PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((JETSON_IP, PORT))
    except ConnectionRefusedError:
        print(f"ERROR: Could not connect to {JETSON_IP}:{PORT}")
        print("Make sure server.py is running on the Jetson.")
        cap.release()
        return

    print("Connected! Press 'q' to quit.")

    # FPS tracking
    frame_count = 0
    start_time = time.time()
    fps = 0

    try:
        while True:
            # 1. Capture a frame from the webcam
            ret, frame = cap.read()
            if not ret:
                break

            # 2. Compress frame to JPEG
            # Raw frame might be 1-2MB. JPEG at quality 80 is ~50-100KB.
            # This is important because we're sending it over WiFi each frame.
            _, jpeg_data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            jpeg_bytes = jpeg_data.tobytes()

            # 3. Send to Jetson
            send_msg(sock, jpeg_bytes)

            # 4. Receive detection results
            response = recv_msg(sock)
            if response is None:
                print("Lost connection to Jetson.")
                break

            detections = json.loads(response.decode("utf-8"))

            # 5. Draw bounding boxes on the original (uncompressed) frame
            frame = draw_detections(frame, detections)

            # Calculate and display FPS
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                start_time = time.time()

            # Draw FPS and detection count on frame
            info = f"FPS: {fps:.1f} | Detections: {len(detections)} | Jetson GPU"
            cv2.putText(frame, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            # Show the frame
            cv2.imshow("YOLO on Jetson", frame)

            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        sock.close()
        cap.release()
        cv2.destroyAllWindows()
        print("Done.")

if __name__ == "__main__":
    main()
