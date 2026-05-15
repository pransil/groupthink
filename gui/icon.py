"""
icon.py — GroupThink icon drawn with QPainter.

Design: four coloured nodes (one per LLM) arranged at N/E/S/W,
each connected by a line to a central blue synthesis node.
Represents multiple AI models converging on a shared understanding.

    groupthink_pixmap(size, dark)   → QPixmap (transparent background)
    groupthink_icon(size, dark)     → QIcon
    logo_widget(parent)             → QWidget (icon + "Groupthink" label)
"""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter,
    QPen, QPixmap, QRadialGradient,
)
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget


# LLM node colours
_NODE_COLORS = [
    "#FF6B35",   # Claude   — orange
    "#34C759",   # GPT      — green
    "#5E5CE6",   # Gemini   — indigo
    "#FF375F",   # DeepSeek — pink
]
_CENTER_COLOR  = "#0A84FF"   # synthesis — blue
_LINE_COLOR_DK = "#66666e"
_LINE_COLOR_LT = "#b0b0b8"


def groupthink_pixmap(size: int = 64, dark: bool = True) -> QPixmap:
    """Return a QPixmap of the GroupThink icon at the requested size."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    cx = cy = size / 2.0
    margin    = size * 0.10
    r_outer   = (size / 2.0) - margin - (size * 0.11)   # centre of outer nodes
    r_node    = size * 0.115                              # outer node radius
    r_center  = size * 0.175                             # central node radius

    # Positions: top, right, bottom, left
    angles = [90, 0, 270, 180]
    positions = [
        (cx + r_outer * math.cos(math.radians(a)),
         cy - r_outer * math.sin(math.radians(a)))
        for a in angles
    ]

    line_color = QColor(_LINE_COLOR_DK if dark else _LINE_COLOR_LT)

    # ── Connecting lines ──────────────────────────────────────────────────────
    pen = QPen(line_color, max(1.0, size * 0.025))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for nx, ny in positions:
        # Shorten line so it doesn't overlap with node circles
        dx, dy = nx - cx, ny - cy
        dist = math.hypot(dx, dy)
        ux, uy = dx / dist, dy / dist
        x1 = cx + ux * r_center
        y1 = cy + uy * r_center
        x2 = nx - ux * r_node
        y2 = ny - uy * r_node
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    # ── Outer nodes ───────────────────────────────────────────────────────────
    p.setPen(Qt.PenStyle.NoPen)
    for i, (nx, ny) in enumerate(positions):
        color = QColor(_NODE_COLORS[i])
        # Subtle radial gradient for depth
        grad = QRadialGradient(nx - r_node * 0.25, ny - r_node * 0.25, r_node * 1.4)
        grad.setColorAt(0.0, color.lighter(130))
        grad.setColorAt(1.0, color.darker(115))
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(nx, ny), r_node, r_node)

    # ── Central node ──────────────────────────────────────────────────────────
    cc = QColor(_CENTER_COLOR)
    grad_c = QRadialGradient(cx - r_center * 0.2, cy - r_center * 0.2, r_center * 1.5)
    grad_c.setColorAt(0.0, cc.lighter(140))
    grad_c.setColorAt(1.0, cc.darker(120))
    p.setBrush(QBrush(grad_c))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(cx, cy), r_center, r_center)

    # Small white dot in centre of central node (highlight)
    p.setBrush(QBrush(QColor(255, 255, 255, 160)))
    p.drawEllipse(QPointF(cx - r_center * 0.22, cy - r_center * 0.22),
                  r_center * 0.28, r_center * 0.28)

    p.end()
    return px


def groupthink_icon(size: int = 64, dark: bool = True) -> QIcon:
    return QIcon(groupthink_pixmap(size, dark))


def logo_widget(parent=None) -> "LogoWidget":
    return LogoWidget(parent)


class LogoWidget(QWidget):
    """Icon + 'Groupthink' wordmark, updates on theme change."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from groupthink.gui.theme import THEME
        self._theme = THEME

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(28, 28)
        layout.addWidget(self._icon_label)

        self._text_label = QLabel("Groupthink")
        self._text_label.setObjectName("app-title")
        layout.addWidget(self._text_label)
        layout.addStretch()

        self._refresh()
        THEME.changed.connect(self._refresh)

    def _refresh(self):
        px = groupthink_pixmap(56, self._theme.is_dark)
        self._icon_label.setPixmap(
            px.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)
        )
