"""Schemas Pydantic da API."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProcessingInfo(BaseModel):
    key: str
    label: str
    description: str
    default_params: dict[str, Any]


class AudioUploadResponse(BaseModel):
    id: str = Field(examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"])
    original_name: str
    original_ext: str
    mime_type: str
    size_bytes: int
    duration_sec: float
    sample_rate: int | None
    channels: int | None
    bitrate: int | None
    processing_type: str
    processing_params: dict[str, Any] | None
    created_at: datetime
    path_original: str
    path_processed: str
    original_url: str
    processed_url: str
    waveform_url: str


class AudioItem(AudioUploadResponse):
    pass


class HistoryResponse(BaseModel):
    total: int
    items: list[AudioItem]


class Message(BaseModel):
    message: str
    id: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    ffmpeg: str
