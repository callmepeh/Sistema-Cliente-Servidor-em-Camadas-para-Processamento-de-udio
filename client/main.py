"""Janela principal do cliente gráfico (PySide6)."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import sys

_CLIENT_DIR = Path(__file__).resolve().parent
if str(_CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CLIENT_DIR))

from api_client import ApiError, AudioApiClient
from audio_player import AudioPlayerWidget
from env_utils import load_env
from ffmpeg_path import resolve_binary

load_env()

DEFAULT_SERVER = os.environ.get("BASE_URL", "http://127.0.0.1:8000")

PARAM_HINTS = {
    "normalize": '{"target_i": -16.0, "target_tp": -1.5}',
    "mono": "{}",
    "speed": '{"factor": 1.5, "preserving_pitch": true}',
    "bitrate": '{"bitrate": "64k"}',
    "convert": '{"target_format": "mp3", "bitrate": "192k"}',
}


class UploadWorker(QThread):
    """Executa o upload em background para não travar a GUI."""

    finished_ok = Signal(dict)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, api: AudioApiClient, file_path: str, processing: str, params: dict | None):
        super().__init__()
        self.api = api
        self.file_path = file_path
        self.processing = processing
        self.params = params

    def run(self):
        try:
            result = self.api.upload_audio(
                self.file_path,
                self.processing,
                self.params,
                progress_cb=lambda sent, total: self.progress.emit(sent, total),
            )
            self.finished_ok.emit(result)
        except ApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Erro inesperado: {exc}")


class HistoryWorker(QThread):
    """Busca o histórico em background."""

    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, api: AudioApiClient):
        super().__init__()
        self.api = api

    def run(self):
        try:
            self.finished_ok.emit(self.api.list_audios())
        except ApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Erro inesperado: {exc}")


class FileWorker(QThread):
    """Baixa original/processado em background para o cache local."""

    finished_ok = Signal(str, str)
    failed = Signal(str)

    def __init__(self, api: AudioApiClient, audio_id: str, kind: str, dest: str, label: str):
        super().__init__()
        self.api = api
        self.audio_id = audio_id
        self.kind = kind
        self.dest = dest
        self.label = label

    def run(self):
        try:
            dest = Path(self.dest)
            if not dest.exists() or dest.stat().st_size == 0:
                self.api.download(self.audio_id, self.kind, dest)
            self.finished_ok.emit(str(dest), self.label)
        except ApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Erro inesperado: {exc}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cliente de Áudio — Sistema Cliente/Servidor")
        self.resize(1100, 720)

        self.api: AudioApiClient | None = None
        self.upload_worker: UploadWorker | None = None
        self.history_worker: HistoryWorker | None = None
        self.file_worker: FileWorker | None = None
        self.current_record: dict | None = None
        self._temp_dir = Path(tempfile.gettempdir()) / "audio_client_cache"
        self._temp_dir.mkdir(exist_ok=True)

        self._build_menu()
        self._build_ui()
        self.set_server_url(DEFAULT_SERVER)

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #

    def _build_menu(self):
        menu = self.menuBar().addMenu("&Servidor")
        act_settings = QAction("&Conectar a outro servidor...", self)
        act_settings.triggered.connect(self._ask_server_url)
        menu.addAction(act_settings)

        act_refresh = QAction("&Atualizar histórico", self)
        act_refresh.setShortcut("F5")
        act_refresh.triggered.connect(self.refresh_history)
        menu.addAction(act_refresh)

        about = self.menuBar().addMenu("&Ajuda")
        act_about = QAction("&Sobre", self)
        act_about.triggered.connect(self._show_about)
        about.addAction(act_about)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ----- Conexão ----- #
        conn_box = QGroupBox("Servidor")
        conn_layout = QHBoxLayout(conn_box)
        self.txt_url = QLineEdit(DEFAULT_SERVER)
        self.btn_connect = QPushButton("Conectar")
        self.lbl_status = QLabel("⚫ Desconectado")
        self.lbl_status.setStyleSheet("color: #888;")
        conn_layout.addWidget(QLabel("URL:"))
        conn_layout.addWidget(self.txt_url, 1)
        conn_layout.addWidget(self.btn_connect)
        conn_layout.addWidget(self.lbl_status)
        root.addWidget(conn_box)

        # ----- Splitter principal ----- #
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # ================= Coluna esquerda: envio ================= #
        left = QWidget()
        left_layout = QVBoxLayout(left)

        # Seleção de arquivo
        file_group = QGroupBox("1. Arquivo de áudio")
        form = QFormLayout(file_group)
        row = QHBoxLayout()
        self.txt_file = QLineEdit()
        self.txt_file.setReadOnly(True)
        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._browse_file)
        row.addWidget(self.txt_file, 1)
        row.addWidget(btn_browse)
        form.addRow(row)

        self.lbl_audio_info = QLabel("Nenhum arquivo selecionado")
        self.lbl_audio_info.setStyleSheet("color: #666;")
        form.addRow(self.lbl_audio_info)
        left_layout.addWidget(file_group)

        # Processamento
        proc_group = QGroupBox("2. Processamento desejado")
        proc_form = QFormLayout(proc_group)
        self.cmb_processing = QComboBox()
        self.cmb_processing.addItem("Carregando...", None)
        self.cmb_processing.currentIndexChanged.connect(self._on_processing_changed)
        proc_form.addRow("Tipo:", self.cmb_processing)

        self.txt_params = QLineEdit()
        self.txt_params.setPlaceholderText('Parâmetros JSON (ex.: {"factor": 1.5})')
        proc_form.addRow("Parâmetros:", self.txt_params)
        left_layout.addWidget(proc_group)

        # Envio
        self.btn_upload = QPushButton("3. Enviar para o servidor")
        self.btn_upload.setEnabled(False)
        self.btn_upload.setMinimumHeight(40)
        self.btn_upload.setStyleSheet("font-weight: bold;")
        self.btn_upload.clicked.connect(self._on_upload)
        left_layout.addWidget(self.btn_upload)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        left_layout.addWidget(self.progress)

        left_layout.addStretch(1)
        splitter.addWidget(left)

        # ================= Coluna direita: player + histórico ================= #
        right = QWidget()
        right_layout = QVBoxLayout(right)

        player_group = QGroupBox("Player")
        player_layout = QVBoxLayout(player_group)
        self.player = AudioPlayerWidget()
        player_layout.addWidget(self.player)

        btn_row = QHBoxLayout()
        self.btn_play_original = QPushButton("Reproduzir original")
        self.btn_play_processed = QPushButton("Reproduzir processado")
        self.btn_waveform = QPushButton("Ver waveform")
        btn_row.addWidget(self.btn_play_original)
        btn_row.addWidget(self.btn_play_processed)
        btn_row.addWidget(self.btn_waveform)
        player_layout.addLayout(btn_row)
        right_layout.addWidget(player_group)

        history_group = QGroupBox("Histórico de áudios enviados")
        hist_layout = QVBoxLayout(history_group)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Nome", "Processamento", "Duração", "Tamanho", "Data", "ID"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_history_select)
        hist_layout.addWidget(self.table)
        self.btn_delete = QPushButton("Excluir selecionado")
        self.btn_delete.clicked.connect(self._on_delete)
        hist_layout.addWidget(self.btn_delete)
        right_layout.addWidget(history_group, 1)

        splitter.addWidget(right)
        splitter.setSizes([420, 640])

        # Conexões
        self.btn_connect.clicked.connect(self._on_connect)
        self.btn_play_original.clicked.connect(lambda: self._play("original"))
        self.btn_play_processed.clicked.connect(lambda: self._play("processed"))
        self.btn_waveform.clicked.connect(self._show_waveform)

    # ------------------------------------------------------------------ #
    # Ações
    # ------------------------------------------------------------------ #

    def set_server_url(self, url: str) -> None:
        self.txt_url.setText(url)
        self._on_connect()

    def _ask_server_url(self):
        from PySide6.QtWidgets import QInputDialog

        url, ok = QInputDialog.getText(
            self, "Conectar ao servidor", "URL do servidor:",
            text=self.txt_url.text(),
        )
        if ok and url:
            self.set_server_url(url.strip())

    def _on_connect(self):
        url = self.txt_url.text().strip().rstrip("/")
        if not url:
            return
        self.api = AudioApiClient(url)
        try:
            health = self.api.health()
            ok = health.get("status") == "ok"
            db = health.get("database") == "ok"
            ffmpeg = health.get("ffmpeg") == "ok"
            color = "#2e9e5b" if (ok and db and ffmpeg) else "#d9a441"
            details = f"banco={'ok' if db else 'erro'} ffmpeg={'ok' if ffmpeg else 'erro'}"
            self.lbl_status.setText(f"🟢 Conectado ({details})" if ok else f"🟡 Parcial ({details})")
            self.lbl_status.setStyleSheet(f"color: {color};")
            if ok:
                self._load_processing_types()
                self.refresh_history()
        except ApiError as exc:
            self.lbl_status.setText("⚫ Desconectado")
            self.lbl_status.setStyleSheet("color: #c33;")
            QMessageBox.warning(self, "Conexão", f"Não foi possível conectar:\n{exc}")

    def _load_processing_types(self):
        if not self.api:
            return
        try:
            types = self.api.processing_types()
        except ApiError:
            return
        self.cmb_processing.blockSignals(True)
        self.cmb_processing.clear()
        for t in types:
            self.cmb_processing.addItem(f"{t['label']}", t["key"])
        self.cmb_processing.blockSignals(False)
        self._on_processing_changed()

    def _on_processing_changed(self):
        key = self.cmb_processing.currentData()
        if key and key in PARAM_HINTS:
            hint = PARAM_HINTS[key]
            self.txt_params.setPlaceholderText(hint)
            current = self.txt_params.text().strip()
            if not current or current in PARAM_HINTS.values():
                self.txt_params.setText("" if hint == "{}" else hint)

    def _browse_file(self):
        formats = " ".join(f"*{e}" for e in (".wav .mp3 .ogg .flac .m4a .aac .opus .wma".split()))
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo de áudio", "", f"Áudio ({formats});;Todos os arquivos (*.*)"
        )
        if not path:
            return
        self.txt_file.setText(path)
        self.btn_upload.setEnabled(True)
        self._show_audio_info(path)

    def _show_audio_info(self, path: str):
        """Mostra informações básicas do arquivo selecionado."""
        p = Path(path)
        size_mb = p.stat().st_size / (1024 * 1024)
        info = f"{p.suffix.lower().lstrip('.').upper()} • {size_mb:.2f} MB"

        # Usa ffprobe se disponível (opcional)
        try:
            import subprocess

            out = subprocess.run(
                [
                    resolve_binary("ffprobe"),
                    "-v", "error", "-print_format", "json",
                    "-show_format", "-show_streams", path,
                ],
                capture_output=True, text=True, check=True, timeout=15,
            )
            data = json.loads(out.stdout)
            stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
            dur = float(data.get("format", {}).get("duration", 0))
            info += f" • {dur:.1f}s"
            if stream.get("sample_rate"):
                info += f" • {stream['sample_rate']} Hz"
            if stream.get("channels"):
                info += f" • {'estéreo' if int(stream['channels']) > 1 else 'mono'}"
        except Exception:
            pass
        self.lbl_audio_info.setText(info)

    def _on_upload(self):
        if not self.api:
            QMessageBox.warning(self, "Envio", "Conecte-se ao servidor primeiro.")
            return
        path = self.txt_file.text().strip()
        if not path:
            QMessageBox.warning(self, "Envio", "Selecione um arquivo de áudio.")
            return
        key = self.cmb_processing.currentData()
        if not key:
            QMessageBox.warning(self, "Envio", "Tipos de processamento não carregados.")
            return

        params = None
        raw = self.txt_params.text().strip()
        if raw:
            try:
                params = json.loads(raw)
            except json.JSONDecodeError as exc:
                QMessageBox.critical(self, "Parâmetros inválidos", f"JSON malformado:\n{exc}")
                return

        self.btn_upload.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Enviando... %p%")

        self.upload_worker = UploadWorker(self.api, path, key, params)
        self.upload_worker.progress.connect(self._on_upload_progress)
        self.upload_worker.finished_ok.connect(self._on_upload_ok)
        self.upload_worker.failed.connect(self._on_upload_fail)
        self.upload_worker.start()

    def _on_upload_progress(self, sent: int, total: int):
        if total <= 0:
            return
        if sent >= total:
            self.progress.setRange(0, 0)
            self.progress.setFormat("Processando no servidor...")
            return
        self.progress.setRange(0, 100)
        self.progress.setValue(int(sent * 100 / total))
        self.progress.setFormat("Enviando... %p%")

    def _on_upload_ok(self, record: dict):
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setFormat("%p%")
        self.btn_upload.setEnabled(True)
        self.current_record = record
        QMessageBox.information(
            self, "Sucesso",
            f"Áudio processado!\n\nID: {record['id']}\n"
            f"Processamento: {record['processing_type']}",
        )
        self.refresh_history()

    def _on_upload_fail(self, msg: str):
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setFormat("%p%")
        self.btn_upload.setEnabled(True)
        QMessageBox.critical(self, "Falha no envio", msg)

    def refresh_history(self):
        if not self.api:
            return
        self.history_worker = HistoryWorker(self.api)
        self.history_worker.finished_ok.connect(self._on_history_ok)
        self.history_worker.failed.connect(self._on_history_fail)
        self.history_worker.start()

    def _on_history_ok(self, data: dict):
        items = data.get("items", [])
        self.table.setRowCount(len(items))
        for i, a in enumerate(items):
            created = a.get("created_at", "")
            try:
                created = datetime.fromisoformat(created).strftime("%d/%m/%Y %H:%M")
            except Exception:
                pass
            size_mb = a.get("size_bytes", 0) / (1024 * 1024)
            values = [
                a.get("original_name", ""),
                a.get("processing_type", ""),
                f"{a.get('duration_sec', 0):.1f}s",
                f"{size_mb:.2f} MB",
                created,
                a.get("id", "")[:8],
            ]
            for j, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                item.setData(Qt.ItemDataRole.UserRole, a)
                self.table.setItem(i, j, item)

    def _on_history_fail(self, msg: str):
        self.player.status.setText(f"Erro no histórico: {msg}")

    def _on_history_select(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item:
            self.current_record = item.data(Qt.ItemDataRole.UserRole)

    def _play(self, kind: str):
        if not self.api or not self.current_record:
            QMessageBox.information(self, "Player", "Selecione um áudio no histórico.")
            return
        rec = self.current_record
        if kind == "original":
            ext = rec.get("original_ext") or "bin"
        else:
            processed = rec.get("path_processed") or ""
            ext = Path(processed).suffix.lstrip(".") or rec.get("original_ext") or "bin"
        dest = self._temp_dir / f"{rec['id']}_{kind}.{ext}"
        label = f"{rec.get('original_name', '')} ({'original' if kind == 'original' else 'processado'})"
        self.player.status.setText("Baixando áudio...")
        if self.file_worker is not None:
            try:
                self.file_worker.finished_ok.disconnect()
                self.file_worker.failed.disconnect()
            except RuntimeError:
                pass
        self.file_worker = FileWorker(self.api, rec["id"], kind, str(dest), label)
        self.file_worker.finished_ok.connect(self.player.play_file)
        self.file_worker.failed.connect(lambda msg: QMessageBox.critical(self, "Player", msg))
        self.file_worker.start()

    def _show_waveform(self):
        if not self.api or not self.current_record:
            QMessageBox.information(self, "Waveform", "Selecione um áudio no histórico.")
            return
        rec = self.current_record
        try:
            data = self.api.fetch_waveform(rec["id"])
        except ApiError as exc:
            QMessageBox.warning(self, "Waveform", str(exc))
            return
        pixmap = QPixmap()
        dlg = QMessageBox(self)
        dlg.setWindowTitle(f"Waveform — {rec.get('original_name', '')}")
        if pixmap.loadFromData(data):
            dlg.setIconPixmap(pixmap.scaledToWidth(560, Qt.TransformationMode.SmoothTransformation))
        else:
            dlg.setText("Não foi possível carregar a waveform.")
        dlg.exec()

    def _on_delete(self):
        if not self.api or not self.current_record:
            QMessageBox.information(self, "Excluir", "Selecione um áudio no histórico.")
            return
        rec = self.current_record
        confirm = QMessageBox.question(
            self,
            "Excluir",
            f"Mover '{rec.get('original_name', rec.get('id'))}' para a lixeira do servidor?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.delete_audio(rec["id"])
        except ApiError as exc:
            QMessageBox.critical(self, "Excluir", str(exc))
            return
        self.current_record = None
        self.refresh_history()

    def _show_about(self):
        QMessageBox.about(
            self, "Sobre",
            "<b>Cliente de Áudio</b><br>"
            "Sistema cliente/servidor em camadas para processamento de áudio.<br><br>"
            "PySide6 + httpx • Servidor: FastAPI + FFmpeg + PostgreSQL",
        )

    def closeEvent(self, event):
        if self.api:
            self.api.close()
        super().closeEvent(event)


def main():
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
