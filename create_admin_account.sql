-- ═══════════════════════════════════════════════════════════════
-- CREATE ADMIN ACCOUNT
-- Run this in the Neon SQL Editor AFTER running reset_database.sql
-- (or against any DB that already has the users table from schema.sql)
--
-- Creates/updates:
--   Username: __Chinni__admin__
--   Password: Chinni@157
--   Email:    22a21a6157@swarnandhra.ac.in
--
-- The password_hash below was generated with Werkzeug's
-- generate_password_hash('Chinni@157') and has been verified to work
-- with the app's login (check_password_hash) - it is NOT plaintext,
-- it's a proper scrypt hash.
-- ═══════════════════════════════════════════════════════════════

INSERT INTO users (
    public_user_id, full_name, email, username, password_hash,
    status, is_admin, created_at
) VALUES (
    '4D68448AA6F1A805',
    'Chinni Admin',
    '22a21a6157@swarnandhra.ac.in',
    '__Chinni__admin__',
    'scrypt:32768:8:1$WeKzgSU3aiKXTs2v$dec5c87cf22464a3bb1e008a42b62d65ab664788f7add695dd5ce8652bc013106e2f06bf746ebb84465941c138b78a96353b37209df09e9039fd0fc8d132e600',
    'approved',
    TRUE,
    NOW()
)
ON CONFLICT (username) DO UPDATE SET
    email = EXCLUDED.email,
    password_hash = EXCLUDED.password_hash,
    status = 'approved',
    is_admin = TRUE;

-- Verify:
-- SELECT username, email, status, is_admin FROM users WHERE username = '__Chinni__admin__';
