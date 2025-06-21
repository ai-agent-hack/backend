from typing import List, Optional
from pydantic import EmailStr, field_validator
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # Application settings
    PROJECT_NAME: str = "FastAPI Backend with SOLID Principles"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Session settings
    SESSION_SECRET_KEY: str = (
        "your-super-secret-session-key-change-in-production-minimum-32-characters"
    )
    SESSION_MAX_AGE: int = 24 * 60 * 60  # 24 hours in seconds

    # GCP Cloud SQL Database Settings
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "fastapi_db"
    DB_HOST: str = "localhost"  # For local development with Cloud SQL Proxy
    DB_PORT: str = "5432"
    CLOUD_SQL_CONNECTION_NAME: Optional[str] = None  # Format: project:region:instance

    # Google Cloud Settings
    GOOGLE_CLOUD_PROJECT: Optional[str] = None

    # CORS Settings
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    # Redis Settings (optional - uncomment when needed)
    # REDIS_URL: str = "redis://localhost:6379"

    # Email Settings
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_TLS: bool = True
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None

    # Testing
    TESTING: bool = False

    @property
    def database_url(self) -> str:
        """Generate database URL based on environment"""
        if self.ENVIRONMENT == "production" and self.CLOUD_SQL_CONNECTION_NAME:
            # Unix socket connection for App Engine/Cloud Run
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@/{self.DB_NAME}?host=/cloudsql/{self.CLOUD_SQL_CONNECTION_NAME}"
        else:
            # TCP connection for local development with Cloud SQL Proxy
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # 추가 환경변수 허용


settings = Settings()
