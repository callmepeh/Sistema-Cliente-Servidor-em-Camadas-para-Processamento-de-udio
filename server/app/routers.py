"""Rotas da API REST do servidor."""
import uuid as uuid_lib
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import service
from .database import get_db
from .ffmpeg_utils import SUPPORTED_EXTENSIONS
from .models import Audio
from .processing import PROCESSING_TYPES
from .schemas import (
    AudioItem,
    AudioUploadResponse,
    HealthResponse,
    HistoryResponse,
    Message,
    ProcessingInfo,
)

router = APIRouter()


@router.get("/", include_in_schema=False, tags=["Sistema"])
def root():
    """Redireciona a raiz para a interface web."""
    return RedirectResponse(url="/web/index.html")


@router.get("/health", response_model=HealthResponse, tags=["Sistema"])
def health(db: Session = Depends(get_db)):
    """Verifica o status do servidor, banco de dados e FFmpeg."""
    import subprocess

    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "erro"

    ffmpeg_status = "ok"
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=10)
    except Exception:
        ffmpeg_status = "erro"

    return HealthResponse(status="ok", database=db_status, ffmpeg=ffmpeg_status)


@router.get("/processing-types", response_model=list[ProcessingInfo], tags=["Sistema"])
def list_processing_types():
    """Lista os tipos de processamento disponíveis."""
    return [
        ProcessingInfo(
            key=p.key, label=p.label, description=p.description, default_params=p.default_params
        )
        for p in PROCESSING_TYPES.values()
    ]


@router.get("/supported-formats", tags=["Sistema"])
def supported_formats():
    """Formatos de áudio aceitos no upload."""
    return {"extensions": sorted(SUPPORTED_EXTENSIONS)}


@router.post("/audios", response_model=AudioUploadResponse, status_code=201, tags=["Áudios"])
async def upload_audio(
    db: Session = Depends(get_db),
    file: UploadFile = File(..., description="Arquivo de áudio"),
    processing_type: str = Form(
        ..., description="normalize | mono | speed | bitrate | convert"
    ),
    processing_params: str | None = Form(None, description='Parâmetros JSON, ex.: {"factor": 1.5}'),
):
    """Recebe um áudio, processa com FFmpeg, salva em disco e registra no PostgreSQL."""
    audio = await service.process_upload(db, file, processing_type, processing_params)
    return AudioUploadResponse(**audio.to_dict(), **service.build_urls(audio))


@router.get("/audios", response_model=HistoryResponse, tags=["Áudios"])
def list_audios(
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    """Histórico paginado de áudios enviados."""
    if page < 1:
        page = 1
    page_size = max(1, min(page_size, 200))

    query = db.query(Audio).order_by(Audio.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [AudioItem(**a.to_dict(), **service.build_urls(a)) for a in rows]
    return HistoryResponse(total=total, items=items)


def _get_audio_or_404(db: Session, audio_id: str) -> Audio:
    try:
        audio_uuid = uuid_lib.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID inválido (esperado um UUID)")
    audio = db.get(Audio, audio_uuid)
    if audio is None:
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    return audio


@router.get("/audios/{audio_id}", response_model=AudioItem, tags=["Áudios"])
def get_audio(audio_id: str, db: Session = Depends(get_db)):
    """Detalhes de um áudio específico."""
    audio = _get_audio_or_404(db, audio_id)
    return AudioItem(**audio.to_dict(), **service.build_urls(audio))


@router.get("/audios/{audio_id}/original", tags=["Áudios"])
def download_original(audio_id: str, db: Session = Depends(get_db)):
    """Baixa/reproduz o arquivo original."""
    audio = _get_audio_or_404(db, audio_id)
    path = Path(audio.path_original)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo original não encontrado em disco")
    return FileResponse(path, media_type=audio.mime_type, filename=path.name)


@router.get("/audios/{audio_id}/processed", tags=["Áudios"])
def download_processed(audio_id: str, db: Session = Depends(get_db)):
    """Baixa/reproduz o arquivo processado."""
    audio = _get_audio_or_404(db, audio_id)
    path = Path(audio.path_processed)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo processado não encontrado em disco")
    return FileResponse(path, media_type=audio.mime_type, filename=path.name)


@router.get("/audios/{audio_id}/waveform", tags=["Áudios"])
def download_waveform(audio_id: str, db: Session = Depends(get_db)):
    """Retorna a imagem waveform.png do áudio."""
    audio = _get_audio_or_404(db, audio_id)
    path = Path(audio.path_original).parent / "waveform.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Waveform não encontrada")
    return FileResponse(path, media_type="image/png", filename="waveform.png")


@router.get("/audios/{audio_id}/meta", tags=["Áudios"])
def download_meta(audio_id: str, db: Session = Depends(get_db)):
    """Retorna o conteúdo do meta.json do áudio."""
    audio = _get_audio_or_404(db, audio_id)
    from . import storage

    meta = storage.read_meta(Path(audio.path_original).parent)
    if not meta:
        raise HTTPException(status_code=404, detail="meta.json não encontrado")
    return meta


@router.delete("/audios/{audio_id}", response_model=Message, tags=["Áudios"])
def delete_audio(audio_id: str, db: Session = Depends(get_db)):
    """Move os arquivos do áudio para trash/ e remove o registro do banco."""
    audio = _get_audio_or_404(db, audio_id)
    service.delete_audio(db, audio_id)
    return Message(message="Áudio movido para a lixeira (trash/)", id=audio_id)


@router.post("/trash/purge", tags=["Sistema"])
def purge_trash(max_age_hours: int = 24):
    """Remove definitivamente itens da trash/ mais antigos que max_age_hours."""
    from . import storage

    removed = storage.purge_trash(max_age_hours)
    return {"removed": removed}
