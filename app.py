from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Response
from datetime import datetime, date

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-later"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///seds.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    diseases = db.Column(db.String(300), nullable=True)
    number_of_residents = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(200), nullable=False)

    emergency_logs = db.relationship("EmergencyLog", backref="user", lazy=True)


class EmergencyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emergency_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Pending")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    video_path = db.Column(db.String(300), nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)
        
        # Get the birthdate from the form
        birthdate_str = request.form["age"]  # still 'age' in HTML
        birthdate = datetime.strptime(birthdate_str, "%Y-%m-%d").date()
        
        # Calculate age
        today = date.today()
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        
        # Handle diseases
        disease_selected = request.form.get("diseases")
        disease_other = request.form.get("diseases_other")
        if disease_selected == "Other":
            diseases = disease_other
        else:
            diseases = disease_selected
        
        # Always get these
        number_of_residents = int(request.form["number_of_residents"])
        location = request.form["location"]

        # Check if email exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            error_message = "Email already exists. Please use another email."
            return render_template("register.html", error=error_message)

        # Create new user
        user = User(
            full_name=full_name,
            email=email,
            password=hashed_password,
            age=age,
            diseases=diseases,
            number_of_residents=number_of_residents,
            location=location
        )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            return render_template("login.html", error="Wrong email or password!")
        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@app.route("/live-stream")
@login_required
def live_stream():
    return render_template("livestream.html")


def generate_frames():
    # WHEN CAMERA IS CONNECTED CHANGE THIS WITH I THE CODE
    while True:
        # no camera yet → just break
        break

@app.route('/video-feed')
@login_required
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/dashboard")
@login_required
def dashboard():

    last_emergency = EmergencyLog.query.filter_by(
        user_id=current_user.id
    ).order_by(EmergencyLog.timestamp.desc()).first()

    return render_template(
        "dashboard.html",
        user=current_user,
        last_emergency=last_emergency
    )


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/emergency-log")
@login_required
def emergency_log():
    logs = EmergencyLog.query.filter_by(user_id=current_user.id).order_by(EmergencyLog.timestamp.desc()).all()
    return render_template("emergency_log.html", logs=logs)


@app.route("/add-test-emergency/<emergency_type>")
@login_required
def add_test_emergency(emergency_type):
    if emergency_type.lower() not in ["fire", "fall"]:
        return "Invalid emergency type!"

    new_log = EmergencyLog(
        emergency_type=emergency_type.capitalize(),
        status="Pending",
        user_id=current_user.id
    )

    db.session.add(new_log)
    db.session.commit()

    return redirect(url_for("emergency_log"))


# API يستقبل تنبيه من نموذج الذكاء الاصطناعي
@app.route("/api/emergency", methods=["POST"])
def api_emergency():

    data = request.json
    emergency_type = data.get("type")

    if emergency_type not in ["Fire", "Fall"]:
        return {"error": "Invalid emergency type"}, 400

    new_log = EmergencyLog(
        emergency_type=emergency_type,
        status="Pending",
        user_id=1
    )

    db.session.add(new_log)
    db.session.commit()

    return {"message": "Emergency recorded"}, 200


if __name__ == "__main__":
    with app.app_context():
        #db.drop_all() --------- this line deletes logs and database content
        db.create_all()

    app.run(debug=True)