# THIS CODE IS FOR THE RASPBERRY PI
from flask import Flask, Response
from ultralytics import YOLO
import cv2
import serial
import threading
import time

app = Flask(__name__)

# -----------------------------
# LOAD MODEL
# -----------------------------
model = YOLO("final_model.pt")

# -----------------------------
# CAMERA
# -----------------------------
cap = cv2.VideoCapture(0)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 20)

# -----------------------------
# GAS DETECTION
# -----------------------------
gas_detected = False
GAS_THRESHOLD = 100

# -----------------------------
# FALL LOGIC
# -----------------------------
fall_start_time = None
fall_already_logged = False
FALL_CONFIRM_SECONDS = 10

# -----------------------------
# EVENT COOLDOWN
# prevents spam logging
# -----------------------------
last_logged_times = {}
EVENT_COOLDOWN = 10


# -----------------------------
# READ ARDUINO
# -----------------------------
def read_arduino():
    global gas_detected

    try:
        ser = serial.Serial("/dev/ttyACM0", 9600, timeout=1)
        time.sleep(2)

        print("Arduino connected")

    except Exception as e:
        print("Could not connect to Arduino:", e)
        return

    while True:

        try:
            value = ser.readline().decode(errors="ignore").strip()

            if value:

                gas_value = int(value)

                gas_detected = gas_value > GAS_THRESHOLD

                print(
                    f"Gas Value: {gas_value} | Gas Detected: {gas_detected}"
                )

        except Exception as e:
            print("Arduino read error:", e)


# -----------------------------
# SAVE LOG + IMAGE
# -----------------------------
def write_log(event_type, frame=None):

    global last_logged_times

    current_time = time.time()

    # cooldown
    if event_type in last_logged_times:

        elapsed = current_time - last_logged_times[event_type]

        if elapsed < EVENT_COOLDOWN:
            return

    last_logged_times[event_type] = current_time

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

    image_path = ""

    # save image
    if frame is not None:

        image_path = f"detected_{event_type}_{timestamp}.jpg"

        cv2.imwrite(image_path, frame)

    # save log
    with open("emergency_logs.txt", "a") as file:

        file.write(
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} - "
            f"Detected: {event_type} - "
            f"Image: {image_path}\n"
        )

    print(f"Logged: {event_type} | Image: {image_path}")


# -----------------------------
# YOLO + STREAM
# -----------------------------
def generate_frames():

    global gas_detected
    global fall_start_time
    global fall_already_logged

    frame_count = 0
    detect_every = 3

    last_annotated_frame = None

    while True:

        success, frame = cap.read()

        if not success:
            break

        frame_count += 1

        detected_labels = []

        # run YOLO every few frames
        if frame_count % detect_every == 0:

            results = model(
                frame,
                verbose=False,
                imgsz=320
            )

            last_annotated_frame = results[0].plot()

            boxes = results[0].boxes
            names = results[0].names

            if boxes is not None:

                for box in boxes:

                    cls_id = int(box.cls[0])

                    label = names[cls_id]

                    detected_labels.append(label)

            # -----------------------------
            # FALL DETECTION (10 sec)
            # -----------------------------
            if "Fall" in detected_labels:

                if fall_start_time is None:

                    fall_start_time = time.time()

                    fall_already_logged = False

                    print("Fall detected. Starting timer...")

                elapsed = time.time() - fall_start_time

                print(f"Fall timer: {elapsed:.1f}s")

                if (
                    elapsed >= FALL_CONFIRM_SECONDS
                    and not fall_already_logged
                ):

                    write_log(
                        "Fall",
                        last_annotated_frame
                    )

                    fall_already_logged = True

            else:

                fall_start_time = None
                fall_already_logged = False

            # -----------------------------
            # GUN
            # -----------------------------
            if "Gun" in detected_labels:

                write_log(
                    "Gun",
                    last_annotated_frame
                )

            # -----------------------------
            # KNIFE
            # -----------------------------
            if "Knife" in detected_labels:

                write_log(
                    "Knife",
                    last_annotated_frame
                )

            # -----------------------------
            # FIRE + GAS
            # -----------------------------
            if (
                "fire" in detected_labels
                and gas_detected
            ):

                write_log(
                    "Fire_Gas_Emergency",
                    last_annotated_frame
                )

        # -----------------------------
        # STREAM FRAME
        # -----------------------------
        if last_annotated_frame is not None:

            annotated_frame = last_annotated_frame

        else:

            annotated_frame = frame

        ret, buffer = cv2.imencode(
            ".jpg",
            annotated_frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 80]
        )

        if not ret:
            continue

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes +
            b"\r\n"
        )


# -----------------------------
# FLASK ROUTE
# -----------------------------
@app.route("/")
def video_feed():

    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":

    threading.Thread(
        target=read_arduino,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=5000
    )