"""
Configuration for FastAPI Ingestion Service.
Uses environment variables with sensible defaults.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""

    # Application
    app_name: str = "SAP B1 Ingestion Service"
    app_version: str = "1.0.0"
    debug: bool = False

    # API Keys (comma-separated list of valid keys)
    api_keys: str = ""

    # Encryption
    encryption_key: str  # Fernet key for payload encryption

    # Database
    database_url: str

    # CORS
    cors_origins: str = "*"  # Comma-separated list

    # Rate Limiting
    rate_limit_per_minute: int = 60

    # Railway
    railway_environment: str = "production"
    railway_project: str = "sap-railway-pipeline"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def api_keys_list(self) -> list[str]:
        """Parse API keys string into list."""
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
