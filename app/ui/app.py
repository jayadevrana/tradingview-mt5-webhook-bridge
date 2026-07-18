from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.bootstrap import AgentProcessController
from app.config.models import AppSettings
from app.ui.main_window import MainWindow


def run_ui(settings: AppSettings) -> int:
    qapp = QApplication(sys.argv)
    controller = AgentProcessController()
    window = MainWindow(settings=settings, agent_controller=controller)
    window.show()
    return qapp.exec()

