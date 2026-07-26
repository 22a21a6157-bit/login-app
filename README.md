# Login App - Fixed v4

## What Changed from v3 (bug fixes, all verified against a real Postgres DB)
- **Fixed: `schema.sql` was missing the `is_admin` column.** A fresh install using `schema.sql` alone locked everyone out of `/admin` because every admin check errored. Added the column.
- **Fixed: forgot-password crashed every time.** `cur.execute(...).fetchall()` doesn't work with psycopg2 (`execute()` returns `None`), so every reset request threw an error. Split into two statements.
- **Fixed: referral rewards were never actually granted by the DB trigger** (and would have double-counted if it had worked). The trigger's `IF referrer_record IS NOT NULL THEN` check is a PL/pgSQL gotcha that never evaluates true even when the row exists, so it silently no-opped. Meanwhile `app.py`'s `approve_user` route does the same crediting correctly. Removed the trigger from `schema.sql` and `migration.sql`; referral crediting is now handled exclusively by the app.
- **Fixed: password reset links were forgeable.** The old token was just unsigned `base64(user_id:public_id)`, and `public_user_id` is shown to users on their own dashboard - so anyone could guess/construct a link for another account. Reset links are now signed with `itsdangerous` and expire after 1 hour.
- **Fixed: login could silently fail on plain HTTP.** `SESSION_COOKIE_SECURE` was hardcoded `True`, so on non-HTTPS setups (e.g. local testing) the session cookie was never set, making login look like it "worked" then bounce straight back. Now controlled by `SESSION_COOKIE_SECURE` env var (defaults to `true` - keep it `true` in production behind HTTPS; set to `false` only for local HTTP testing).
- **Fixed: `/api/user/check` ignored email if a username was also passed.**
- **Improved:** Google OAuth client is now registered once at startup instead of on every single request (was re-fetching Google's OIDC metadata every time).

## Critical: Run Migration First (existing databases)!

Before deploying, run `migration.sql` in your Neon SQL Editor. It's safe to re-run.

Then make your admin account:
```sql
UPDATE users
SET is_admin = TRUE, status = 'approved'
WHERE username = '__Chinni__admin__';
```

## New deployments
Just run `schema.sql` - it now includes everything (including `is_admin`).

## Environment Variables
- `DATABASE_URL` - required
- `SECRET_KEY` - required in production (also used to sign password-reset tokens)
- `SESSION_COOKIE_SECURE` - `true` (default) in production over HTTPS, `false` for local HTTP testing
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - optional, enables "Sign in with Google"

## Deploy Steps
1. Replace ALL files with these new ones
2. Push to GitHub
3. Render auto-deploys

## Test Login
- Username: `__Chinni__admin__`
- Password: `Chinni@157`
- Should redirect to `/admin`

