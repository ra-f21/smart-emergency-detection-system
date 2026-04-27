from flask import Flask, render_template, request, redirect, url_for, flash, Response, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import time
import re
import cv2  # Import OpenCV
from ultralytics import YOLO # Import YOLO

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-later-but-keep-it-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///seds.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- LOAD YOUR TRAINED MODEL ---
# Make sure best.pt is in the same folder as app.py
model = YOLO("best.pt")

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"

# --- LATENCY TRACKING LOGIC ---
@app.before_request
def start_timer():
    g.start = time.time()

@app.after_request
def log_latency(response):
    if hasattr(g, 'start'):
        latency = time.time() - g.start
        # We store the latest latency in a header or just pass it to templates
        response.headers["X-Response-Time"] = str(latency)
    return response


# --- MODELS ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    diseases = db.Column(db.String(300), nullable=True)
    number_of_residents = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    # Relationship to logs
    logs = db.relationship('EmergencyLog', backref='owner', lazy=True)

class EmergencyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emergency_type = db.Column(db.String(50)) # e.g., 'Fire', 'Fall'
    status = db.Column(db.String(50), default='Unresolved')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- DETECTION LOGIC WITH COOLDOWN ---
# This dictionary prevents spamming the database
# It stores the last time a specific event was logged for a user
last_logged_event = {}

def log_emergency_to_db(user_id, e_type):
    now = datetime.now()
    key = f"{user_id}_{e_type}"
    
    if key not in last_logged_event or (now - last_logged_event[key]) > timedelta(seconds=10):
        # We MUST use the app_context to talk to the database from the generator
        with app.app_context(): 
            try:
                new_log = EmergencyLog(emergency_type=e_type, user_id=user_id, status="Active")
                db.session.add(new_log)
                db.session.commit()
                last_logged_event[key] = now
                print(f"✅ SUCCESS: Logged {e_type} to database!")
            except Exception as e:
                print(f"❌ DATABASE ERROR: {e}")

# --- CAMERA / YOLO GENERATOR ---
def generate_frames(user_id):
    camera = cv2.VideoCapture(0) 
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            results = model(frame, conf=0.5)
            for r in results:
                for box in r.boxes:
                    label = model.names[int(box.cls[0])]
                    if label in ['fire', 'Gun', 'Knife', 'Fall', 'smoke']:
                        log_type = "Weapon" if label in ["Gun", "Knife"] else label
                        log_emergency_to_db(user_id, log_type)

            ret, buffer = cv2.imencode('.jpg', results[0].plot())
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- ROUTES ---

@app.route("/")
def home():
    total_users = User.query.count()  #actual user count
    total_emergencies = EmergencyLog.query.count()  #actual emergency log number
    if hasattr(g,'start'):
        current_latency = round((time.time() - g.start) * 100,2)
    else:
        current_latency = 0

    return render_template("index.html", 
                           total_users=total_users, total_emergencies=total_emergencies, latency=current_latency)


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

        # --- FIX FOR THE DATE/AGE ERROR ---
        birth_date_str = request.form.get("age") # This is getting '2017-06-13'
        try:
            # Convert string to date object
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d')
            # Calculate age
            today = datetime.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except (ValueError, TypeError):
            # Fallback if the date is missing or wrong format
            age = 0 
        # ----------------------------------

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
        number_of_residents = int(request.form.get("number_of_residents", 1))
        location = request.form["location"]

        if User.query.filter_by(email=email).first():
            flash("Email already exists!", "danger") # This sends the notification
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        
        user = User(
            full_name=full_name,
            email=email,
            password=hashed_pw,
            age=age,
            diseases=final_diseases,
            number_of_residents=number_of_residents,
            location=location
        )
        db.session.add(user)
        db.session.commit()
        
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    # Only displays information
    return render_template("dashboard.html", user=current_user)

@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.full_name = request.form["full_name"]
        current_user.age = int(request.form["age"])
        current_user.number_of_residents = int(request.form["number_of_residents"])
        current_user.location = request.form["location"]

        selected_diseases = request.form.getlist("diseases")
        other_text = request.form.get("diseases_other").strip()

        # 1. If "None" is in the list, we just save "None"
        if "None" in selected_diseases:
            current_user.diseases = "None"
        else:
            # 2. Handle "Other" validation
            if "Other" in selected_diseases and not other_text:
                flash("Please specify your 'Other' medical condition", "danger")
                return render_template("edit_profile.html", user=current_user)

            # 3. Combine choices
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

@app.route("/emergency_log")
@login_required
def emergency_log():
    # Fetch logs only for the logged-in user, ordered by newest first
    logs = EmergencyLog.query.filter_by(user_id=current_user.id).order_by(EmergencyLog.timestamp.desc()).all()
    return render_template("emergency_log.html", logs=logs)

@app.route("/livestream")
@login_required
def live_stream():
    return render_template("livestream.html")

@app.route("/video_feed")
@login_required
def video_feed():
    return Response(generate_frames(current_user.id), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)