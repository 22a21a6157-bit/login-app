
-- ═══════════════════════════════════════════════════════════════
-- NEON DATABASE MIGRATION
-- Run this in your Neon SQL Editor to upgrade existing data
-- ═══════════════════════════════════════════════════════════════

-- Step 1: Add new columns to existing users table (safe - won't break data)
DO $$
BEGIN
    -- public_user_id
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='public_user_id') THEN
        ALTER TABLE users ADD COLUMN public_user_id CHAR(16);
    END IF;

    -- phone
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='phone') THEN
        ALTER TABLE users ADD COLUMN phone VARCHAR(20);
    END IF;

    -- address
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='address') THEN
        ALTER TABLE users ADD COLUMN address TEXT;
    END IF;

    -- google_id
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='google_id') THEN
        ALTER TABLE users ADD COLUMN google_id VARCHAR(100);
    END IF;

    -- password_reset_status
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='password_reset_status') THEN
        ALTER TABLE users ADD COLUMN password_reset_status VARCHAR(20);
    END IF;

    -- approved_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='approved_at') THEN
        ALTER TABLE users ADD COLUMN approved_at TIMESTAMP;
    END IF;

    -- last_login
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='last_login') THEN
        ALTER TABLE users ADD COLUMN last_login TIMESTAMP;
    END IF;

    -- updated_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='updated_at') THEN
        ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    END IF;

    -- is_admin
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='is_admin') THEN
        ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;
    END IF;

    -- referral_count
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='referral_count') THEN
        ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0;
    END IF;

    -- amount_earned
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='amount_earned') THEN
        ALTER TABLE users ADD COLUMN amount_earned DECIMAL(12,2) DEFAULT 0.00;
    END IF;

    -- user_level
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='user_level') THEN
        ALTER TABLE users ADD COLUMN user_level VARCHAR(20) DEFAULT 'Starter';
    END IF;

    -- referral_id (stores the referrer's public_user_id)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='referral_id') THEN
        ALTER TABLE users ADD COLUMN referral_id CHAR(16);
    END IF;

    -- status (if not exists, create it)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='status') THEN
        ALTER TABLE users ADD COLUMN status VARCHAR(20) DEFAULT 'approved';
    END IF;

    -- full_name (if not exists)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='users' AND column_name='full_name') THEN
        ALTER TABLE users ADD COLUMN full_name VARCHAR(100);
        -- Copy username to full_name as fallback
        UPDATE users SET full_name = username WHERE full_name IS NULL;
    END IF;
END $$;

-- Step 2: Generate public_user_id for existing users who don't have one
-- (16 hex chars, matching both the CHAR(16) column and generate_public_id()
-- in app.py - gen_random_uuid() alone produces 32 hex chars and overflows
-- the column, which used to make this UPDATE fail outright on any DB that
-- actually had legacy rows to backfill)
UPDATE users 
SET public_user_id = UPPER(SUBSTRING(REPLACE(gen_random_uuid()::TEXT, '-', '') FROM 1 FOR 16))
WHERE public_user_id IS NULL;

-- Step 3: Make public_user_id unique and not null
ALTER TABLE users ALTER COLUMN public_user_id SET NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'unique_public_user_id'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT unique_public_user_id UNIQUE (public_user_id);
    END IF;
END $$;

-- Step 3b: referral_id should reference public_user_id, same as a fresh
-- install via schema.sql - a DB that only ever ran this migration script
-- was missing this FK entirely. Added as NOT VALID so it can't fail the
-- migration if a stray/orphaned referral_id already exists; it still
-- enforces the constraint for everything written from this point on. Once
-- you've confirmed your data is clean you can tighten it with:
--   ALTER TABLE users VALIDATE CONSTRAINT fk_users_referral_id;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_users_referral_id'
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT fk_users_referral_id
            FOREIGN KEY (referral_id) REFERENCES users(public_user_id) NOT VALID;
    END IF;
END $$;

-- Step 4: Set default status for users without status
UPDATE users SET status = 'approved' WHERE status IS NULL;

-- Step 5: Set existing admin if you know the username/email
-- UPDATE users SET is_admin = TRUE WHERE username = 'your_admin_username';

-- Step 6: Create new tables (if they don't exist)
CREATE TABLE IF NOT EXISTS password_reset_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending',
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_id CHAR(16) REFERENCES users(public_user_id),
    referred_id CHAR(16) REFERENCES users(public_user_id),
    status VARCHAR(20) DEFAULT 'pending',
    reward_amount DECIMAL(12,2) DEFAULT 100.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_logs (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    target_user_id INTEGER,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 7: Create indexes for performance
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

-- Step 8: Create function to calculate user level
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

-- Step 9: Referral crediting on approval is handled exclusively by the
-- Flask app (see approve_user() in app.py), which also writes an
-- admin_logs entry. A DB trigger doing the same thing used to live here
-- but has been removed: it duplicated the app's logic (risking the
-- referrer being credited twice), and its "referrer_record IS NOT NULL"
-- check is a PL/pgSQL RECORD-comparison gotcha that never evaluated true
-- even when a matching row was found - so it silently never worked.
-- This drops it in case it was created by an earlier version of this file.
DROP TRIGGER IF EXISTS trg_process_referral ON users;
DROP FUNCTION IF EXISTS process_referral_on_approval();

-- Step 11: Create auto-update updated_at function
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

-- ═══════════════════════════════════════════════════════════════
-- MIGRATION COMPLETE!
-- ═══════════════════════════════════════════════════════════════
-- Run this to verify:
-- SELECT id, public_user_id, username, email, status, is_admin, user_level, referral_count, amount_earned FROM users LIMIT 5;
