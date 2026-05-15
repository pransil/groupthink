"""
cost_widget.py — Cost badge with a hover dropdown showing per-service breakdown.

CostWidget is a styled QLabel that displays the total estimated cost.
When the mouse enters it, a frameless popup appears below showing
a line per LLM with its individual cost. Follows THEME for colours.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QTimer, Qt
from PyQt6.QtGui import QCursor, QEnterEvent
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from groupthink.core.cost_tracker import CostTracker
from groupthink.gui.theme import THEME

_LLM_DISPLAY = {
    "claude":   "Claude",
    "gpt":      "GPT",
    "gemini":   "Gemini",
    "deepseek": "DeepSeek",
}


def _fmt(usd: float) -> str:
    if usd < 0.0001:
        return "$0.0000"
    if usd < 0.01:
        return f"${usd:.4f}"
    return f"${usd:.3f}"


def _badge_style() -> str:
    c = THEME.c
    return f"""
        QLabel {{
            background-color: {c.button};
            color: {c.text};
            font-size: 13px;
            font-weight: 500;
            padding: 5px 16px;
            border-radius: 7px;
            border: 1px solid {c.border};
        }}
        QLabel:hover {{
            background-color: {c.button_hover};
        }}
    """


def _popup_style() -> str:
    c = THEME.c
    return f"""
        QFrame {{
            background: {c.surface};
            border: 1px solid {c.border};
            border-radius: 10px;
        }}
    """


class _CostPopup(QFrame):
    """Frameless floating breakdown panel."""

    def __init__(self, parent: QWidget):
        super().__init__(
            parent.window(),
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 10, 14, 10)
        self._layout.setSpacing(3)

        self._header = QLabel("Estimated cost")
        self._rows: dict[str, QLabel] = {}
        self._layout.addWidget(self._header)

        self._apply_style()
        THEME.changed.connect(self._apply_style)

    def _apply_style(self):
        self.setStyleSheet(_popup_style())
        c = THEME.c
        self._header.setStyleSheet(
            f"color: {c.subtext}; font-size: 11px; font-weight: 600; "
            f"letter-spacing: 0.4px; background: transparent;"
        )
        for row in self._rows.values():
            row.setStyleSheet(f"color: {c.text}; font-size: 12px; background: transparent;")

    def update_rows(self, by_llm: dict[str, float]):
        for label in self._rows.values():
            self._layout.removeWidget(label)
            label.deleteLater()
        self._rows.clear()

        c = THEME.c
        for llm, cost in sorted(by_llm.items()):
            display = _LLM_DISPLAY.get(llm, llm.upper())
            row = QLabel(f"{display}   {_fmt(cost)}")
            row.setStyleSheet(f"color: {c.text}; font-size: 12px; background: transparent;")
            self._layout.addWidget(row)
            self._rows[llm] = row

        if not by_llm:
            row = QLabel("No usage recorded yet.")
            row.setStyleSheet(f"color: {c.subtext}; font-size: 12px; background: transparent;")
            self._layout.addWidget(row)
            self._rows["_empty"] = row

        self.adjustSize()

    def show_below(self, badge: "CostWidget"):
        global_pos = badge.mapToGlobal(QPoint(0, badge.height() + 6))
        win = badge.window()
        win_right = win.mapToGlobal(QPoint(win.width(), 0)).x()
        x = min(global_pos.x(), win_right - self.width() - 12)
        self.move(x, global_pos.y())
        self.show()
        self.raise_()


class CostWidget(QLabel):
    """
    Badge label showing total cost. Hover reveals per-LLM breakdown popup.
    """

    def __init__(self, parent=None):
        super().__init__("Cost: —", parent)
        self._apply_style()
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(30)

        self._popup = _CostPopup(self)
        self._popup.hide()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(150)
        self._hide_timer.timeout.connect(self._maybe_hide)

        self._by_llm: dict[str, float] = {}

        THEME.changed.connect(self._apply_style)

    def _apply_style(self):
        self.setStyleSheet(_badge_style())

    def refresh(self, tracker: CostTracker):
        total = tracker.total_cost()
        self._by_llm = tracker.cost_by_llm()
        self.setText(f"Cost: {_fmt(total)}")
        self._popup.update_rows(self._by_llm)

    def enterEvent(self, event: QEnterEvent):
        self._hide_timer.stop()
        self._popup.update_rows(self._by_llm)
        self._popup.show_below(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hide_timer.start()
        super().leaveEvent(event)

    def _maybe_hide(self):
        if not self._popup.frameGeometry().contains(QCursor.pos()):
            self._popup.hide()
