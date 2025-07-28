# ===== src/config/settings.py =====
import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    filemaker_dsn_path: Path = Field(default=Path("/config/filemaker.dsn"))
    filemaker_server: str = Field(default="192.168.10.216")
    filemaker_port: int = Field(default=2399)
    filemaker_database: str = Field(default="CrownMasterDatabase")
    filemaker_username: Optional[str] = None
    filemaker_password: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FILEMAKER_",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


class ProcessingSettings(BaseSettings):
    """Image processing configuration."""
    input_dir: Path = Field(default=Path("/data/input"))
    processing_dir: Path = Field(default=Path("/data/processing"))
    production_dir: Path = Field(default=Path("/data/production"))
    rejected_dir: Path = Field(default=Path("/data/rejected"))
    metadata_dir: Path = Field(default=Path("/data/metadata"))
    logs_dir: Path = Field(default=Path("/data/logs"))

    supported_extensions: List[str] = Field(default=[".psd", ".png", ".jpg", ".jpeg", ".tif", ".tiff"])
    min_file_size_bytes: int = Field(default=1024)
    max_file_size_bytes: int = Field(default=100 * 1024 * 1024)  # 100MB
    min_resolution: int = Field(default=2500)

    scan_interval_seconds: int = Field(default=30)
    processing_timeout_seconds: int = Field(default=300)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PROCESSING_",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


class WebSettings(BaseSettings):
    """Web interface configuration."""
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    debug: bool = Field(default=False)
    secret_key: str = Field(default="change-me-in-production")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WEB_",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


class NotificationSettings(BaseSettings):
    """Notification configuration."""
    teams_webhook_url: Optional[str] = None
    email_enabled: bool = Field(default=False)
    smtp_server: Optional[str] = None
    smtp_port: int = Field(default=587)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NOTIFICATION_",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


class Settings(BaseSettings):
    """Main application settings."""
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    tz: str = Field(default="America/New_York")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Global settings instance
settings = Settings()