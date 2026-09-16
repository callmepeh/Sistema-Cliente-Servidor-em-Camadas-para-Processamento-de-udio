"""Carrega variáveis do arquivo .env do cliente (sem dependências externas)."""
import os
from pathlib import Path


def load_env() -> None:
    """Lê client/.env, se existir, e define as variáveis no ambiente."""
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
