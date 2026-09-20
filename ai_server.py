from flask import Flask, Response, jsonify, render_template
import cv2
from ultralytics import YOLO
import threading
import time
import os

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

# Read camera stream URL from environment variable, fallback to local IP
VIDEO_URL = os.getenv("CAMERA_STREAM_URL", "http://192.0.0.4:8080/video")

# ============================================================
# YOLO MODEL
# ============================================================

model = YOLO("yolov8n.pt")

# ============================================================
# GLOBAL STATE & THREAD LOCKS
# ============================================================

latest_detections = []
latest_frame = None
lock = threading.Lock()

# ============================================================
# BACKGROUND CAPTURE & INFERENCE WORKER
# Runs once globally regardless of how many users view the dashboard
# ============================================================

def process_camera_stream():
    global latest_detections, latest_frame
    cap = None

    while True:
        if cap is None or not cap.isOpened():
            print(f"Connecting to camera stream at {VIDEO_URL}...")
            cap = cv2.VideoCapture(VIDEO_URL)

            if not cap.isOpened():
                print("ERROR: Could not connect to camera stream. Retrying in 2s...")
                time.sleep(2)
                continue

            print("Connected to camera stream. YOLO processing running.")

        success, frame = cap.read()

        if not success:
            print("Frame capture failed. Attempting reconnection...")
            cap.release()
            cap = None
            time.sleep(1)
            continue

        # Resize frame to prevent high network latency & CPU load
        frame = cv2.resize(frame, (640, 480))

        # Run YOLO inference
        results = model(frame, verbose=False, conf=0.40)
        result = results[0]

        annotated_frame = result.plot()

        # Parse detections
        detections = []
        if result.boxes is not None:
            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                class_name = model.names[class_id]

                detections.append({
                    "class": class_name,
                    "confidence": round(confidence * 100, 1)
                })

        # Encode frame to JPEG
        success, buffer = cv2.imencode(".jpg", annotated_frame)
        if success:
            encoded_bytes = buffer.tobytes()
            with lock:
                latest_detections = detections
                latest_frame = encoded_bytes

        time.sleep(0.03)  # Cap loop rate to ~30 FPS

# Start background thread immediately when app initializes
threading.Thread(target=process_camera_stream, daemon=True).start()

# ============================================================
# STREAM GENERATOR
# Simply broadcasts the latest cached frame to clients
# ============================================================

def generate_frames():
    while True:
        with lock:
            frame = latest_frame

        if frame is not None:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame
                + b"\r\n"
            )
        time.sleep(0.04)  # ~25 FPS stream delivery

# ============================================================
# DASHBOARD ROUTE
# ============================================================

@app.route("/")
def dashboard():
    return render_template("index.html")

# ============================================================
# AI VIDEO STREAM
# ============================================================

@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

# ============================================================
# AI DETECTIONS API
# Supports both /api/detections and /detections endpoints
# ============================================================

@app.route("/api/detections")
@app.route("/detections")
def detections():
    with lock:
        data = list(latest_detections)

    return jsonify({
        "count": len(data),
        "detections": data
    })

# ============================================================
# SERVER RUNNER
# ============================================================

if __name__ == "__main__":
    print("")
    print("==============================================")
    print(" MIRA AI VISION SERVER")
    print("==============================================")
    print("Dashboard : http://127.0.0.1:5000")
    print("AI Stream : http://127.0.0.1:5000/video_feed")
    print("Detection : http://127.0.0.1:5000/api/detections")
    print("==============================================")
    print("")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )