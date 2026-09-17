"""Utilidades de FFmpeg: sondagem de metadados e execução de filtros."""
import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

# Extensões e MIME types aceitos
SUPPORTED_EXTENSIONS = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".opus": "audio/opus",
    ".wma": "audio/x-ms-wma",
}


@lru_cache(maxsize=4)
def resolve_binary(name: str) -> str:
    """Localiza ffmpeg/ffprobe no PATH, em variáveis de ambiente ou no WinGet."""
    found = shutil.which(name)
    if found:
        return found

    env_value = os.environ.get(f"{name.upper()}_PATH") or os.environ.get("FFMPEG_BIN")
    if env_value:
        p = Path(env_value)
        if p.is_dir():
            candidate = p / (f"{name}.exe" if os.name == "nt" else name)
            if candidate.exists():
                return str(candidate)
        elif p.exists():
            return str(p)

    localapp = os.environ.get("LOCALAPPDATA", "")
    if localapp:
        packages = Path(localapp) / "Microsoft" / "WinGet" / "Packages"
        if packages.is_dir():
            exe_name = f"{name}.exe" if os.name == "nt" else name
            for pkg in packages.glob("Gyan.FFmpeg*"):
                matches = sorted(pkg.glob(f"ffmpeg-*/bin/{exe_name}"))
                if matches:
                    return str(matches[0])
    return name


def ffmpeg_bin() -> str:
    return resolve_binary("ffmpeg")


def ffprobe_bin() -> str:
    return resolve_binary("ffprobe")


class FFmpegError(RuntimeError):
    """Erro ao executar o FFmpeg/ffprobe."""


def probe_audio(path: str | Path) -> dict:
    """Extrai metadados do áudio via ffprobe (JSON)."""
    cmd = [
        ffprobe_bin(),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
    except subprocess.CalledProcessError as exc:
        raise FFmpegError(f"ffprobe falhou: {exc.stderr.strip()}") from exc
    except FileNotFoundError as exc:
        raise FFmpegError("ffprobe não encontrado. Instale o FFmpeg.") from exc

    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if audio_stream is None:
        raise FFmpegError("Arquivo não contém stream de áudio válido.")

    return {
        "duration_sec": float(fmt.get("duration", 0.0)),
        "sample_rate": int(audio_stream.get("sample_rate", 0)) or None,
        "channels": int(audio_stream.get("channels", 0)) or None,
        "bitrate": int(fmt.get("bit_rate", 0)) or int(audio_stream.get("bit_rate", 0)) or None,
        "codec": audio_stream.get("codec_name"),
    }


def run_ffmpeg(args: list[str], timeout: int = 300) -> None:
    """Executa um comando ffmpeg e lança erro em caso de falha."""
    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", *args]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        raise FFmpegError(f"ffmpeg falhou: {exc.stderr.strip()}") from exc
    except FileNotFoundError as exc:
        raise FFmpegError("ffmpeg não encontrado. Instale o FFmpeg.") from exc


def generate_waveform(audio_path: str | Path, output_path: str | Path) -> None:
    """Gera uma imagem PNG da forma de onda do áudio usando FFmpeg."""
    out = str(output_path)
    args = [
        "-i", str(audio_path),
        "-filter_complex",
        "showwavespic=s=960x240:colors=#4f8cff|#a05cff",
        "-frames:v", "1",
        out,
    ]
    run_ffmpeg(args, timeout=120)


def extract_checksum(path: str | Path) -> str:
    """Calcula checksum SHA-256 do arquivo."""
    import hashlib

    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def is_supported(filename: str) -> bool:
    """Verifica se a extensão do arquivo é suportada."""
    from pathlib import Path as _P

    return _P(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def get_mime_type(filename: str) -> str:
    """Retorna o MIME type baseado na extensão."""
    return SUPPORTED_EXTENSIONS.get(_ext(filename), "application/octet-stream")


def _ext(filename: str) -> str:
    from pathlib import Path as _P

    return _P(filename).suffix.lower()
