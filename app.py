import os
import re
import secrets
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-to-something-random")

# ---- Database config ----
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/login_app"
)

# ---- Google OAuth config ----
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)


def init_db():
    """Create/upgrade the users table, and seed an admin account from
    environment variables if one isn't there yet. Runs on startup --
    no Shell access required."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    email VARCHAR(100) NOT NULL UNIQUE,
                    password VARCHAR(255),
                    role VARCHAR(20) NOT NULL DEFAULT 'user',
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    unique_id VARCHAR(20) UNIQUE,
                    google_id VARCHAR(255) UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # Upgrade columns for tables created before this version existed.
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS unique_id VARCHAR(20) UNIQUE;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE;")
            cur.execute("ALTER TABLE users ALTER COLUMN password DROP NOT NULL;")
            conn.commit()

            # Backfill unique_id for any existing rows that don't have one yet.
            cur.execute("SELECT id FROM users WHERE unique_id IS NULL;")
            for row in cur.fetchall():
                cur.execute(
                    "UPDATE users SET unique_id=%s WHERE id=%s",
                    (f"REG{row['id']:06d}", row["id"]),
                )
            conn.commit()

            admin_username = os.environ.get("ADMIN_USERNAME")
            admin_email = os.environ.get("ADMIN_EMAIL")
            admin_password = os.environ.get("ADMIN_PASSWORD")

            if admin_username and admin_email and admin_password:
                cur.execute("SELECT id FROM users WHERE username=%s", (admin_username,))
                if not cur.fetchone():
                    cur.execute(
                        """INSERT INTO users (username, email, password, role, status)
                           VALUES (%s, %s, %s, 'admin', 'approved') RETURNING id""",
                        (admin_username, admin_email, generate_password_hash(admin_password)),
                    )
                    new_id = cur.fetchone()["id"]
                    cur.execute(
                        "UPDATE users SET unique_id=%s WHERE id=%s",
                        (f"REG{new_id:06d}", new_id),
                    )
                    conn.commit()
                    print(f"Admin user '{admin_username}' created.")
    finally:
        conn.close()


init_db()


def is_strong_password(password):
    """Require at least 8 characters, one uppercase, one lowercase,
    one digit, and one special character."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must include at least one number."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-\[\]\\/~`+=;']", password):
        return False, "Password must include at least one special character."
    return True, ""


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


def log_user_in(user):
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]


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

        strong, message = is_strong_password(password)
        if not strong:
            flash(message)
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE username=%s", (username,))
                if cur.fetchone():
                    flash("That username is already taken. Please choose another.")
                    return redirect(url_for("register"))

                cur.execute("SELECT id FROM users WHERE email=%s", (email,))
                if cur.fetchone():
                    flash("That email is already registered. Please log in instead.")
                    return redirect(url_for("register"))

                cur.execute(
                    """INSERT INTO users (username, email, password, role, status)
                       VALUES (%s, %s, %s, 'user', 'pending') RETURNING id""",
                    (username, email, hashed_password),
                )
                new_id = cur.fetchone()["id"]
                unique_id = f"REG{new_id:06d}"
                cur.execute("UPDATE users SET unique_id=%s WHERE id=%s", (unique_id, new_id))
                conn.commit()
        finally:
            conn.close()

        flash(f"Registration submitted! Your Registration ID is {unique_id} -- please save it. "
              f"An admin must approve your account before you can log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM users WHERE username=%s OR email=%s",
                    (identifier, identifier),
                )
                user = cur.fetchone()
        finally:
            conn.close()

        if not user or not user["password"] or not check_password_hash(user["password"], password):
            flash("Invalid username/email or password.")
            return redirect(url_for("login"))

        if user["status"] == "pending":
            flash("Your account is awaiting admin approval.")
            return redirect(url_for("login"))

        if user["status"] == "rejected":
            flash("Your registration was rejected. Contact the admin.")
            return redirect(url_for("login"))

        log_user_in(user)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


# ---- Google login ----

@app.route("/login/google")
def login_google():
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/login/google/callback")
def google_callback():
    token = google.authorize_access_token()
    user_info = token.get("userinfo")
    google_id = user_info["sub"]
    email = user_info["email"]
    display_name = user_info.get("name", email.split("@")[0])

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE google_id=%s OR email=%s", (google_id, email)
            )
            user = cur.fetchone()

            if not user:
                # brand new signup via Google
                base_username = re.sub(r"[^a-zA-Z0-9]", "", display_name).lower() or "user"
                username = base_username
                suffix = 0
                while True:
                    cur.execute("SELECT id FROM users WHERE username=%s", (username,))
                    if not cur.fetchone():
                        break
                    suffix += 1
                    username = f"{base_username}{suffix}"

                cur.execute(
                    """INSERT INTO users (username, email, password, role, status, google_id)
                       VALUES (%s, %s, NULL, 'user', 'pending', %s) RETURNING id""",
                    (username, email, google_id),
                )
                new_id = cur.fetchone()["id"]
                unique_id = f"REG{new_id:06d}"
                cur.execute("UPDATE users SET unique_id=%s WHERE id=%s", (unique_id, new_id))
                conn.commit()
                flash(f"Registered via Google! Your Registration ID is {unique_id}. "
                      f"An admin must approve your account before you can log in.")
                return redirect(url_for("login"))

            if user["status"] == "pending":
                flash("Your account is awaiting admin approval.")
                return redirect(url_for("login"))
            if user["status"] == "rejected":
                flash("Your registration was rejected. Contact the admin.")
                return redirect(url_for("login"))

            log_user_in(user)
            return redirect(url_for("dashboard"))
    finally:
        conn.close()


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
                """SELECT id, unique_id, username, email, status FROM users
                   WHERE role != 'admin' ORDER BY created_at DESC"""
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
    
