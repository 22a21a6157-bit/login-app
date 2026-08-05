
-- Drop old tables if you want a fresh start (BACKUP DATA FIRST!)
-- If you have existing data, use ALTER TABLE instead (see comments below)

-- ============================================
-- USERS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS users (
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
CREATE TABLE IF NOT EXISTS password_reset_requests (
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
CREATE TABLE IF NOT EXISTS referrals (
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
CREATE TABLE IF NOT EXISTS admin_logs (
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
CREATE INDEX IF NOT EXISTS idx_users_public_id ON users(public_user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_referral_id ON users(referral_id);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_user ON password_reset_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_status ON password_reset_requests(status);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referred ON referrals(referred_id);
CREATE INDEX IF NOT EXISTS idx_admin_logs_admin ON admin_logs(admin_id);

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

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- FUNCTION: Calculate User Level
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

-- ============================================
-- NOTE: Referral crediting on approval is handled exclusively by the
-- Flask app (see approve_user() in app.py), which also writes an
-- admin_logs entry. A DB trigger doing the same thing used to exist here
-- but was removed: it duplicated the app's logic (risking the referrer
-- being credited twice), and its "referrer_record IS NOT NULL" check
-- never evaluated true, so it silently never worked in the first place.
-- Make sure any existing database has it removed too:
-- ============================================
DROP TRIGGER IF EXISTS trg_process_referral ON users;
DROP FUNCTION IF EXISTS process_referral_on_approval();

-- ============================================
-- MIGRATION NOTES FOR EXISTING DATA
-- ============================================
/*
If you have existing data, DO NOT drop tables. Run these ALTER statements instead:

-- Add new columns
ALTER TABLE users ADD COLUMN IF NOT EXISTS public_user_id CHAR(16);
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_status VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Update existing users with public_user_id
UPDATE users SET public_user_id = UPPER(SUBSTRING(REPLACE(gen_random_uuid()::TEXT, '-', '') FROM 1 FOR 16)) WHERE public_user_id IS NULL;

-- Make it unique and not null
ALTER TABLE users ALTER COLUMN public_user_id SET NOT NULL;
ALTER TABLE users ADD CONSTRAINT unique_public_user_id UNIQUE (public_user_id);

-- Create other tables
[Run CREATE TABLE statements for password_reset_requests, referrals, admin_logs above]

-- Create indexes
[Run CREATE INDEX statements above]

-- Create functions and triggers
[Run function/trigger statements above]
*/
