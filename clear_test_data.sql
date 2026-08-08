-- ═══════════════════════════════════════════════════════════════
-- CLEAR TEST DATA (keeps schema + your admin account)
-- Run this in the Neon SQL Editor.
-- Deletes every non-admin user, all referrals, all password reset
-- requests, and all admin action logs. Your admin login(s) stay,
-- with their referral stats reset to a clean slate.
-- ═══════════════════════════════════════════════════════════════

-- Order matters: these reference users with no ON DELETE action, so
-- they must be cleared before any users are deleted.
TRUNCATE TABLE admin_logs RESTART IDENTITY;
TRUNCATE TABLE referrals RESTART IDENTITY;
TRUNCATE TABLE password_reset_requests RESTART IDENTITY;

-- Remove every non-admin user. (users.referral_id is
-- ON DELETE SET NULL, so this can't break any remaining row.)
DELETE FROM users WHERE is_admin = FALSE;

-- Give the surviving admin account(s) a clean referral slate.
UPDATE users
SET referral_count = 0,
    amount_earned = 0.00,
    user_level = 'Starter'
WHERE is_admin = TRUE;

-- ═══════════════════════════════════════════════════════════════
-- DONE. Verify with:
-- SELECT id, username, email, is_admin FROM users;
-- SELECT COUNT(*) FROM referrals;
-- ═══════════════════════════════════════════════════════════════
