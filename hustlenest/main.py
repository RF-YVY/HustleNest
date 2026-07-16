from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from hustlenest.data import database
from hustlenest.ui.main_window import MainWindow
from hustlenest.resources import get_app_icon_path
from hustlenest.versioning import APP_VERSION


def main() -> int:
    database.initialize()

    app = QApplication(sys.argv)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(str(get_app_icon_path())))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
