from typing import List, Optional
from pydantic import EmailStr, field_validator
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # アプリケーション設定
    PROJECT_NAME: str = "FastAPI Backend with SOLID Principles"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # セッション設定
    SESSION_SECRET_KEY: str = (
        "your-super-secret-session-key-change-in-production-minimum-32-characters"
    )
    SESSION_MAX_AGE: int = 24 * 60 * 60  # 24時間（秒単位）

    # GCP Cloud SQLデータベース設定
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "fastapi_db"
    DB_HOST: str = "localhost"  # Cloud SQL Proxyを使用したローカル開発用
    DB_PORT: str = "5432"
    CLOUD_SQL_CONNECTION_NAME: Optional[str] = None  # 形式: project:region:instance

    # Google Cloud設定
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_MAP_API_KEY: Optional[str] = None

    # CORS設定
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "https://vibe-planning-service-900145575342.asia-northeast1.run.app",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    # Redis設定（オプション - 必要時にコメントを解除）
    REDIS_URL: str = "redis://localhost:6379"
    USE_REDIS_CACHE: bool = False

    # メール設定
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_TLS: bool = True
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None

    # テスト
    TESTING: bool = False

    # 성능 최적화 설정
    ENABLE_CACHE: bool = True
    CACHE_TTL: int = 3600  # 1시간
    MAX_CACHE_SIZE: int = 1000
    ASYNC_CONCURRENCY_LIMIT: int = 10
    BATCH_SIZE: int = 50
    API_TIMEOUT: int = 30
    ENABLE_PERFORMANCE_LOGGING: bool = True

    @property
    def database_url(self) -> str:
        """環境に基づいてデータベースURLを生成"""
        if self.ENVIRONMENT == "production" and self.CLOUD_SQL_CONNECTION_NAME:
            # App Engine/Cloud Run用のUnixソケット接続
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@/{self.DB_NAME}?host=/cloudsql/{self.CLOUD_SQL_CONNECTION_NAME}"
        else:
            # Cloud SQL Proxyを使用したローカル開発用のTCP接続
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # 追加環境変数を許可


settings = Settings()
