#!/usr/bin/env python3
"""
FileForge — Advanced File Properties Manager
Entry point. Run this file to launch the application.
"""

import sys
import os
import logging

# Ensure the package root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from modules.main_window import MainWindow


def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('fileforge.log'),
            logging.StreamHandler(sys.stdout),
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting FileForge application")

    # Enable HiDPI
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("FileForge")
    app.setOrganizationName("FileForge")

    window = MainWindow()
    window.show()

    logger.info("Application started successfully")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()