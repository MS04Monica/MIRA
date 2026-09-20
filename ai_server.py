from flask import Flask, Response, jsonify, render_template
import cv2
from ultralytics import YOLO
import threading
import time
import os

app = Flask(__name__)

# Read camera stream URL from environment variable
VIDEO_URL = os.getenv("CAMERA_STREAM_URL", "http://192.0.0.4:8080/video")

# Lazy-load YOLO model to speed up server boot on Render
model = None

latest_detections = []
latest_frame = None
lock = threading.Lock()
thread_started = False

def process_camera_stream():
    global latest_detections, latest_frame, model
    
    # Load YOLO inside thread to prevent worker boot timeouts
    if model is None:
        model = YOLO("yolov8n.pt")

    cap = None

    while True:
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(VIDEO_URL)

            if not cap.isOpened():
                time.sleep(5)  # Wait longer between retries to save CPU
                continue

        success, frame = cap.read()

        if not success:
            cap.release()
            cap = None
            time.sleep(2)
            continue

        frame = cv2.resize(frame, (640, 480))
        results = model(frame, verbose=False, conf=0.40)
        result = results[0]
        annotated_frame = result.plot()

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

        success, buffer = cv2.imencode(".jpg", annotated_frame)
        if success:
            encoded_bytes = buffer.tobytes()
            with lock:
                latest_detections = detections
                latest_frame = encoded_bytes

        time.sleep(0.03)

def start_background_thread():
    global thread_started
    if not thread_started:
        thread = threading.Thread(target=process_camera_stream, daemon=True)
        thread.start()
        thread_started = True

# Start background worker when Flask starts
start_background_thread()

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
        time.sleep(0.04)

# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def dashboard():
    return render_template("index.html")

@app.route("/analytics")
def analytics():
    return render_template("analytics.html")

@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/api/detections")
@app.route("/detections")
def detections():
    with lock:
        data = list(latest_detections)

    return jsonify({
        "count": len(data),
        "detections": data
    })

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )