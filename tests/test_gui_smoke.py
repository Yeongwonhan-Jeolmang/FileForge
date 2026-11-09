"""
Headless GUI smoke test: builds the main window, opens a file and visits every tab.

Uses Qt's "offscreen" platform, so it runs on CI without a display.
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

QtWidgets = pytest.importorskip("PyQt5.QtWidgets")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    # Isolated settings so the test never touches the developer's real preferences
    os.environ["XDG_CONFIG_HOME"] = str(tmp_path_factory.mktemp("cfg"))
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield application


def _pump(app, ms=300):
    from PyQt5.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec_()


def test_open_file_and_visit_all_tabs(app, tmp_path):
    errors = []
    old_hook = sys.excepthook
    sys.excepthook = lambda t, e, tb: errors.append(e)
    try:
        from modules.main_window import MainWindow

        sample = tmp_path / "sample.txt"
        sample.write_text("FileForge smoke test\n" * 50)

        w = MainWindow()
        w.show()
        w.open_file(str(sample))
        _pump(app, 1000)
        assert w._current_info is not None and w._current_info.name == "sample.txt"

        for i in range(w._tabs.count()):
            w._tabs.setCurrentIndex(i)
            for sub in (w._metadata_tabs, w._analysis_tabs):
                for j in range(sub.count()):
                    sub.setCurrentIndex(j)
                    _pump(app, 50)
        _pump(app, 500)

        w._close_file()
        _pump(app, 200)
        assert w._current_info is None
        w.close()
    finally:
        sys.excepthook = old_hook
    assert not errors, errors
