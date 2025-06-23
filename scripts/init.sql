-- FastAPIバックエンド用データベース初期化スクリプト
-- このスクリプトは必要な拡張機能と初期データを作成します

-- 拡張機能を作成
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- パフォーマンス向上のためのインデックス作成（SQLAlchemyマイグレーションで作成されます）
-- これは参考用です

-- 初期スーパーユーザーを挿入（オプション - API経由でも可能）
-- パスワードは'admin123'をbcryptでハッシュ化
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

-- updated_atタイムスタンプを自動更新する関数を作成
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- このトリガーはSQLAlchemyマイグレーションでテーブルに適用されます
-- CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
--     FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); 