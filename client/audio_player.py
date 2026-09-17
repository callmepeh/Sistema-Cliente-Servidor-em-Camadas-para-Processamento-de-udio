"""Player de áudio com QMediaPlayer e widget de waveform (desenhada localmente)."""
from __future__ import annotations

import array
import subprocess
import wave
from pathlib import Path
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)


def extract_pcm(source: str | Path, tmp_wav: Path) -> bool:
    """Converte qualquer áudio para PCM WAV mono 8kHz para análise de waveform."""
    try:
        from ffmpeg_path import resolve_binary
    except ImportError:
        from .ffmpeg_path import resolve_binary

    try:
        subprocess.run(
            [
                resolve_binary("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(source),
                "-ac", "1", "-ar", "8000",
                "-c:a", "pcm_s16le",
                str(tmp_wav),
            ],
            check=True, capture_output=True, timeout=60,
        )
        return True
    except Exception:
        return False


def read_wav_peaks(path: Path, buckets: int = 600) -> list[float]:
    """Lê um WAV PCM e retorna picos normalizados por bucket."""
    try:
        with wave.open(str(path), "rb") as w:
            n = w.getnframes()
            if n == 0:
                return [0.0] * buckets
            raw = w.readframes(n)
            ch = w.getnchannels()
            sw = w.getsampwidth()
            if sw != 2:
                return [0.0] * buckets
            samples = array.array("h")
            samples.frombytes(raw)
            if ch > 1:
                samples = samples[::ch]
            step = max(1, len(samples) // buckets)
            peaks = []
            for i in range(0, len(samples), step):
                chunk = samples[i:i + step]
                if chunk:
                    peaks.append(max(abs(s) for s in chunk) / 32768.0)
            if not peaks:
                return [0.0] * buckets
            m = max(peaks) or 1.0
            return [p / m for p in peaks]
    except Exception:
        return [0.0] * buckets


class WaveformCanvas(QWidget):
    """Widget que desenha a forma de onda e a posição atual."""

    seekRequested = Signal(float)  # fração 0..1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks: list[float] = []
        self.position_frac: float = 0.0
        self.setMinimumHeight(70)

    def set_peaks(self, peaks: list[float]) -> None:
        self.peaks = peaks
        self.update()

    def set_position(self, frac: float) -> None:
        self.position_frac = max(0.0, min(1.0, frac))
        self.update()

    def mousePressEvent(self, event):
        if self.peaks:
            frac = event.position().x() / max(1, self.width())
            self.seekRequested.emit(frac)

    def paintEvent(self, event):
        if not self.peaks:
            from PySide6.QtGui import QFont
            painter = QPainter(self)
            painter.setPen(QPen(QColor("#8892a8")))
            painter.drawText(self.rect(), Qt.AlignCenter, "Sem waveform — reproduza um arquivo local")
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        mid = h / 2

        # fundo
        painter.fillRect(0, 0, w, h, QColor("#0f1526"))
        played = QColor("#4f8cff")
        pending = QColor("#2a3a5c")

        n = len(self.peaks)
        bar_w = max(1, w // n - 1)
        pos_x = int(self.position_frac * w)

        for i, p in enumerate(self.peaks):
            x = int(i * w / n)
            bar_h = max(2, int(p * (h - 8)))
            color = played if x <= pos_x else pending
            painter.fillRect(x, int(mid - bar_h / 2), bar_w, bar_h, color)


class AudioPlayerWidget(QWidget):
    """Widget de player: waveform + play/pause/stop + slider de progresso."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_out = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_out)
        self._audio_out.setVolume(0.9)

        self._temp_wav: Path | None = None
        self._current_label = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.waveform = WaveformCanvas()
        layout.addWidget(self.waveform)

        controls = QHBoxLayout()
        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.label_time = QLabel("0:00 / 0:00")

        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_stop)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.label_time)
        layout.addLayout(controls)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #8892a8;")
        layout.addWidget(self.status)

        # Conexões
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_stop.clicked.connect(self.stop)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        self.waveform.seekRequested.connect(self._seek_frac)
        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.playbackStateChanged.connect(self._on_state)
        self._player.errorOccurred.connect(self._on_error)

    # ---------------- API pública ---------------- #

    def play_file(self, source: str, label: str = "") -> None:
        """Reproduz uma URL (http://...) ou arquivo local."""
        self.stop()
        self._current_label = label or source
        self.status.setText(f"Carregando: {self._current_label}")
        self.status.setStyleSheet("color: #8892a8;")
        self.waveform.set_peaks([])

        local = Path(source)
        if local.exists():
            self._player.setSource(QUrl.fromLocalFile(str(local.resolve())))
            self._render_local_waveform(local)
        else:
            self._player.setSource(QUrl(source))
        self._player.play()

    def play_local_file(self, path: str | Path, label: str = "") -> None:
        self.play_file(Path(path).resolve().as_uri(), label)

    def stop(self) -> None:
        self._player.stop()
        self.slider.setValue(0)
        self.waveform.set_position(0)

    # ---------------- Internos ---------------- #

    def _render_local_waveform(self, path: Path) -> None:
        import tempfile

        tmp = Path(tempfile.gettempdir()) / f"wf_{path.stem}_{path.stat().st_size}.wav"
        if not tmp.exists():
            if not extract_pcm(path, tmp):
                return
        self._temp_wav = tmp
        self.waveform.set_peaks(read_wav_peaks(tmp))

    def toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_slider_moved(self, value: int) -> None:
        if self._player.duration() > 0:
            self._player.setPosition(int(value / 1000 * self._player.duration()))

    def _seek_frac(self, frac: float) -> None:
        if self._player.duration() > 0:
            self._player.setPosition(int(frac * self._player.duration()))

    def _on_position(self, pos: int) -> None:
        dur = self._player.duration()
        if dur > 0:
            frac = pos / dur
            self.slider.blockSignals(True)
            self.slider.setValue(int(frac * 1000))
            self.slider.blockSignals(False)
            self.waveform.set_position(frac)
            self.label_time.setText(f"{self._fmt(pos)} / {self._fmt(dur)}")

    def _on_duration(self, dur: int) -> None:
        if dur > 0:
            self.label_time.setText(f"0:00 / {self._fmt(dur)}")
            self.status.setText(f"Reproduzindo: {self._current_label}")

    def _on_state(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        icon = QStyle.StandardPixmap.SP_MediaPause if playing else QStyle.StandardPixmap.SP_MediaPlay
        self.btn_play.setIcon(self.style().standardIcon(icon))

    def _on_error(self, err, msg: str) -> None:
        if err != QMediaPlayer.Error.NoError:
            self.status.setText(f"Erro no player: {msg or 'desconhecido'}")
            self.status.setStyleSheet("color: #e05252;")

    @staticmethod
    def _fmt(ms: int) -> str:
        s = int(ms / 1000)
        return f"{s // 60}:{s % 60:02d}"
