from flask import Flask, Response, jsonify, send_file
import cv2
from ultralytics import YOLO
import threading
import time

app = Flask(__name__)

# ============================================================
# ONEPLUS 11R IP WEBCAM
# ============================================================

VIDEO_URL = "http://192.0.0.4:8080/video"

# ============================================================
# YOLO MODEL
# ============================================================

model = YOLO("yolov8n.pt")

# ============================================================
# LATEST DETECTIONS
# ============================================================

latest_detections = []
lock = threading.Lock()


# ============================================================
# VIDEO + YOLO PROCESSING
# ============================================================

def generate_frames():

    global latest_detections

    cap = None

    while True:

        # ----------------------------------------------------
        # Connect to phone camera
        # ----------------------------------------------------

        if cap is None or not cap.isOpened():

            print("Connecting to OnePlus 11R camera...")

            cap = cv2.VideoCapture(VIDEO_URL)

            if not cap.isOpened():

                print("ERROR: Could not connect to phone camera.")
                time.sleep(2)
                continue

            print("Connected to OnePlus 11R.")
            print("YOLO detection started.")

        # ----------------------------------------------------
        # Read frame
        # ----------------------------------------------------

        success, frame = cap.read()

        if not success:

            print("Camera frame failed. Reconnecting...")

            cap.release()
            cap = None

            time.sleep(1)
            continue

        # ----------------------------------------------------
        # YOLO inference
        # ----------------------------------------------------

        results = model(
            frame,
            verbose=False,
            conf=0.40
        )

        result = results[0]

        # ----------------------------------------------------
        # Draw detections
        # ----------------------------------------------------

        annotated_frame = result.plot()

        # ----------------------------------------------------
        # Collect detection information
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Save latest detection data
        # ----------------------------------------------------

        with lock:

            latest_detections = detections

        # ----------------------------------------------------
        # Convert frame to JPEG
        # ----------------------------------------------------

        success, buffer = cv2.imencode(
            ".jpg",
            annotated_frame
        )

        if not success:
            continue

        frame_bytes = buffer.tobytes()

        # ----------------------------------------------------
        # MJPEG stream
        # ----------------------------------------------------

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes
            + b"\r\n"
        )

    if cap is not None:
        cap.release()


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
def dashboard():

    return send_file("index.html")


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
# ============================================================

@app.route("/api/detections")
def detections():

    with lock:

        data = list(latest_detections)

    return jsonify({
        "count": len(data),
        "detections": data
    })


# ============================================================
# SERVER
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