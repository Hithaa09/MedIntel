from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    db_user: str = "APP"
    db_pass: str = "app"
    db_dsn: str = "localhost:1521/XEPDB1"
    db_pool_min: int = 2
    db_pool_max: int = 10
    cors_origins: list[str] = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Accept both JSON array and comma-separated string from env var:
    #   CORS_ORIGINS=http://localhost:5500,http://localhost:3000   ← works
    #   CORS_ORIGINS=["http://localhost:5500","http://localhost:3000"]  ← also works
    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
