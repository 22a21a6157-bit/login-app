import os
import re
import requests
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

# ---- Google OAuth config (optional) ----
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_LOGIN_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

oauth = OAuth(app)
google = None
if GOOGLE_LOGIN_ENABLED:
    google = oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@app.context_processor
def inject_google_flag():
    return {"google_login_enabled": GOOGLE_LOGIN_ENABLED}


# ---- Email (OTP) config -- using Brevo's HTTPS email API ----
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL")
MAIL_ENABLED = bool(BREVO_API_KEY and BREVO_SENDER_EMAIL)


def send_email(to_email, subject, body):
    if not MAIL_ENABLED:
        print(f"[MAIL DISABLED] Would send to {to_email}: {subject}\n{body}")
        return False
    try:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": BREVO_API_KEY,
                "content-type": "application/json",
            },
            json={
                "sender": {"email": BREVO_SENDER_EMAIL, "name": "Login App"},
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": body,
            },
            timeout=10,
        )
        if response.status_code in (200, 201):
            return True
        print(f"Email send failed: {response.status_code} {response.text}")
        return False
    except Exception as e:
        print(f"Email send failed: {e}")
        return False


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
                    referred_by VARCHAR(20),
                    reset_status VARCHAR(20) NOT NULL DEFAULT 'none',
                    phone VARCHAR(20),
                    address VARCHAR(255),
                    otp_code VARCHAR(10),
                    otp_expiry TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # Upgrade columns for tables created before this version existed.
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS unique_id VARCHAR(20) UNIQUE;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by VARCHAR(20);")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_code VARCHAR(10);")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_expiry TIMESTAMP;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_status VARCHAR(20) NOT NULL DEFAULT 'none';")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS address VARCHAR(255);")
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
    session["unique_id"] = user["unique_id"]


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
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        ref_code = request.form.get("ref", "").strip().upper()

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

                # Validate referral code, if any -- must match an existing user's unique_id.
                referred_by = None
                if ref_code:
                    cur.execute("SELECT unique_id FROM users WHERE unique_id=%s", (ref_code,))
                    ref_row = cur.fetchone()
                    if ref_row:
                        referred_by = ref_row["unique_id"]

                cur.execute(
                    """INSERT INTO users (username, email, password, role, status, referred_by, phone, address)
                       VALUES (%s, %s, %s, 'user', 'pending', %s, %s, %s) RETURNING id""",
                    (username, email, hashed_password, referred_by, phone or None, address or None),
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

    ref_code = request.args.get("ref", "")
    return render_template("register.html", ref_code=ref_code)


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


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM users WHERE username=%s OR email=%s",
                    (identifier, identifier),
                )
                user = cur.fetchone()

                if not user or user["status"] != "approved":
                    flash("If that account exists and is approved, a reset request has been submitted.")
                    return redirect(url_for("forgot_password"))

                # Don't clobber an already-approved reset with a fresh 'pending'.
                if user["reset_status"] != "approved":
                    cur.execute(
                        "UPDATE users SET reset_status='pending' WHERE id=%s", (user["id"],)
                    )
                    conn.commit()
        finally:
            conn.close()

        flash("Your password reset request has been submitted.")
        return redirect(url_for("reset_password", identifier=identifier))

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    # Accept the identifier from the URL (works even if the browser/session
    # was closed while waiting for admin approval) or fall back to a form
    # field on this same page for re-entry.
    identifier = request.args.get("identifier") or request.form.get("identifier")

    if not identifier:
        return render_template("reset_password.html", need_identifier=True)

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

    if not user:
        flash("No account found with that username/email.")
        return render_template("reset_password.html", need_identifier=True)

    if user["reset_status"] == "pending":
        return render_template(
            "reset_password.html", awaiting_approval=True, identifier=identifier
        )

    if user["reset_status"] != "approved":
        flash("No pending or approved reset request found for that account. Please request again.")
        return redirect(url_for("forgot_password"))

    # reset_status == 'approved' -- admin has cleared this user to set a new password
    if request.method == "POST" and request.form.get("password"):
        new_password = request.form.get("password", "")

        strong, message = is_strong_password(new_password)
        if not strong:
            flash(message)
            return render_template(
                "reset_password.html", awaiting_approval=False, identifier=identifier
            )

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET password=%s, reset_status='none' WHERE id=%s",
                    (generate_password_hash(new_password), user["id"]),
                )
                conn.commit()
        finally:
            conn.close()

        flash("Password reset successfully. Please log in.")
        return redirect(url_for("login"))

    return render_template(
        "reset_password.html", awaiting_approval=False, identifier=identifier
    )


# ---- Google login ----

