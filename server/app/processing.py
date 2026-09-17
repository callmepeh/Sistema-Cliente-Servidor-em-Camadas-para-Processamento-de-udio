"""Tipos de processamento de áudio suportados (via FFmpeg)."""
from dataclasses import dataclass, field
from pathlib import Path

from .ffmpeg_utils import FFmpegError, probe_audio


@dataclass
class ProcessingType:
    key: str
    label: str
    description: str
    default_params: dict = field(default_factory=dict)

    def build_args(self, input_path: Path, output_path: Path, params: dict) -> list[str]:
        """Constrói os argumentos ffmpeg para este processamento."""
        raise NotImplementedError


@dataclass
class Normalize(ProcessingType):
    def __init__(self):
        super().__init__(
            key="normalize",
            label="Normalização de volume",
            description="Ajusta o volume para um nível padrão usando o filtro loudnorm (EBU R128).",
            default_params={"target_i": -16.0, "target_tp": -1.5},
        )

    def build_args(self, input_path: Path, output_path: Path, params: dict) -> list[str]:
        target_i = float(params.get("target_i", self.default_params["target_i"]))
        target_tp = float(params.get("target_tp", self.default_params["target_tp"]))
        return [
            "-i", str(input_path),
            "-af", f"loudnorm=I={target_i}:TP={target_tp}",
            str(output_path),
        ]


@dataclass
class ToMono(ProcessingType):
    def __init__(self):
        super().__init__(
            key="mono",
            label="Conversão para mono",
            description="Converte o áudio para um único canal (mono).",
        )

    def build_args(self, input_path: Path, output_path: Path, params: dict) -> list[str]:
        return [
            "-i", str(input_path),
            "-ac", "1",
            str(output_path),
        ]


@dataclass
class Speed(ProcessingType):
    def __init__(self):
        super().__init__(
            key="speed",
            label="Alteração de velocidade",
            description="Altera a velocidade de reprodução (ex.: 1.5 = 50% mais rápido).",
            default_params={"factor": 1.5, "preserving_pitch": True},
        )

    def build_args(self, input_path: Path, output_path: Path, params: dict) -> list[str]:
        factor = float(params.get("factor", 1.5))
        if not 0.25 <= factor <= 4.0:
            raise FFmpegError("Fator de velocidade deve estar entre 0.25 e 4.0")
        keep_pitch = bool(params.get("preserving_pitch", True))
        if keep_pitch:
            af = _atempo_chain(factor)
        else:
            sr = probe_audio(input_path).get("sample_rate") or 44100
            af = f"asetrate={sr}*{factor},aresample={sr}"
        return [
            "-i", str(input_path),
            "-af", af,
            str(output_path),
        ]


def _atempo_chain(factor: float) -> str:
    """atempo só aceita 0.5–2.0; encadeia filtros para fatores fora dessa faixa."""
    parts: list[str] = []
    remaining = factor
    while remaining > 2.0 + 1e-9:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5 - 1e-9:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining}")
    return ",".join(parts)


@dataclass
class BitrateReduction(ProcessingType):
    def __init__(self):
        super().__init__(
            key="bitrate",
            label="Redução da taxa de bits",
            description="Reencoda o áudio com uma taxa de bits menor.",
            default_params={"bitrate": "64k"},
        )

    def build_args(self, input_path: Path, output_path: Path, params: dict) -> list[str]:
        bitrate = str(params.get("bitrate", self.default_params["bitrate"]))
        return [
            "-i", str(input_path),
            "-b:a", bitrate,
            str(output_path),
        ]


@dataclass
class ConvertFormat(ProcessingType):
    def __init__(self):
        super().__init__(
            key="convert",
            label="Conversão de formato",
            description="Converte o áudio para outro formato (ex.: WAV → MP3).",
            default_params={"target_format": "mp3", "bitrate": "192k"},
        )

    def build_args(self, input_path: Path, output_path: Path, params: dict) -> list[str]:
        bitrate = str(params.get("bitrate", self.default_params["bitrate"]))
        return [
            "-i", str(input_path),
            "-b:a", bitrate,
            str(output_path),
        ]


# Registro central de processamentos disponíveis
PROCESSING_TYPES: dict[str, ProcessingType] = {
    p.key: p
    for p in (
        Normalize(),
        ToMono(),
        Speed(),
        BitrateReduction(),
        ConvertFormat(),
    )
}


def get_processing_type(key: str) -> ProcessingType:
    if key not in PROCESSING_TYPES:
        raise KeyError(
            f"Processamento desconhecido: '{key}'. "
            f"Disponíveis: {', '.join(PROCESSING_TYPES.keys())}"
        )
    return PROCESSING_TYPES[key]
