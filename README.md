# Login App - Fixed v6

## What Changed from v5

### 1. Password reset is now "compose, don't send"
Approving a reset request used to email the link straight to the user via SMTP. Now the server never sends anything - it generates the (still single-use, still 1-hour) reset link, then hands the admin a **Compose Reset Email** modal with the recipient, subject, and body already filled in. From there the admin can:
- Click **Open in Email App** to launch their own mail client with everything prefilled (a `mailto:` link), or
- Copy any individual field (To / Subject / Body / just the raw link) and paste it wherever they want to send it (email, SMS, WhatsApp, etc.)

Nothing is transmitted by the server in this flow, so SMTP configuration is no longer required for password resets to work. The `SMTP_*` settings and the `send_email()` helper are still in the codebase, just unused by this route - they're there if you want to wire up a different transactional email later.

### 2. Bug fixes
- **DB connection pool right-sized for Neon.** The pool was `maxconn=20` **per gunicorn worker**, hardcoded. With more than a couple of workers that can exceed Neon's connection ceiling (intermittent `too many connections` errors). It's now `maxconn=5` by default and configurable via `DB_POOL_MINCONN` / `DB_POOL_MAXCONN`. If you're on Neon, prefer the **pooled** connection string (hostname contains `-pooler`) for `DATABASE_URL`.
- **Stale/dropped connections no longer crash a request.** Neon can silently close idle connections (e.g. when the compute auto-suspends). `get_db()` now does a cheap health check before handing out a pooled connection and transparently swaps in a fresh one if it's dead, instead of the request failing with a raw `OperationalError`.
- **`migration.sql` / `schema.sql` backfill bug.** The line that generates a `public_user_id` for pre-existing rows used `gen_random_uuid()` with the hyphens stripped, which is 32 characters - but the column is `CHAR(16)`. On any database that actually had existing rows to backfill, this failed outright with `value too long for type character(16)`. Fixed to generate 16 hex characters (matching `generate_public_id()` in `app.py`).
- **`migration.sql` was missing the `referral_id` foreign key.** A database set up via `schema.sql` had `referral_id` correctly referencing `users(public_user_id)`; one upgraded via `migration.sql` didn't have that constraint at all. Added (as `NOT VALID` so it can't fail the migration on a DB that already has a stray value - see the comment in the file for how to validate it once your data's confirmed clean).
- **Added `Procfile`.** There wasn't one in the repo, which means Render's Start Command had to be set by hand in the dashboard with nothing to fall back on. Now: `gunicorn app:app --worker-class gthread --workers 2 --threads 4 --timeout 60`.
- Replaced the deprecated `datetime.utcnow()` with timezone-aware `datetime.now(timezone.utc)`.
- The dashboard page was silently redefining `copyToClipboard()` with a version that has no fallback if the Clipboard API is unavailable/denied, shadowing the better version already in `main.js`. Removed the duplicate.

### 3. Referral network visualization
A new **Network** page (`/admin/network`, linked from the admin nav bar) shows every independent referral tree as a hexagon (the referrer) surrounded by circles (their direct referrals), colored by status - green/amber/red for approved/pending/rejected, matching the colors already used elsewhere in the admin dashboard. It's:
- **Live** - polls for updates every 20s and shows a "updated Xs ago" indicator; there's also a manual refresh button.
- **Interactive** - hover any node for a tooltip, click a circle with its own referrals to step into their network (with breadcrumbs to navigate back up), or search by name/referral ID to jump straight to someone.
- Every user also gets a compact read-only version of their own network ("My Network") on their dashboard, showing their direct referrals **regardless of status** - previously the dashboard's referrals table only ever showed approved ones, so this is the first place a user can see that e.g. a referral is still pending.

No database changes were needed for this - it's built entirely from columns that already existed (`referral_id`, `status`, `user_level`, `referral_count`, `amount_earned`).

## Environment Variables
- `DATABASE_URL` - required
- `SECRET_KEY` - required in production (also signs password-reset tokens)
- `SESSION_COOKIE_SECURE` - `true` (default) in production over HTTPS, `false` for local HTTP testing
- `DB_POOL_MINCONN` (default `1`) / `DB_POOL_MAXCONN` (default `5`) - per-worker DB connection pool size; keep `MAXCONN × gunicorn workers` comfortably under your Postgres provider's connection limit
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - optional, enables "Sign in with Google"
- `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, `SMTP_USE_TLS` (default true) - optional and currently unused by the reset-password flow (see above); kept for anyone who wants to send other transactional email later.

## Customizing the wallpaper
The rotating background photos are listed as an array (`WALLPAPERS`) near the top of `static/js/main.js`. Swap in your own 4K images any time by replacing that list with URLs to your own hosted photos (or files under `/static/img/`) - no other code changes needed.

## Critical: Run Migration First (existing databases)!

Before deploying, run `migration.sql` in your Neon SQL Editor. It's safe to re-run.

Then make your admin account (see `create_admin_account.sql`, or use the `flask create-admin` CLI).

## New deployments
Run `reset_database.sql` (wipes everything) or `schema.sql` (fresh install) - both now include everything (including `is_admin`).

## Deploy Steps
1. Replace ALL files with these new ones
2. Set the environment variables above
3. In Render, confirm the web service's Start Command matches the `Procfile` (`gunicorn app:app --worker-class gthread --workers 2 --threads 4 --timeout 60`) - Render will pick up the `Procfile` automatically for a new service, but an existing service with a Start Command already set by hand in the dashboard won't switch over on its own
4. Push to GitHub
5. Render auto-deploys



