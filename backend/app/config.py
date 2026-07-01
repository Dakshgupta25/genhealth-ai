"""
Application configuration management.

Uses Pydantic Settings to load and validate all environment variables.
Settings are loaded once at startup and cached.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, EmailStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ─── Application ──────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "GenHealth AI"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # ─── Security ─────────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    OTP_EXPIRE_MINUTES: int = 10
    BCRYPT_ROUNDS: int = 12

    # ─── CORS ─────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v):
        """Allow comma-separated string or list from env."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ─── PostgreSQL ───────────────────────────────────────────────────
    DATABASE_URL: str
    SYNC_DATABASE_URL: Optional[str] = None
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # ─── MongoDB ─────────────────────────────────────────────────────
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "genhealth"

    # ─── Redis ───────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── Celery ──────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ─── AWS S3 / MinIO ──────────────────────────────────────────────
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin123"
    AWS_REGION: str = "ap-south-1"
    AWS_BUCKET_NAME: str = "genhealth-records"
    S3_ENDPOINT_URL: Optional[str] = "http://localhost:9000"  # None for real AWS
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"

    # ─── Email ────────────────────────────────────────────────────────
    SENDGRID_API_KEY: Optional[str] = None
    FROM_EMAIL: str = "noreply@genhealth.ai"
    FROM_NAME: str = "GenHealth AI"

    # ─── Rate Limiting ────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_BURST: int = 20

    # ─── File Upload ─────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "pdf", "heic"]

    @field_validator("ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_extensions(cls, v):
        """Allow comma-separated string from env."""
        if isinstance(v, str):
            return [ext.strip().lower() for ext in v.split(",")]
        return v

    # ─── Invite ──────────────────────────────────────────────────────
    INVITE_TOKEN_EXPIRE_HOURS: int = 72
    INVITE_BASE_URL: str = "http://localhost:3000/invite"

    # ─── ML / OCR ────────────────────────────────────────────────────
    TESSERACT_CMD: str = "/usr/bin/tesseract"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # ─── Computed properties ─────────────────────────────────────────
    @property
    def is_development(self) -> bool:
        """True when running in local development mode."""
        return self.ENVIRONMENT.lower() == "development"

    @property
    def is_production(self) -> bool:
        """True when running in production mode."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def max_upload_bytes(self) -> int:
        """Maximum upload file size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def use_minio(self) -> bool:
        """True when using local MinIO instead of real AWS S3."""
        return self.S3_ENDPOINT_URL is not None


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    The lru_cache decorator ensures this is only called once per process
    lifetime, making it safe to use as a FastAPI dependency.
    """
    return Settings()