@app.route("/login/google")
def login_google():
    if not GOOGLE_LOGIN_ENABLED:
        flash("Google Sign-In is not set up on this app.")
        return redirect(url_for("login"))
    ref_code = request.args.get("ref", "").strip().upper()
    if ref_code:
        session["pending_ref"] = ref_code
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/login/google/callback")
def google_callback():
    if not GOOGLE_LOGIN_ENABLED:
        return redirect(url_for("login"))
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
                # Brand new signup via Google -- don't create the account yet.
                # Stash their Google info and send them to a form to fill in
                # the remaining details (username, phone, address, password).
                suggested_username = re.sub(r"[^a-zA-Z0-9]", "", display_name).lower() or "user"
                session["google_pending"] = {
                    "google_id": google_id,
                    "email": email,
                    "name": display_name,
                    "suggested_username": suggested_username,
                }
                return redirect(url_for("complete_google_profile"))

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


@app.route("/complete-google-profile", methods=["GET", "POST"])
def complete_google_profile():
    pending = session.get("google_pending")
    if not pending:
        flash("Please sign in with Google first.")
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("complete_google_profile"))

        strong, message = is_strong_password(password)
        if not strong:
            flash(message)
            return redirect(url_for("complete_google_profile"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE username=%s", (username,))
                if cur.fetchone():
                    flash("That username is already taken. Please choose another.")
                    return redirect(url_for("complete_google_profile"))

                referred_by = None
                ref_code = session.pop("pending_ref", None)
                if ref_code:
                    cur.execute("SELECT unique_id FROM users WHERE unique_id=%s", (ref_code,))
                    ref_row = cur.fetchone()
                    if ref_row:
                        referred_by = ref_row["unique_id"]

                cur.execute(
                    """INSERT INTO users (username, email, password, role, status,
                                           google_id, referred_by, phone, address)
                       VALUES (%s, %s, %s, 'user', 'pending', %s, %s, %s, %s) RETURNING id""",
                    (
                        username,
                        pending["email"],
                        generate_password_hash(password),
                        pending["google_id"],
                        referred_by,
                        phone or None,
                        address or None,
                    ),
                )
                new_id = cur.fetchone()["id"]
                unique_id = f"REG{new_id:06d}"
                cur.execute("UPDATE users SET unique_id=%s WHERE id=%s", (unique_id, new_id))
                conn.commit()
        finally:
            conn.close()

        session.pop("google_pending", None)
        flash(f"Registered via Google! Your Registration ID is {unique_id}. "
              f"An admin must approve your account before you can log in.")
        return redirect(url_for("login"))

    return render_template(
        "complete_google_profile.html",
        email=pending["email"],
        name=pending["name"],
        suggested_username=pending["suggested_username"],
    )


@app.route("/dashboard")
@login_required
def dashboard():
    referral_link = url_for("register", ref=session.get("unique_id"), _external=True)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM users WHERE referred_by=%s AND status='approved'",
                (session.get("unique_id"),),
            )
            referral_count = cur.fetchone()["c"]

            cur.execute(
                "SELECT referred_by FROM users WHERE id=%s", (session["user_id"],)
            )
            upline_row = cur.fetchone()
            upline_id = upline_row["referred_by"] if upline_row else None
    finally:
        conn.close()

    amount = referral_count * 100

    if referral_count >= 10:
        level = "Level 4 - Gold"
    elif referral_count >= 5:
        level = "Level 3 - Silver"
    elif referral_count >= 1:
        level = "Level 2 - Bronze"
    else:
        level = "Level 1 - Starter"

    return render_template(
        "dashboard.html",
        username=session["username"],
        unique_id=session.get("unique_id"),
        referral_link=referral_link,
        referral_count=referral_count,
        upline_id=upline_id,
        level=level,
        amount=amount,
    )


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
                """
                SELECT u.id, u.unique_id, u.username, u.email, u.status,
                       u.referred_by, u.reset_status, u.phone, u.address,
                       u.created_at, r.username AS referrer_username
                FROM users u
                LEFT JOIN users r ON u.referred_by = r.unique_id
                WHERE u.role != 'admin'
                ORDER BY u.created_at DESC
                """
            )
            users = cur.fetchall()

            cur.execute("SELECT COUNT(*) AS c FROM users WHERE role != 'admin' AND status='pending'")
            pending_count = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) AS c FROM users WHERE role != 'admin' AND status='approved'")
            total_participants = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) AS c FROM users WHERE role != 'admin' AND reset_status='pending'")
            password_requests = cur.fetchone()["c"]
    finally:
        conn.close()
    return render_template(
        "admin.html",
        users=users,
        pending_count=pending_count,
        total_participants=total_participants,
        password_requests=password_requests,
    )


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


@app.route("/admin/approve-reset/<int:user_id>", methods=["POST"])
@admin_required
def approve_reset(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET reset_status='approved' WHERE id=%s", (user_id,))
            conn.commit()
    finally:
        conn.close()
    flash("Password reset approved -- the user can now set a new password.")
    return redirect(url_for("admin_panel"))


@app.route("/admin/reject-reset/<int:user_id>", methods=["POST"])
@admin_required
def reject_reset(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET reset_status='none' WHERE id=%s", (user_id,))
            conn.commit()
    finally:
        conn.close()
    flash("Password reset request denied.")
    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    app.run(debug=True)
