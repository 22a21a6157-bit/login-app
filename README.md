# Login App - Fixed v5

## What Changed from v4
- **Referral ID field is now read-only.** It only ever displays whatever code came from an invite link (`?ref=...`) - it can no longer be hand-edited on the registration or Google-signup-completion forms.
- **Password reset links are now emailed directly to the user** when an admin approves the request, instead of only appearing in a 5-second admin toast (which was the real bug behind "the reset page doesn't show" - the link was never lost on the server, it just vanished from the admin's screen before it could be copied and given to the user). If email sending isn't configured or fails, the link still falls back to a persistent (non-auto-hiding) admin toast so it's never truly lost.
- **New "Liquid Glass" visual redesign**: frosted-glass cards/toasts/forms (iOS-style blur + translucency) over a dynamically-rotating, full-bleed nature wallpaper background (freely-licensed Wikimedia Commons photos, crossfading every ~12s). Applies site-wide automatically since every page extends `base.html`.

## Environment Variables
- `DATABASE_URL` - required
- `SECRET_KEY` - required in production (also signs password-reset tokens)
- `SESSION_COOKIE_SECURE` - `true` (default) in production over HTTPS, `false` for local HTTP testing
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - optional, enables "Sign in with Google"
- **`SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, `SMTP_USE_TLS` (default true)** - required for password-reset emails to actually send. Works with any standard SMTP provider (Gmail app password, SendGrid, Mailgun, SES SMTP, etc.). If left unset, the app still works, but reset links fall back to being shown to the admin instead of emailed.

## Customizing the wallpaper
The rotating background photos are listed as an array (`WALLPAPERS`) near the top of `static/js/main.js`. Swap in your own 4K images any time by replacing that list with URLs to your own hosted photos (or files under `/static/img/`) - no other code changes needed.

## Critical: Run Migration First (existing databases)!

Before deploying, run `migration.sql` in your Neon SQL Editor. It's safe to re-run.

Then make your admin account (see `create_admin_account.sql`, or use the `flask create-admin` CLI).

## New deployments
Run `reset_database.sql` (wipes everything) or `schema.sql` (fresh install) - both now include everything (including `is_admin`).

## Deploy Steps
1. Replace ALL files with these new ones
2. Set the environment variables above (especially the SMTP ones, or reset emails won't send)
3. Push to GitHub
4. Render auto-deploys


