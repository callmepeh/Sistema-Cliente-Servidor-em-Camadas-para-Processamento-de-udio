"""Modelo ORM da tabela `audios`."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

# JSONB no PostgreSQL; JSON comum em outros bancos (ex.: SQLite nos testes)
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class Audio(Base):
    __tablename__ = "audios"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_ext: Mapped[str] = mapped_column(String(10), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_sec: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_type: Mapped[str] = mapped_column(String(50), nullable=False)
    processing_params: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    path_original: Mapped[str] = mapped_column(Text, nullable=False)
    path_processed: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("idx_audios_created_at", created_at.desc()),
        Index("idx_audios_processing", processing_type),
    )

    def to_dict(self) -> dict:
        """Representação serializável do registro."""
        return {
            "id": str(self.id),
            "original_name": self.original_name,
            "original_ext": self.original_ext,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "duration_sec": float(self.duration_sec) if self.duration_sec is not None else None,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bitrate": self.bitrate,
            "processing_type": self.processing_type,
            "processing_params": self.processing_params,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "path_original": self.path_original,
            "path_processed": self.path_processed,
        }
