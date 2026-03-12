from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime

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
        age = int(request.form["age"])
        diseases = request.form["diseases"]
        number_of_residents = int(request.form["number_of_residents"])
        location = request.form["location"]

        if User.query.filter_by(email=email).first():
            return "Email already exists!"

        user = User(
            full_name=full_name,
            email=email,
            password=password,
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

        user = User.query.filter_by(email=email, password=password).first()
        if not user:
            return "Wrong email or password!"

        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


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
    return redirect(url_for("home"))


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
        db.drop_all()
        db.create_all()

    app.run(debug=True)