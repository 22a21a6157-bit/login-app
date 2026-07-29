-- ═══════════════════════════════════════════════════════════════
-- FULL RESET - Neon SQL Editor
-- WARNING: this permanently deletes ALL existing data
-- (users, referrals, password reset requests, admin logs).
-- There is no undo. Only run this if you're OK losing everything
-- currently in the database.
-- ═══════════════════════════════════════════════════════════════

-- ── Step 1: Drop everything from the old app ──────────────────
DROP TABLE IF EXISTS admin_logs CASCADE;
DROP TABLE IF EXISTS referrals CASCADE;
DROP TABLE IF EXISTS password_reset_requests CASCADE;
DROP TABLE IF EXISTS users CASCADE;

DROP TRIGGER IF EXISTS trg_process_referral ON users;
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP FUNCTION IF EXISTS process_referral_on_approval();
DROP FUNCTION IF EXISTS update_updated_at_column();
DROP FUNCTION IF EXISTS calculate_user_level(INTEGER);

-- ── Step 2: Rebuild fresh from the fixed schema ────────────────

-- ============================================
-- USERS TABLE
-- ============================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    public_user_id CHAR(16) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    phone VARCHAR(20),
    address TEXT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    google_id VARCHAR(100) UNIQUE,

    -- Referral system
    referral_id CHAR(16) REFERENCES users(public_user_id) ON DELETE SET NULL,
    referral_count INTEGER DEFAULT 0,
    amount_earned DECIMAL(12,2) DEFAULT 0.00,
    user_level VARCHAR(20) DEFAULT 'Starter',

    -- Approval & status
    status VARCHAR(20) DEFAULT 'pending',  -- pending, approved, rejected
    approved_at TIMESTAMP,
    is_admin BOOLEAN DEFAULT FALSE,

    -- Password reset via admin
    password_reset_status VARCHAR(20) DEFAULT NULL,  -- requested, approved, rejected
    password_reset_requested_at TIMESTAMP,

    -- Tracking
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- PASSWORD RESET REQUESTS TABLE
-- ============================================
CREATE TABLE password_reset_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, approved, rejected
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by INTEGER REFERENCES users(id)
);

-- ============================================
-- REFERRALS TABLE (for audit trail)
-- ============================================
CREATE TABLE referrals (
    id SERIAL PRIMARY KEY,
    referrer_id CHAR(16) REFERENCES users(public_user_id),
    referred_id CHAR(16) REFERENCES users(public_user_id),
    status VARCHAR(20) DEFAULT 'pending',
    reward_amount DECIMAL(12,2) DEFAULT 100.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP
);

-- ============================================
-- ADMIN LOGS TABLE
-- ============================================
CREATE TABLE admin_logs (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    target_user_id INTEGER,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================
CREATE INDEX idx_users_public_id ON users(public_user_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_referral_id ON users(referral_id);
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_password_reset_user ON password_reset_requests(user_id);
CREATE INDEX idx_password_reset_status ON password_reset_requests(status);
CREATE INDEX idx_referrals_referrer ON referrals(referrer_id);
CREATE INDEX idx_referrals_referred ON referrals(referred_id);
CREATE INDEX idx_admin_logs_admin ON admin_logs(admin_id);

-- ============================================
-- FUNCTION: Auto-update updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- FUNCTION: Calculate User Level
-- (kept for reference / possible future direct-SQL use - the app does
-- not currently call this; it computes levels in Python)
-- ============================================
CREATE OR REPLACE FUNCTION calculate_user_level(ref_count INTEGER)
RETURNS VARCHAR(20) AS $$
BEGIN
    IF ref_count >= 50 THEN RETURN 'Legend';
    ELSIF ref_count >= 25 THEN RETURN 'Diamond';
    ELSIF ref_count >= 10 THEN RETURN 'Gold';
    ELSIF ref_count >= 5 THEN RETURN 'Silver';
    ELSIF ref_count >= 1 THEN RETURN 'Bronze';
    ELSE RETURN 'Starter';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- NOTE: There is intentionally no referral-crediting trigger here.
-- Referral crediting on approval is handled exclusively by the Flask
-- app (see approve_user() in app.py), which also writes an admin_logs
-- entry. An earlier version had a DB trigger doing the same thing,
-- but it duplicated the app's logic (risking double-crediting) and
-- its "referrer_record IS NOT NULL" check never evaluated true anyway,
-- so it silently never worked.

-- ═══════════════════════════════════════════════════════════════
-- DONE. Verify with:
-- SELECT table_name FROM information_schema.tables WHERE table_schema='public';
-- ═══════════════════════════════════════════════════════════════
