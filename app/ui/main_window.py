from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.bootstrap import AgentProcessController
from app.config.models import AppSettings


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, agent_controller: AgentProcessController) -> None:
        super().__init__()
        self._settings = settings
        self._agent_controller = agent_controller
        self.setWindowTitle(self._settings.ui.window_title)
        self.resize(980, 640)

        self._agent_status = QLabel("Stopped")
        self._mt5_status = QLabel("Unknown")
        self._mt5_terminal_pid = QLabel("-")
        self._mt5_account = QLabel("-")
        self._mt5_server = QLabel("-")
        self._webhook_local = QLabel(
            f"http://{self._settings.agent.host}:{self._settings.agent.port}/webhook/<endpoint_token>"
        )
        self._public_url = QLabel("Not configured yet")

        self._start_btn = QPushButton("Start Agent")
        self._stop_btn = QPushButton("Stop Agent")
        self._start_btn.clicked.connect(self._on_start_agent)  # type: ignore[arg-type]
        self._stop_btn.clicked.connect(self._on_stop_agent)  # type: ignore[arg-type]

        self._build_layout()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh_status)  # type: ignore[arg-type]
        self._timer.start()

    def _build_layout(self) -> None:
        central = QWidget()
        root = QVBoxLayout()

        status_box = QGroupBox("Dashboard")
        status_grid = QGridLayout()
        status_grid.addWidget(QLabel("Agent status"), 0, 0)
        status_grid.addWidget(self._agent_status, 0, 1)
        status_grid.addWidget(QLabel("License status"), 1, 0)
        status_grid.addWidget(QLabel("Not implemented"), 1, 1)
        status_grid.addWidget(QLabel("MT5 status"), 2, 0)
        status_grid.addWidget(self._mt5_status, 2, 1)
        status_grid.addWidget(QLabel("MT5 terminal PID"), 3, 0)
        status_grid.addWidget(self._mt5_terminal_pid, 3, 1)
        status_grid.addWidget(QLabel("MT5 account ID"), 4, 0)
        status_grid.addWidget(self._mt5_account, 4, 1)
        status_grid.addWidget(QLabel("MT5 server"), 5, 0)
        status_grid.addWidget(self._mt5_server, 5, 1)
        status_grid.addWidget(QLabel("ngrok status"), 6, 0)
        status_grid.addWidget(QLabel("Not configured"), 6, 1)
        status_grid.addWidget(QLabel("Local webhook URL"), 7, 0)
        status_grid.addWidget(self._webhook_local, 7, 1)
        status_grid.addWidget(QLabel("Public webhook URL"), 8, 0)
        status_grid.addWidget(self._public_url, 8, 1)
        status_box.setLayout(status_grid)

        controls = QHBoxLayout()
        controls.addWidget(self._start_btn)
        controls.addWidget(self._stop_btn)
        controls.addStretch()

        root.addWidget(status_box)
        root.addLayout(controls)
        root.addStretch()

        central.setLayout(root)
        self.setCentralWidget(central)

    def _on_start_agent(self) -> None:
        self._agent_controller.start()
        self._refresh_status()

    def _on_stop_agent(self) -> None:
        self._agent_controller.stop()
        self._refresh_status()

    def _refresh_status(self) -> None:
        running = self._agent_controller.is_running()
        self._agent_status.setText("Running" if running else "Stopped")
        if not running:
            self._set_mt5_labels_not_available("Agent not running")
            return
        status_payload = self._fetch_mt5_status()
        if status_payload is None:
            self._set_mt5_labels_not_available("MT5 status unavailable")
            return
        selection_status = str(status_payload.get("selection_status") or "unknown")
        connected = bool(status_payload.get("connected", False))
        message = str(status_payload.get("message") or "")
        adapter = str(status_payload.get("adapter") or "unknown")
        self._mt5_status.setText(f"{selection_status} | connected={connected} | {adapter} | {message}")
        pid = status_payload.get("selected_terminal_pid")
        self._mt5_terminal_pid.setText(str(pid) if pid is not None else "-")
        account_login = status_payload.get("account_login")
        self._mt5_account.setText(str(account_login) if account_login is not None else "-")
        account_server = status_payload.get("account_server")
        self._mt5_server.setText(str(account_server) if account_server is not None else "-")

    def _fetch_mt5_status(self) -> dict[str, object] | None:
        url = f"http://{self._settings.agent.host}:{self._settings.agent.port}/mt5/status"
        request = Request(url=url, method="GET")
        try:
            with urlopen(request, timeout=0.8) as response:
                raw = response.read().decode("utf-8")
            payload = json.loads(raw)
            if isinstance(payload, dict):
                return payload
            return None
        except (URLError, TimeoutError, json.JSONDecodeError):
            return None

    def _set_mt5_labels_not_available(self, reason: str) -> None:
        self._mt5_status.setText(reason)
        self._mt5_terminal_pid.setText("-")
        self._mt5_account.setText("-")
        self._mt5_server.setText("-")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._agent_controller.stop()
        super().closeEvent(event)
