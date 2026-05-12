# Library imports
from flask import Flask, render_template, request, redirect, url_for, flash, Response, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import time
import re
import cv2
from ultralytics import YOLO 
import os
import subprocess
from flask import jsonify

# Create Flask project
app = Flask(__name__)

# Create secret key + Database timeout + Disable modifications on database to maintain storage
app.config["SECRET_KEY"] = "adnfjnwoi4r8y9wfebq9"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///seds.db?check_same_thread=False&timeout=30"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

#Create database "db"
db = SQLAlchemy(app)

# Trained YOLO Model
model = YOLO("final_model.pt")

# keeps session alive
login_manager = LoginManager(app)
# In order to disable anyone from typing the path of the website, used to block unregistered users 
login_manager.login_view = "login"
# Display an error message for user
login_manager.login_message_category = "info"

# Create a folder to store emergency images
UPLOAD_FOLDER = 'static/emergency_pics'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Create User table in database
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    diseases = db.Column(db.String(300), nullable=True)
    number_of_residents = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    logs = db.relationship('EmergencyLog', backref='owner', lazy=True)
    emergency_contact = db.Column(db.String(20), nullable=True)

# Create Emergency Log table in database
class EmergencyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emergency_type = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    image_file = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@app.route("/check_notifications")
@login_required
def check_notifications():
    # Only look for emergencies in the very last 5 seconds
    # This prevents the alert from showing up multiple times for one event
    time_limit = datetime.now(timezone.utc) - timedelta(seconds=5)
    
    new_log = EmergencyLog.query.filter_by(user_id=current_user.id)\
                                .filter(EmergencyLog.timestamp >= time_limit)\
                                .order_by(EmergencyLog.timestamp.desc()).first()

    if new_log:
        return jsonify({
            "alert": True, 
            "message": f"⚠️ EMERGENCY: {new_log.emergency_type} Detected!",
            "type": new_log.emergency_type
        })
    
    return jsonify({"alert": False})

# Checks if the user-id is same for the logged in user
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Function used in the livestream where the camera detects emergency 
# Updated log function
def log_emergency_to_db(user_id, e_type, frame=None):
    with app.app_context():
        try:
            # Check for duplicates within 60 seconds
            time_limit = datetime.now(timezone.utc) - timedelta(seconds=60)
            exists = EmergencyLog.query.filter_by(
                user_id=user_id, 
                emergency_type=e_type
            ).filter(EmergencyLog.timestamp >= time_limit).first()

            if not exists:
                image_filename = None
                if frame is not None:
                    # Create unique filename
                    timestamp_str = datetime.now().strftime("%Y%m%d-%H%M%S")
                    image_filename = f"{e_type}_{user_id}_{timestamp_str}.jpg"
                    
                    # USE ABSOLUTE PATH to ensure it goes to static/emergency_pics
                    basedir = os.path.abspath(os.path.dirname(__file__))
                    filepath = os.path.join(basedir, 'static', 'emergency_pics', image_filename)
                    
                    success = cv2.imwrite(filepath, frame)
                    if success:
                        print(f"✅ DEBUG: Image saved at {filepath}")
                    else:
                        print(f"❌ DEBUG: Failed to save image. Is the folder static/emergency_pics missing?")
                # --- END IMAGE SAVING ---
                    # Save the image

                new_log = EmergencyLog(
                    emergency_type=e_type, 
                    user_id=user_id,
                    image_file=image_filename 
                )
                db.session.add(new_log)
                db.session.commit()
                print(f"DEBUG: {e_type} saved with image:")

        except Exception as e:
            db.session.rollback()
            print(f" DB Error: {e}")

