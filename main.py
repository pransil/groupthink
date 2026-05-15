"""
main.py — Groupthink application entry point.

Run from project root:
    python main.py
or:
    cd /path/to/groupthink && python main.py
"""

import asyncio
import sys

import qasync
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from groupthink.gui.main_window import MainWindow
from groupthink.gui.theme import THEME


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Groupthink")
    app.setOrganizationName("Groupthink")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    win = MainWindow()
    win.show()

    # Re-polish the stylesheet on the first event-loop tick so macOS
    # finalises button geometry and layout before the first paint.
    QTimer.singleShot(0, lambda: THEME.apply())

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
