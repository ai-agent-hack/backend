-- Database initialization script for FastAPI backend
-- This script creates necessary extensions and initial data

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes for better performance (will be created by SQLAlchemy migrations)
-- This is just for reference

-- Insert initial superuser (optional - can be done via API)
-- Password is 'admin123' hashed with bcrypt
-- INSERT INTO users (email, username, hashed_password, is_active, is_superuser, full_name, created_at, updated_at)
-- VALUES (
--     'admin@example.com',
--     'admin',
--     '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewDJRZDt2.FHTrIy',
--     true,
--     true,
--     'System Administrator',
--     NOW(),
--     NOW()
-- );

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- This trigger will be applied to tables by SQLAlchemy migrations
-- CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
--     FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); 