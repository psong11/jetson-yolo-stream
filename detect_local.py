"""
Local YOLO Detection — runs entirely on the Jetson Orin Nano.

Captures frames from the CSI camera (ArduCam IMX519), runs YOLO
inference on the Jetson GPU, and prints detections to the console.

No MacBook needed. No network. Just the Jetson and its camera.

Since the Jetson is headless (no monitor), we can't display a video
window. Instead we:
  - Print detections to the console in real time
  - Save a snapshot every 10 seconds with bounding boxes drawn on it
  - You can SCP the snapshots to your MacBook to see what the camera sees
"""

import cv2
import time
import os
from ultralytics import YOLO

# --- Config ---
MODEL = "yolo11n.pt"
CAMERA_ID = 0
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080
CONFIDENCE_THRESHOLD = 0.5
SNAPSHOT_INTERVAL = 10  # Save a snapshot every N seconds
SNAPSHOT_DIR = os.path.expanduser("~/snapshots")

def main():
    # Create snapshot directory
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    # Load YOLO model
    print(f"Loading YOLO model: {MODEL}")
    model = YOLO(MODEL)

    # Open CSI camera via GStreamer + NVIDIA's Argus camera stack.
    # We can't use cv2.VideoCapture(0) because the IMX519 outputs raw
    # 10-bit Bayer data that OpenCV can't debayer properly (green screen).
    # nvarguscamerasrc runs the image through NVIDIA's ISP (Image Signal
    # Processor) which handles debayering, white balance, and exposure.
    gst_pipeline = (
        f"nvarguscamerasrc ! "
        f"video/x-raw(memory:NVMM),width={CAPTURE_WIDTH},height={CAPTURE_HEIGHT},framerate=30/1 ! "
        f"nvvidconv ! video/x-raw,format=BGRx ! "
        f"videoconvert ! video/x-raw,format=BGR ! appsink"
    )
    print(f"Opening camera at {CAPTURE_WIDTH}x{CAPTURE_HEIGHT} via GStreamer...")
    cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        print("ERROR: Could not open camera.")
        return

    # Warm up
    print("Warming up model...")
    ret, frame = cap.read()
    if ret:
        model(frame, verbose=False)
    print("Ready. Press Ctrl+C to stop.\n")

    frame_count = 0
    start_time = time.time()
    last_snapshot = 0
    fps = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to capture frame.")
                continue

            # Run YOLO inference
            results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)

            # Extract detections
            detections = []
            for box in results[0].boxes:
                detections.append({
                    "class_name": model.names[int(box.cls[0])],
                    "confidence": float(box.conf[0]),
                    "bbox": [float(x) for x in box.xyxy[0]],
                })

            # Calculate FPS
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                start_time = time.time()

            # Print detections
            if detections:
                det_summary = ", ".join(
                    f"{d['class_name']} ({d['confidence']:.2f})"
                    for d in detections
                )
                print(f"[FPS: {fps:.1f}] {det_summary}")
            else:
                print(f"[FPS: {fps:.1f}] (nothing detected)", end="\r")

            # Save snapshot periodically
            now = time.time()
            if now - last_snapshot >= SNAPSHOT_INTERVAL:
                # Draw bounding boxes on the frame
                annotated = results[0].plot()
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                path = os.path.join(SNAPSHOT_DIR, f"snap_{timestamp}.jpg")
                cv2.imwrite(path, annotated)
                print(f"\n  -> Snapshot saved: {path}")
                last_snapshot = now

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        cap.release()
        print(f"Snapshots saved in {SNAPSHOT_DIR}/")
        print("Done.")

if __name__ == "__main__":
    main()
