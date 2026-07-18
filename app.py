import os
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-to-something-random")

# ---- Database config ----
# On Render, set DATABASE_URL as an environment variable (Render gives you
# this automatically when you create a Postgres database and link it).
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/login_app"
)


def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
    return conn


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session or session.get("role") != "admin":
            flash("Admin access only.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM users WHERE username=%s OR email=%s",
                    (username, email),
                )
                if cur.fetchone():
                    flash("Username or email already registered.")
                    return redirect(url_for("register"))

                cur.execute(
                    """INSERT INTO users (username, email, password, role, status)
                       VALUES (%s, %s, %s, 'user', 'pending')""",
                    (username, email, hashed_password),
                )
                conn.commit()
        finally:
            conn.close()

        flash("Registration submitted. An admin must approve your account before you can log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username=%s", (username,))
                user = cur.fetchone()
        finally:
            conn.close()

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid username or password.")
            return redirect(url_for("login"))

        if user["status"] == "pending":
            flash("Your account is awaiting admin approval.")
            return redirect(url_for("login"))

        if user["status"] == "rejected":
            flash("Your registration was rejected. Contact the admin.")
            return redirect(url_for("login"))

        # approved
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session["username"])


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---- Admin routes ----

@app.route("/admin")
@admin_required
def admin_panel():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, status FROM users WHERE role != 'admin' ORDER BY created_at DESC"
            )
            users = cur.fetchall()
    finally:
        conn.close()
    return render_template("admin.html", users=users)


@app.route("/admin/approve/<int:user_id>", methods=["POST"])
@admin_required
def approve_user(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET status='approved' WHERE id=%s", (user_id,))
            conn.commit()
    finally:
        conn.close()
    flash("User approved.")
    return redirect(url_for("admin_panel"))


@app.route("/admin/reject/<int:user_id>", methods=["POST"])
@admin_required
def reject_user(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET status='rejected' WHERE id=%s", (user_id,))
            conn.commit()
    finally:
        conn.close()
    flash("User rejected.")
    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    app.run(debug=True)
