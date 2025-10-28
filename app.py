from flask import Flask, Response, render_template, request, jsonify
import io, os, json, time, threading, serial, platform

app = Flask(__name__)
armed = False
# -------------------------
# Arduino serial setup
# -------------------------
try:
    if os.name == "nt":
        arduino = serial.Serial("COM10", 250000, timeout=1)
    else:
        arduino = serial.Serial("/dev/serial0", 250000, timeout=1)
    time.sleep(2)
    arduino.reset_input_buffer()
    print("✅ Arduino connected")
except Exception as e:
    print("❌ Arduino connection failed:", e)
    arduino = None


# -------------------------
# Camera setup (Auto detect)
# -------------------------
use_picamera2 = False
picam2 = None
camera = None

try:
    # Only try on Raspberry Pi
    if "arm" in platform.machine().lower():
        from picamera2 import Picamera2
        from libcamera import Transform
        picam2 = Picamera2()
        config = picam2.create_video_configuration(
            main={"size": (320, 240)},
            transform=Transform(hflip=1, vflip=1)
        )
        picam2.configure(config)
        picam2.start()
        time.sleep(2)
        use_picamera2 = True
        print("📷 Using PiCamera2")
except Exception as e:
    print("⚠️ PiCamera2 not available:", e)
    use_picamera2 = False

if not use_picamera2:
    try:
        import cv2
        camera = cv2.VideoCapture(0)
        print("💻 Using OpenCV webcam")
    except Exception as e:
        print("❌ OpenCV camera error:", e)
        camera = None


# -------------------------
# Frame generator
# -------------------------
def generate_frames():
    if use_picamera2 and picam2:
        while True:
            stream = io.BytesIO()
            picam2.capture_file(stream, format="jpeg")
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + stream.getvalue() + b'\r\n')
    elif camera:
        import cv2
        while True:
            success, frame = camera.read()
            if not success:
                continue
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    else:
        # fallback placeholder if no camera found
        from PIL import Image
        img = Image.new("RGB", (320, 240), (100, 100, 100))
        while True:
            stream = io.BytesIO()
            img.save(stream, format="JPEG")
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + stream.getvalue() + b'\r\n')


# -------------------------
# Flask routes
# -------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/filo')
def filo():
    return render_template('filo.html')

# -------------------------
# Joystick state cache
# -------------------------
joystick_state = {
    "roll": 0.0,
    "pitch": 0.0,
    "yaw": 0.0,
    "throttle": -1.0  # Start at lowest position
}

@app.route('/joystick', methods=['POST'])
def joystick():
    global joystick_state, armed
    try:
        if not armed:
            return jsonify({"status": "error", "message": "Motors are disarmed"}), 403

        data = request.get_json(force=True)

        # Update state
        for key in data:
            if key in joystick_state:
                joystick_state[key] = float(data[key])

        # Apply conversions
        roll = joystick_state["roll"] * 45
        pitch = joystick_state["pitch"] * 45
        yaw = joystick_state["yaw"] * 45
        throttle_input = -joystick_state["throttle"]
        throttle = 1000 + ((throttle_input + 1) * 500)

        print(
            f"🎮 Joystick | ROLL={roll:+.2f}° | PITCH={pitch:+.2f}° | "
            f"YAW={yaw:+.2f}° | THROTTLE(raw)={throttle_input:+.2f} → {throttle:.0f} μs"
        )

        if arduino:
            command = f"CMD,{roll:.2f},{pitch:.2f},{throttle:.0f},{yaw:.2f}\n"
            arduino.write(command.encode("utf-8"))

        return jsonify({"status": "ok", "sent": {"roll": roll, "pitch": pitch, "yaw": yaw, "throttle": throttle}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/arm', methods=['POST'])
def arm():
    global armed
    armed = True
    if arduino:
        arduino.write(b"a\n")  # Sends 'a' command to Arduino
    return jsonify({"status": "ok", "message": "Motors ARMED"})

@app.route('/disarm', methods=['POST'])
def disarm():
    global armed
    armed = False
    if arduino:
        arduino.write(b"d\n")  # Sends 'd' command to Arduino
    return jsonify({"status": "ok", "message": "Motors DISARMED"})



# 🧠 Background thread to read serial data
def read_from_arduino():
    if not arduino:
        return
    while True:
        try:
            raw_line = arduino.readline()
            if raw_line:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if line:
                    if line.startswith("ACK,"):
                        print(f"✅ Received ACK: {line}")
                    elif line.startswith("R:"):
                        print(f"📡 Telemetry: {line}")
                    else:
                        print(f"⚠️ Unknown line: {line}")
        except Exception as e:
            print("⚠️ Serial read error:", e)
            break
        time.sleep(0.05)



# Start background thread
if arduino:
    thread = threading.Thread(target=read_from_arduino, daemon=True)
    thread.start()



@app.route('/run', methods=['POST'])
def run_program():
    try:
        program = request.json
        print("📦 Blockly program:", program)
        if arduino:
            command = json.dumps(program) + "\n"
            arduino.write(command.encode("utf-8"))
        return jsonify({"status": "ok", "sent": program})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# -------------------------
# Run Flask app
# -------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
