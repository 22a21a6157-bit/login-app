# Login App with Admin Approval (Flask + PostgreSQL)

## What this app does
- Users can register — but their account status starts as `pending`.
- They CANNOT log in until an admin approves them.
- A separate `/admin` panel (admin-only) lists all users and lets the
  admin Approve or Reject each one.
- Once approved, the user can log in normally and reach the dashboard.

## 1. Run it locally first

1. Install Postgres locally (or use any Postgres instance) and create a
   database, e.g. `login_app`.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set your local DB connection as an environment variable:
   ```
   export DATABASE_URL=postgresql://youruser:yourpassword@localhost:5432/login_app
   ```
   (On Windows: `set DATABASE_URL=...`)
4. Run schema.sql against that database to create the `users` table:
   ```
   psql $DATABASE_URL -f schema.sql
   ```
5. Create your admin account (one time):
   ```
   python create_admin.py
   ```
6. Run the app:
   ```
   python app.py
   ```
7. Visit `http://127.0.0.1:5000`:
   - Log in as admin -> go to `/admin` -> nothing pending yet.
   - Register a normal test user -> try logging in -> you'll be blocked
     with "awaiting admin approval".
   - Log back in as admin -> Approve that user -> now they can log in.

## 2. Deploy for free, 24/7 (Render + built-in Postgres)

Render's free web service + free Postgres database live in the same
dashboard, so nothing needs to be stitched together across providers.

1. Push this project to a GitHub repo (Render deploys from GitHub).
2. Go to render.com -> sign up free -> **New** -> **PostgreSQL**.
   - Give it a name, choose the free plan, create it.
   - Copy the **Internal Database URL** shown after creation.
3. Go to **New** -> **Web Service** -> connect your GitHub repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
   - Choose the Free instance type.
4. In the web service's **Environment** tab, add:
   - `DATABASE_URL` = (the Internal Database URL from step 2)
   - `SECRET_KEY` = any long random string
5. Deploy. Once live, open Render's **Shell** tab for your web service (or
   the Postgres dashboard's own SQL console) and run:
   ```
   psql $DATABASE_URL -f schema.sql
   python create_admin.py
   ```
   to set up the table and your admin login.
6. Visit your `https://yourapp.onrender.com` URL. Full loop:
   register -> pending -> admin approves at `/admin` -> user can log in.

### Note on "24/7"
Render's free web service sleeps after 15 minutes without traffic, and
takes about 60 seconds to wake back up on the next visit. This is the
tradeoff of $0 hosting anywhere. If you need instant response at all
times with zero downtime, that requires a paid tier (Render Starter is
$7/month). For a personal project or learning/demo purposes, the free
tier is fine.

## Notes
- Passwords are hashed with Werkzeug's `generate_password_hash` — never
  stored in plain text.
- The admin account is created only via `create_admin.py`, never through
  the public `/register` form — so random users can't grant themselves
  admin access.
- Change `SECRET_KEY` to a long random string before going live.
