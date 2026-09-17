"""Localiza ffmpeg/ffprobe no PATH ou em instalações comuns no Windows."""
from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=4)
def resolve_binary(name: str) -> str:
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
