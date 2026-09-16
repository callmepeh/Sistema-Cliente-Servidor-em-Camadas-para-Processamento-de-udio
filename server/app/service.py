"""Camada de serviço: orquestra o fluxo completo de um áudio.

Fluxo:
    1. Recebe upload e valida extensão.
    2. Gera UUID e cria diretório storage/YYYY/MM/DD/<uuid>/.
    3. Salva o original como audio.{ext}.
    4. Sonda metadados com ffprobe.
    5. Executa o processamento via FFmpeg -> audio_processed.{ext}.
    6. Gera waveform.png do áudio processado.
    7. Grava meta.json (checksums, parâmetros, tamanhos).
    8. Registra tudo no PostgreSQL.
"""
import json
import shutil
import uuid as uuid_lib
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from . import storage
from .config import settings
from .ffmpeg_utils import (
    SUPPORTED_EXTENSIONS,
    FFmpegError,
    extract_checksum,
    generate_waveform,
    get_mime_type,
    is_supported,
    probe_audio,
)
from .models import Audio
from .processing import get_processing_type


async def process_upload(
    db: Session,
    file: UploadFile,
    processing_type: str,
    processing_params: str | None,
) -> Audio:
    """Fluxo completo de upload + processamento + persistência."""
    # 1. Validações
    if not file.filename or not is_supported(file.filename):
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Formato não suportado. Aceitos: {supported}")

    original_name = file.filename
    original_ext = Path(original_name).suffix.lower().lstrip(".")
    mime = get_mime_type(original_name)
    params: dict = {}
    if processing_params:
        try:
            params = json.loads(processing_params)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="processing_params deve ser um JSON válido")

    try:
        ptype = get_processing_type(processing_type)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 2. Cria diretório com UUID
    try:
        audio_uuid, target_dir = storage.new_audio_dir()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao criar diretório: {exc}")

    original_path = target_dir / f"audio.{original_ext}"

    # Extensão do arquivo processado: pode mudar em conversão de formato
    proc_ext = original_ext
    if ptype.key == "convert":
        proc_ext = str(params.get("target_format", "mp3")).lower().lstrip(".")
        if f".{proc_ext}" not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Formato de destino não suportado: {proc_ext}")

    processed_path = target_dir / f"audio_processed.{proc_ext}"

    # 3. Salva o arquivo original
    size_bytes = 0
    try:
        with open(original_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)
                size_bytes += len(chunk)
    except Exception as exc:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {exc}")

    if size_bytes == 0:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Arquivo vazio")
    if size_bytes > settings.max_upload_mb * 1024 * 1024:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise HTTPException(status_code=413, detail="Arquivo excede o limite de upload")

    try:
        # 4. Metadados via ffprobe
        try:
            meta_probe = probe_audio(original_path)
        except FFmpegError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        # 5. Processamento FFmpeg
        ffmpeg_args = ptype.build_args(original_path, processed_path, params)
        try:
            run_ffmpeg_safely(ffmpeg_args)
        except FFmpegError as exc:
            raise HTTPException(status_code=422, detail=f"Falha no processamento: {exc}")

        # 6. Waveform
        try:
            generate_waveform(original_path, target_dir / "waveform.png")
        except FFmpegError:
            pass  # não falha o upload por causa da waveform

        # 7. meta.json
        created_at = datetime.now()
        meta = {
            "uuid": audio_uuid,
            "original_name": original_name,
            "original_ext": original_ext,
            "processed_ext": proc_ext,
            "mime_type": mime,
            "size_bytes_original": size_bytes,
            "size_bytes_processed": processed_path.stat().st_size if processed_path.exists() else None,
            "checksum_original_sha256": extract_checksum(original_path),
            "checksum_processed_sha256": extract_checksum(processed_path) if processed_path.exists() else None,
            "duration_sec": meta_probe.get("duration_sec"),
            "sample_rate": meta_probe.get("sample_rate"),
            "channels": meta_probe.get("channels"),
            "bitrate": meta_probe.get("bitrate"),
            "processing_type": ptype.key,
            "processing_params": params,
            "created_at": created_at.isoformat(),
        }
        storage.write_meta(target_dir, meta)

        # 8. Banco de dados
        audio = Audio(
            id=uuid_lib.UUID(audio_uuid),
            original_name=original_name,
            original_ext=original_ext,
            mime_type=mime,
            size_bytes=size_bytes,
            duration_sec=meta_probe["duration_sec"],
            sample_rate=meta_probe.get("sample_rate"),
            channels=meta_probe.get("channels"),
            bitrate=meta_probe.get("bitrate"),
            processing_type=ptype.key,
            processing_params=params,
            created_at=created_at,
            path_original=str(original_path),
            path_processed=str(processed_path),
        )
        db.add(audio)
        db.commit()
        db.refresh(audio)
        return audio

    except Exception:
        # Em caso de falha, move o diretório para a trash em vez de apagar
        storage.move_to_trash(audio_uuid, datetime.now())
        raise


def run_ffmpeg_safely(args: list[str]) -> None:
    """Wrapper para execução do FFmpeg (mantém o import local)."""
    from .ffmpeg_utils import run_ffmpeg

    run_ffmpeg(args)


def build_urls(audio: Audio) -> dict:
    """Constrói as URLs de download/reprodução para a resposta da API."""
    return {
        "original_url": f"/api/audios/{audio.id}/original",
        "processed_url": f"/api/audios/{audio.id}/processed",
        "waveform_url": f"/api/audios/{audio.id}/waveform",
    }


def delete_audio(db: Session, audio_id: str) -> Audio:
    """Marca um áudio para exclusão: move arquivos para trash/ e remove do banco."""
    audio = db.get(Audio, uuid_lib.UUID(audio_id))
    if audio is None:
        raise HTTPException(status_code=404, detail="Áudio não encontrado")

    storage.move_to_trash(audio_id, audio.created_at)
    db.delete(audio)
    db.commit()
    return audio