# Updated generate_frames function
def generate_frames(user_id):   
    camera = cv2.VideoCapture(0) 
    while True:
        success, frame = camera.read()
        if not success: break
        
        results = model(frame, conf=0.5)
        # We save the annotated_frame (with boxes) so the user sees exactly what the AI saw
        annotated_frame = results[0].plot() 

        for r in results:
            for box in r.boxes:
                label = model.names[int(box.cls[0])]
                if label in ['fire', 'Gun', 'Knife', 'Fall', 'smoke']:
                    # TRIGGER LOGGING WITH THE ANNOTATED FRAME
                    log_emergency_to_db(user_id, label, annotated_frame)
        
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
# Function that connects camera, model, and website together
def generate_frames(user_id):   
    # Turn on camera
    camera = cv2.VideoCapture(0) 
    # While website is open, keep recording
    while True:
        success, frame = camera.read()
        if not success: break
        results = model(frame, conf=0.5)
        annotated_frame = results[0].plot() 

        for r in results:
            for box in r.boxes:
                label = model.names[int(box.cls[0])]
                if label in ['fire', 'Gun', 'Knife', 'Fall', 'smoke']:
                    log_emergency_to_db(user_id, label, annotated_frame)
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# Function where we sync the logs form pi device which is connected on MAC
def sync_logs_from_pi():
    pi_ip = "192.168.8.190"

    current_dir = os.path.dirname(os.path.abspath(__file__))
    local_log_path = os.path.join(current_dir, "emergency_logs.txt")

    upload_dir = os.path.join(current_dir, "static", "emergency_pics")
    os.makedirs(upload_dir, exist_ok=True)

    remote_log_path = f"pi@{pi_ip}:/home/pi/emergency_logs.txt"

    try:
        # 1) Pull log file from Raspberry Pi
        subprocess.run(["scp", remote_log_path, local_log_path], check=True)

        if not os.path.exists(local_log_path):
            print("No log file found after sync.")
            return

        with open(local_log_path, "r") as file:
            lines = file.readlines()

        print(f"DEBUG: Found {len(lines)} lines in the log file.")

        with app.app_context():
            new_entries = False

            for line in lines:
                clean_line = line.strip()

                if "Detected:" not in clean_line:
                    continue

                # Example:
                # 2026-05-11 18:20:10 - Detected: Fall - Image: detected_Fall_2026-05-11_18-20-10.jpg

                detected_part = clean_line.split("Detected:")[-1].strip()

                if " - Image:" in detected_part:
                    event_type = detected_part.split(" - Image:")[0].strip()
                    image_name = detected_part.split(" - Image:")[-1].strip()
                else:
                    event_type = detected_part.strip()
                    image_name = None

                if event_type not in ["Gun", "Knife", "Fall", "fire", "smoke", "Fire_Gas_Emergency"]:
                    continue

                # avoid duplicate logs within 60 seconds
                time_limit = datetime.now(timezone.utc) - timedelta(seconds=60)
                exists = EmergencyLog.query.filter_by(
                    user_id=current_user.id,
                    emergency_type=event_type
                ).filter(EmergencyLog.timestamp >= time_limit).first()

                if exists:
                    continue

                final_image_name = None

                # 2) Pull image if exists
                if image_name:
                    remote_image_path = f"pi@{pi_ip}:/home/pi/{image_name}"
                    local_image_path = os.path.join(upload_dir, image_name)

                    try:
                        subprocess.run(
                            ["scp", remote_image_path, local_image_path],
                            check=True
                        )
                        final_image_name = image_name
                        print(f"DEBUG: Image copied: {image_name}")

                    except Exception as img_error:
                        print(f"DEBUG: Could not copy image {image_name}: {img_error}")

                new_log = EmergencyLog(
                    emergency_type=event_type,
                    user_id=current_user.id,
                    image_file=final_image_name
                )

                db.session.add(new_log)
                new_entries = True

                print(f"DEBUG: Added {event_type} with image {final_image_name}")

            if new_entries:
                db.session.commit()
                print("Database successfully updated with new logs.")
            else:
                print("No NEW unique detections found in this sync.")

        # 3) Clear Pi log file after successful sync
        subprocess.run(
            ["ssh", f"pi@{pi_ip}", "truncate -s 0 /home/pi/emergency_logs.txt"],
            check=True
        )

    except Exception as e:
        print(f"Sync Error: {e}")
# Clears logs from more than 7 days
def cleanup_old_logs():
    limit = datetime.utcnow() - timedelta(days=7)
    with app.app_context():
        EmergencyLog.query.filter(EmergencyLog.timestamp < limit).delete()
        db.session.commit()
        print("Old logs deleted to save space.")

