"""Cliente HTTP do servidor de áudio (httpx)."""
from __future__ import annotations

import json
from pathlib import Path

import httpx


class ApiError(RuntimeError):
    """Erro na comunicação com o servidor."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class AudioApiClient:
    """Encapsula as chamadas HTTP para o servidor."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=120.0)

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------ #
    # Sistema
    # ------------------------------------------------------------------ #

    def health(self) -> dict:
        try:
            r = self._client.get(f"{self.base_url}/api/health")
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            raise ApiError(f"Servidor inacessível: {exc}") from exc

    def processing_types(self) -> list[dict]:
        r = self._client.get(f"{self.base_url}/api/processing-types")
        r.raise_for_status()
        return r.json()

    def supported_formats(self) -> list[str]:
        r = self._client.get(f"{self.base_url}/api/supported-formats")
        r.raise_for_status()
        return r.json().get("extensions", [])

    # ------------------------------------------------------------------ #
    # Upload
    # ------------------------------------------------------------------ #

    def upload_audio(
        self,
        file_path: str | Path,
        processing_type: str,
        processing_params: dict | None = None,
        progress_cb=None,
    ) -> dict:
        """Envia um arquivo de áudio para processamento.

        progress_cb(bytes_sent, total_bytes) é chamado durante o envio.
        """
        path = Path(file_path)
        if not path.exists():
            raise ApiError(f"Arquivo não encontrado: {path}")
        total = path.stat().st_size

        data = {"processing_type": processing_type}
        if processing_params:
            data["processing_params"] = json.dumps(processing_params)

        sent = {"n": 0}

        def _monitor(chunk: bytes):
            sent["n"] += len(chunk)
            if progress_cb:
                progress_cb(sent["n"], total)

        with open(path, "rb") as f:
            try:
                r = self._client.post(
                    f"{self.base_url}/api/audios",
                    files={"file": (path.name, f, "application/octet-stream")},
                    data=data,
                )
            except httpx.HTTPError as exc:
                raise ApiError(f"Falha no upload: {exc}") from exc

        if r.status_code >= 400:
            detail = ""
            try:
                detail = r.json().get("detail", "")
            except Exception:
                detail = r.text
            raise ApiError(f"Erro {r.status_code}: {detail}", status_code=r.status_code)
        return r.json()

    # ------------------------------------------------------------------ #
    # Histórico
    # ------------------------------------------------------------------ #

    def list_audios(self, page: int = 1, page_size: int = 100) -> dict:
        try:
            r = self._client.get(
                f"{self.base_url}/api/audios", params={"page": page, "page_size": page_size}
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            raise ApiError(f"Falha ao listar áudios: {exc}") from exc

    def get_audio(self, audio_id: str) -> dict:
        r = self._client.get(f"{self.base_url}/api/audios/{audio_id}")
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------ #
    # Streaming de mídia
    # ------------------------------------------------------------------ #

    def stream_url(self, audio_id: str, kind: str) -> str:
        """URL para reprodução no player (kind: original|processed)."""
        return f"{self.base_url}/api/audios/{audio_id}/{kind}"

    def download(self, audio_id: str, kind: str, dest: str | Path) -> Path:
        """Baixa um arquivo (original ou processado) para o disco."""
        url = self.stream_url(audio_id, kind)
        dest = Path(dest)
        try:
            with self._client.stream("GET", url) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_bytes(1024 * 256):
                        f.write(chunk)
        except httpx.HTTPError as exc:
            raise ApiError(f"Falha no download: {exc}") from exc
        return dest

    def waveform_url(self, audio_id: str) -> str:
        return f"{self.base_url}/api/audios/{audio_id}/waveform"

    def delete_audio(self, audio_id: str) -> None:
        r = self._client.delete(f"{self.base_url}/api/audios/{audio_id}")
        if r.status_code >= 400:
            raise ApiError(f"Erro ao excluir: {r.text}", status_code=r.status_code)
