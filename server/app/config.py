"""Configurações do servidor via variáveis de ambiente (arquivo .env)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Servidor de Áudio"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    # Banco de dados
    database_url: str = "postgresql+psycopg://audio:audio123@localhost:5432/audiodb"

    # Armazenamento
    storage_root: str = str(BASE_DIR / "storage")
    trash_dir: str = str(BASE_DIR / "storage" / "trash")

    # CORS
    cors_origins: str = "*"

    # Uploads
    max_upload_mb: int = 100


settings = Settings()
