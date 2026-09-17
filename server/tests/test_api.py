"""Testes da API REST (usando SQLite em memória)."""
from pathlib import Path

import pytest


@pytest.mark.usefixtures("client")
class TestSystem:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"
        assert body["ffmpeg"] == "ok"

    def test_processing_types(self, client):
        resp = client.get("/api/processing-types")
        assert resp.status_code == 200
        keys = {item["key"] for item in resp.json()}
        assert keys == {"normalize", "mono", "speed", "bitrate", "convert"}

    def test_supported_formats(self, client):
        resp = client.get("/api/supported-formats")
        assert resp.status_code == 200
        assert ".wav" in resp.json()["extensions"]

    def test_root_redirects_to_web(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code in (301, 302, 307)

    def test_swagger_docs(self, client):
        resp = client.get("/api/docs")
        assert resp.status_code == 200


@pytest.mark.usefixtures("client")
class TestUploadAndProcessing:
    def test_upload_normalize(self, client, sample_wav):
        with open(sample_wav, "rb") as f:
            resp = client.post(
                "/api/audios",
                files={"file": ("sample.wav", f, "audio/wav")},
                data={"processing_type": "normalize"},
            )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["original_name"] == "sample.wav"
        assert body["processing_type"] == "normalize"
        assert body["duration_sec"] > 0
        assert body["original_url"].startswith("/api/audios/")
        assert body["waveform_url"].startswith("/api/audios/")

        # limpa diretório gerado
        from server.app import storage
        from datetime import datetime
        shutil_rmtree = __import__("shutil").rmtree
        target = storage.audio_dir(body["id"])
        shutil_rmtree(target, ignore_errors=True)

    @pytest.mark.parametrize("ptype", ["mono", "speed", "bitrate", "convert"])
    def test_upload_all_processing_types(self, client, sample_wav, ptype):
        with open(sample_wav, "rb") as f:
            resp = client.post(
                "/api/audios",
                files={"file": ("sample.wav", f, "audio/wav")},
                data={"processing_type": ptype, "processing_params": "{}"},
            )
        assert resp.status_code == 201, resp.text

        from server.app import storage
        from datetime import datetime
        shutil_rmtree = __import__("shutil").rmtree
        target = storage.audio_dir(resp.json()["id"])
        shutil_rmtree(target, ignore_errors=True)

    def test_processed_mime_after_convert(self, client, sample_wav):
        with open(sample_wav, "rb") as f:
            resp = client.post(
                "/api/audios",
                files={"file": ("sample.wav", f, "audio/wav")},
                data={
                    "processing_type": "convert",
                    "processing_params": '{"target_format": "mp3"}',
                },
            )
        assert resp.status_code == 201, resp.text
        audio_id = resp.json()["id"]
        media = client.get(f"/api/audios/{audio_id}/processed")
        assert media.status_code == 200
        assert media.headers["content-type"].startswith("audio/mpeg")

        from server.app import storage
        shutil_rmtree = __import__("shutil").rmtree
        shutil_rmtree(storage.audio_dir(audio_id), ignore_errors=True)

    def test_upload_invalid_processing_type(self, client, sample_wav):
        with open(sample_wav, "rb") as f:
            resp = client.post(
                "/api/audios",
                files={"file": ("sample.wav", f, "audio/wav")},
                data={"processing_type": "inexistente"},
            )
        assert resp.status_code in (400, 422)

    def test_upload_unsupported_extension(self, client, tmp_path):
        fake = tmp_path / "nota.txt"
        fake.write_text("isto não é um áudio")
        with open(fake, "rb") as f:
            resp = client.post(
                "/api/audios",
                files={"file": ("nota.txt", f, "text/plain")},
                data={"processing_type": "normalize"},
            )
        assert resp.status_code == 400

    def test_upload_empty_file(self, client, tmp_path):
        empty = tmp_path / "vazio.wav"
        empty.write_bytes(b"")
        with open(empty, "rb") as f:
            resp = client.post(
                "/api/audios",
                files={"file": ("vazio.wav", f, "audio/wav")},
                data={"processing_type": "normalize"},
            )
        assert resp.status_code == 400


@pytest.mark.usefixtures("client")
class TestHistoryAndMedia:
    def test_history_lists_records(self, client, audio_record):
        resp = client.get("/api/audios")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        ids = [item["id"] for item in body["items"]]
        assert str(audio_record.id) in ids

    def test_get_audio_by_id(self, client, audio_record):
        resp = client.get(f"/api/audios/{audio_record.id}")
        assert resp.status_code == 200
        assert resp.json()["original_name"] == "sample.wav"

    def test_get_audio_invalid_uuid(self, client):
        resp = client.get("/api/audios/nao-e-uuid")
        assert resp.status_code == 400

    def test_get_audio_not_found(self, client):
        resp = client.get("/api/audios/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_download_original(self, client, audio_record):
        resp = client.get(f"/api/audios/{audio_record.id}/original")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("audio/wav")

    def test_download_processed(self, client, audio_record):
        resp = client.get(f"/api/audios/{audio_record.id}/processed")
        assert resp.status_code == 200

    def test_waveform(self, client, audio_record):
        resp = client.get(f"/api/audios/{audio_record.id}/waveform")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    def test_meta(self, client, audio_record):
        from server.app import storage

        target = storage.audio_dir(str(audio_record.id))
        storage.write_meta(target, {"uuid": str(audio_record.id), "checksum_original_sha256": "abc"})
        resp = client.get(f"/api/audios/{audio_record.id}/meta")
        assert resp.status_code == 200
        assert resp.json()["uuid"] == str(audio_record.id)


@pytest.mark.usefixtures("client")
class TestDelete:
    def test_delete_moves_to_trash(self, client, audio_record):
        from server.app import storage
        from server.app.config import settings
        from pathlib import Path

        resp = client.delete(f"/api/audios/{audio_record.id}")
        assert resp.status_code == 200

        trash_item = Path(settings.trash_dir) / str(audio_record.id)
        assert trash_item.exists(), "Diretório deveria ter sido movido para trash/"

        # limpa
        import shutil
        shutil.rmtree(trash_item, ignore_errors=True)


def test_atempo_chain_covers_ffmpeg_limits():
    from server.app.processing import _atempo_chain

    assert _atempo_chain(1.5) == "atempo=1.5"
    assert _atempo_chain(4.0) == "atempo=2.0,atempo=2.0"
    assert _atempo_chain(0.25) == "atempo=0.5,atempo=0.5"