# ---- ROUTES ----
# Login Route
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("home"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")

# Register Route
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if len(password) < 8:
            flash("Password must be longer than 8 characters", "danger")
            return redirect(url_for("register"))

        email_regex = r'^[a-zA-A0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            flash("Please enter a valid email address", "danger")
            return redirect(url_for("register"))
        
        domain = email.split('@')[-1]
        if len(domain.split('.')[0]) < 2:
            flash("This email looks invalid", "danger")
            return redirect(url_for("register"))
        
        emergency_contact = request.form.get("emergency_contact")
        if not emergency_contact.isdigit():
            flash("Emergency contact must contain only numbers!", "danger")

        birth_date_str = request.form.get("age")
        try:
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d')
            today = datetime.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except (ValueError, TypeError):
            age = 0 

        selected_diseases = request.form.getlist("diseases")
        other_text = request.form.get("diseases_other").strip
        if "None" in selected_diseases or not selected_diseases:
            final_diseases = "None"
        else:
            if "Other" in selected_diseases and not other_text:
                flash("Please specify your other medical conditions", "danger")
                return redirect(url_for("register"))
            temp_list = []
            for d in selected_diseases:
                if d == "Other":
                    temp_list.append(other_text)
                else:
                    temp_list.append(d)
                    final_diseases = ", ".join(temp_list)
        raw_residents = request.form.get("number_of_residents", 1)
        number_of_residents = max(1, int(raw_residents) if str(raw_residents).isdigit() else 1)        
        location = request.form["location"]

        if User.query.filter_by(email=email).first():
            flash("Email already exists!", "danger")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        
        user = User(
            full_name=full_name,
            email=email,
            password=hashed_pw,
            age=age,
            diseases=final_diseases,
            number_of_residents=number_of_residents,
            location=location,
            emergency_contact=emergency_contact
        )
        db.session.add(user)
        db.session.commit()
        
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# Logout Route
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

# Home Route
@app.route("/")
def home():
    total_users = User.query.count() 
    total_emergencies = EmergencyLog.query.count()
    if hasattr(g,'start'):
        current_latency = round((time.time() - g.start) * 100,2)
    else:
        current_latency = 0

    return render_template("index.html", 
                           total_users=total_users, total_emergencies=EmergencyLog.query.count(), latency=current_latency)

# Profile (Dashboard) Route
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)

# Edit Profile Route
@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.full_name = request.form["full_name"]
        current_user.age = int(request.form["age"])
        res_input = request.form.get("number_of_residents", 1)
        current_user.number_of_residents = max(1, int(res_input) if str(res_input).lstrip('-').isdigit() else 1)
        current_user.location = request.form["location"]
        current_user.emergency_contact = request.form["emergency_contact"]
        emergency_contact = request.form.get("emergency_contact")
        if emergency_contact and not emergency_contact.isdigit():
            flash("Emergency contact must contain only numbers!", "danger")
        selected_diseases = request.form.getlist("diseases")
        other_text = request.form.get("diseases_other").strip()

        if "None" in selected_diseases:
            current_user.diseases = "None"
        else:
            if "Other" in selected_diseases and not other_text:
                flash("Please specify your 'Other' medical condition", "danger")
                return render_template("edit_profile.html", user=current_user)

            final_list = []
            for d in selected_diseases:
                if d == "Other":
                    final_list.append(other_text)
                else:
                    final_list.append(d)
            
            current_user.diseases = ", ".join(final_list) if final_list else "None"

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_profile.html", user=current_user)

# Livestream Route   
@app.route("/livestream")
@login_required
def live_stream():
    return render_template("livestream.html")

# Video feed Route
@app.route("/video_feed")
@login_required
def video_feed():
    return Response(generate_frames(current_user.id), mimetype='multipart/x-mixed-replace; boundary=frame')

# Emergency Log Route
@app.route("/emergency_log")
@login_required
def emergency_log():
    sync_logs_from_pi()
    db.session.expire_all()
    logs = EmergencyLog.query.filter_by(user_id=current_user.id).order_by(EmergencyLog.timestamp.desc()).all()
    return render_template("emergency_log.html", logs=logs)

# Clear Logs Route
@app.route("/clear_logs")
@login_required
def clear_logs():
    EmergencyLog.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return redirect(url_for("emergency_log"))

# Route to start counting time from when the user entered the system 
@app.before_request
def start_timer():
    g.start = time.time()

# Route to calculate latency
@app.after_request
def log_latency(response):
    if hasattr(g, 'start'):
        latency = time.time() - g.start
        response.headers["X-Response-Time"] = str(latency)
    return response

# Builder and Start 
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)