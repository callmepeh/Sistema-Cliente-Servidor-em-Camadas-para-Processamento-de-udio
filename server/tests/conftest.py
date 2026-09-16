"""Fixtures dos testes do servidor.

Usa SQLite em memória para isolar os testes do PostgreSQL real.
"""
import os

# Precisa ser definido antes de importar qualquer módulo do app
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.app.database import Base, get_db
from server.app.main import app
from server.app.models import Audio  # noqa: F401  (registra os modelos)

TEST_DB_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    """Sessão isolada por teste (rollback ao final)."""
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(test_engine):
    """Cliente HTTP de testes com override da dependência do banco."""
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_wav(tmp_path):
    """Gera um WAV de teste de ~2 segundos usando FFmpeg."""
    import subprocess

    path = tmp_path / "sample.wav"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-ar", "44100", "-ac", "2",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


@pytest.fixture()
def audio_record(db_session, sample_wav):
    """Cria um registro de áudio válido (sem passar pelo fluxo de upload)."""
    import shutil
    import uuid as uuid_lib
    from datetime import datetime
    from pathlib import Path

    from server.app import storage

    audio_uuid = str(uuid_lib.uuid4())
    target = storage.audio_dir(audio_uuid)
    target.mkdir(parents=True, exist_ok=True)

    orig = target / "audio.wav"
    shutil.copy(sample_wav, orig)

    from server.app.ffmpeg_utils import generate_waveform

    try:
        generate_waveform(orig, target / "waveform.png")
    except Exception:
        pass

    record = Audio(
        id=uuid_lib.UUID(audio_uuid),
        original_name="sample.wav",
        original_ext="wav",
        mime_type="audio/wav",
        size_bytes=orig.stat().st_size,
        duration_sec=2.0,
        sample_rate=44100,
        channels=2,
        bitrate=1411000,
        processing_type="normalize",
        processing_params={},
        created_at=datetime.now(),
        path_original=str(orig),
        path_processed=str(orig),
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    yield record

    shutil.rmtree(target, ignore_errors=True)
