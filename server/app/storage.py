"""Gerenciamento de armazenamento em disco.

Estrutura gerada:

    storage/
        2026/09/16/
            <uuid>/
                audio.wav            # original
                audio_processed.mp3  # processado
                meta.json
                waveform.png
        trash/
            <uuid>/...
"""
import json
import shutil
import uuid as uuid_lib
from datetime import datetime
from pathlib import Path

from .config import settings


def ensure_dirs() -> None:
    """Garante que os diretórios base existam."""
    Path(settings.storage_root).mkdir(parents=True, exist_ok=True)
    Path(settings.trash_dir).mkdir(parents=True, exist_ok=True)


def audio_dir(audio_uuid: str, created_at: datetime | None = None) -> Path:
    """Retorna o diretório do áudio: storage/YYYY/MM/DD/<uuid>."""
    ref = created_at or datetime.now()
    base = Path(settings.storage_root)
    return base / f"{ref.year:04d}" / f"{ref.month:02d}" / f"{ref.day:02d}" / audio_uuid


def new_audio_dir() -> tuple[str, Path]:
    """Cria um novo diretório de áudio com UUID, retornando (uuid, caminho)."""
    audio_uuid = str(uuid_lib.uuid4())
    target = audio_dir(audio_uuid)
    target.mkdir(parents=True, exist_ok=False)
    return audio_uuid, target


def write_meta(target_dir: Path, meta: dict) -> None:
    """Grava o arquivo meta.json com metadados complementares."""
    meta_path = target_dir / "meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def read_meta(target_dir: Path) -> dict:
    """Lê o meta.json do diretório, se existir."""
    meta_path = target_dir / "meta.json"
    if not meta_path.exists():
        return {}
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def move_to_trash(audio_uuid: str, created_at: datetime) -> Path | None:
    """Move o diretório do áudio para a lixeira (trash/). Retorna o destino."""
    src = audio_dir(audio_uuid, created_at)
    if not src.exists():
        return None
    ensure_dirs()
    dest = Path(settings.trash_dir) / audio_uuid
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(src), str(dest))
    return dest


def restore_from_trash(audio_uuid: str, created_at: datetime) -> Path | None:
    """Restaura um diretório da lixeira para o local original."""
    trash_item = Path(settings.trash_dir) / audio_uuid
    if not trash_item.exists():
        return None
    dest = audio_dir(audio_uuid, created_at)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(trash_item), str(dest))
    return dest


def purge_trash(max_age_hours: int = 24) -> int:
    """Remove da lixeira itens mais antigos que max_age_hours. Retorna qtd removida."""
    trash = Path(settings.trash_dir)
    if not trash.exists():
        return 0
    import time

    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for item in trash.iterdir():
        try:
            if item.stat().st_mtime < cutoff:
                shutil.rmtree(item)
                removed += 1
        except OSError:
            continue
    return removed
