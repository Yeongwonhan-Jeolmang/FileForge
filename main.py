#!/usr/bin/env python3
"""
FileForge — Advanced File Properties Manager
Entry point. Run this file to launch the application.
"""

import sys
import os

# Ensure the package root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from modules.main_window import MainWindow


def main():
    # Enable HiDPI
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("FileForge")
    app.setOrganizationName("FileForge")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()