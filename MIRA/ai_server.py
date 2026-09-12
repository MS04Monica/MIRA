from flask import Flask, Response, jsonify, send_file
import cv2
from ultralytics import YOLO
import threading
import time

app = Flask(__name__)

VIDEO_URL = "http://192.0.0.4:8080/video"

# Load YOLO
model = YOLO("yolov8n.pt")

# Latest detections
latest_detections = []
lock = threading.Lock()


def generate_frames():
    global latest_detections

    cap = cv2.VideoCapture(VIDEO_URL)

    if not cap.isOpened():
        print("ERROR: Could not connect to phone camera.")
        return

    print("Connected to phone camera.")
    print("YOLO detection started.")
    print("MIRA AI server running at http://127.0.0.1:5000")

    while True:

        success, frame = cap.read()

        if not success:
            print("Camera frame failed.")
            time.sleep(0.5)
            continue

        # YOLO detection
        results = model(frame, verbose=False)

        result = results[0]

        # Draw YOLO boxes
        annotated_frame = result.plot()

        # Collect detection information
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

        with lock:
            latest_detections = detections

        # Convert frame to JPEG
        success, buffer = cv2.imencode(".jpg", annotated_frame)

        if not success:
            continue

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes
            + b"\r\n"
        )

    cap.release()


@app.route("/")
def dashboard():
    return send_file("index.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/detections")
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