from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────────
    database_url: str = "postgresql://postgres:postgres@localhost:5432/medintel"
    db_pool_min: int = 2
    db_pool_max: int = 10

    # ── JWT Auth ─────────────────────────────────────────────
    secret_key: str       = "medintel-insecure-dev-key-change-before-deploy"
    jwt_algorithm: str    = "HS256"
    jwt_expire_hours: int = 24

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: str = (
        "http://localhost:5500,"
        "http://127.0.0.1:5500,"
        "http://localhost:3000,"
        "http://127.0.0.1:3000"
    )

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
