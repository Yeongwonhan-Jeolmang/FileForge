#!/usr/bin/env python3
"""
FileForge — Advanced File Properties Manager
Entry point. Run this file to launch the application.

Usage:
    python main.py                 # start empty
    python main.py path/to/file    # open a file straight away
    python main.py path/to/folder  # browse a folder
"""

import sys
import os
import logging
import traceback
from logging.handlers import RotatingFileHandler

# Ensure the package root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QSettings
from modules import __version__, APP_NAME


def _log_path() -> str:
    """Log into the per-user app-data folder, not whatever the current directory is."""
    try:
        from modules.integrity_tools import ensure_app_data_dir
        return str(ensure_app_data_dir() / 'fileforge.log')
    except Exception:
        return 'fileforge.log'


def _install_excepthook(logger: logging.Logger):
    """
    PyQt5 aborts the whole process on an unhandled exception inside a slot.
    Log it and show a dialog instead, so one bug can't take the app down.
    """
    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        details = ''.join(traceback.format_exception(exc_type, exc, tb))
        logger.error("Unhandled exception:\n%s", details)
        app = QApplication.instance()
        if app is not None:
            box = QMessageBox(QMessageBox.Critical, f"{APP_NAME} — Unexpected error",
                              f"{exc_type.__name__}: {exc}")
            box.setInformativeText("The error was logged. You can keep working, "
                                   "but you may want to reload the current file.")
            box.setDetailedText(details)
            box.exec_()
    sys.excepthook = hook


def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(_log_path(), maxBytes=1_000_000, backupCount=2, encoding='utf-8'),
            logging.StreamHandler(sys.stdout),
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting FileForge %s", __version__)
    _install_excepthook(logger)

    # Enable HiDPI
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(__version__)
    # Fusion gives the stylesheet a consistent base on Windows / macOS / Linux
    app.setStyle("Fusion")

    # Imported after QApplication exists so theme/tokens can read settings safely
    from modules.main_window import MainWindow

    window = MainWindow()
    window.show()

    # Optional path argument
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if args:
        target = os.path.abspath(args[0])
        if os.path.isdir(target):
            window.open_folder(target)
        elif os.path.isfile(target):
            window.open_file(target)
        else:
            logger.warning("Path from command line does not exist: %s", target)

    logger.info("Application started successfully")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
