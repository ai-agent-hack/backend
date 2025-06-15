from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Generator

from app.core.config import settings

# Create SQLAlchemy engine with optimized settings for Cloud SQL
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Validate connections before use
    pool_recycle=300,  # Recycle connections every 5 minutes
    pool_size=10,  # Number of permanent connections to pool
    max_overflow=20,  # Maximum overflow connections
    echo=settings.ENVIRONMENT == "development",  # Log SQL queries in development
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for models
Base = declarative_base()


def get_db() -> Generator:
    """
    Database dependency injection.
    Creates a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
