"""
main_window.py — Top-level application window.

Layout:
  ┌─────────────────────────────────────────────────────────┐
  │  Header bar: logo · app name                 theme btn  │
  ├──────────┬──────────────────────────────────────────────┤
  │ Sidebar  │ Main panel (TopicPanel for active topic)     │
  │  TOPICS  │                                              │
  │  · foo   │                                              │
  │  · bar   │                                              │
  │          │                                              │
  │ [+ New]  │                                              │
  └──────────┴──────────────────────────────────────────────┘
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from groupthink import config
from groupthink.core.session_manager import SessionManager, TopicSession
from groupthink.gui.theme import THEME


class _ArrowDelegate(QStyledItemDelegate):
    """Draws a › arrow before the selected item instead of a highlight block."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        c = THEME.c
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover    = bool(option.state & QStyle.StateFlag.State_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Hover background (non-selected only)
        if is_hover and not is_selected:
            painter.setBrush(QColor(c.surface2))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(option.rect.adjusted(2, 1, -2, -1), 6, 6)

        # Arrow for selected item
        if is_selected:
            arrow_color = QColor(c.accent)
            pen = QPen(arrow_color, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            r = option.rect
            ax = r.left() + 8
            mid = r.center().y()
            tip_x = ax + 6
            painter.drawLine(ax, mid - 5, tip_x, mid)
            painter.drawLine(ax, mid + 5, tip_x, mid)

        # Text
        text_color = QColor(c.text)
        painter.setPen(text_color)
        font = option.font
        if is_selected:
            font.setBold(True)
        painter.setFont(font)
        text_rect = option.rect.adjusted(22, 0, -4, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter,
                         index.data(Qt.ItemDataRole.DisplayRole))
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        return QSize(super().sizeHint(option, index).width(), 32)
from groupthink.core.topic_manager import TopicManager
from groupthink.gui.icon import groupthink_icon, logo_widget
from groupthink.gui.topic_panel import TopicPanel


# ── New-topic dialog ──────────────────────────────────────────────────────────

class NewTopicDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Research Topic")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Topic name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Quantum Computing and Cryptography")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Description (optional):"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setFixedHeight(80)
        self.desc_edit.setPlaceholderText("Brief description of what you want to research…")
        layout.addWidget(self.desc_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def topic_name(self) -> str:
        return self.name_edit.text().strip()

    @property
    def topic_description(self) -> str:
        return self.desc_edit.toPlainText().strip()


# ── Header bar ────────────────────────────────────────────────────────────────

class HeaderBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("header")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)

        self._logo = logo_widget()
        layout.addWidget(self._logo)
        layout.addStretch()

        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setFixedHeight(28)
        self._settings_btn.setMinimumWidth(80)
        layout.addWidget(self._settings_btn)

        self._theme_btn = QPushButton()
        self._theme_btn.setFixedHeight(28)
        self._theme_btn.setMinimumWidth(110)
        self._theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self._theme_btn)

        self._refresh_btn_label()
        THEME.changed.connect(self._refresh_btn_label)

    def _toggle_theme(self):
        THEME.toggle()

    def _refresh_btn_label(self):
        self._theme_btn.setText("Light Mode" if THEME.is_dark else "Dark Mode")


# ── Sidebar ───────────────────────────────────────────────────────────────────

class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(210)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(6)

        header = QLabel("TOPICS")
        header.setObjectName("section-header")
        layout.addWidget(header)

        self._list = QListWidget()
        self._list.setFrameShape(self._list.Shape.NoFrame)
        self._list.setSpacing(1)
        self._delegate = _ArrowDelegate(self._list)
        self._list.setItemDelegate(self._delegate)
        layout.addWidget(self._list, stretch=1)
        THEME.changed.connect(self._list.viewport().update)

        self._new_btn = QPushButton("+ New Topic")
        self._new_btn.setFixedHeight(30)
        layout.addWidget(self._new_btn)

        self._close_btn = QPushButton("Close Topic")
        self._close_btn.setFixedHeight(30)
        self._close_btn.setEnabled(False)
        layout.addWidget(self._close_btn)

    @property
    def list_widget(self) -> QListWidget:
        return self._list

    @property
    def new_button(self) -> QPushButton:
        return self._new_btn

    @property
    def close_button(self) -> QPushButton:
        return self._close_btn


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Groupthink")
        self.setMinimumSize(1100, 700)
        self.resize(1360, 860)
        self.setWindowIcon(groupthink_icon(128, THEME.is_dark))

        self._sm = SessionManager(use_web_search=bool(config.TAVILY_API_KEY))
        self._panels: dict[str, TopicPanel] = {}

        THEME.apply()
        THEME.changed.connect(self._on_theme_changed)

        self._build_ui()
        self._load_existing_topics()
        self._show_warnings()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Header
        self._header = HeaderBar()
        v.addWidget(self._header)

        # Divider under header
        div_h = QWidget()
        div_h.setFixedHeight(1)
        div_h.setStyleSheet(f"background: {THEME.c.border};")
        self._header_div = div_h
        v.addWidget(div_h)

        # Body: sidebar + main panel
        body = QWidget()
        h = QHBoxLayout(body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        v.addWidget(body, stretch=1)

        self._sidebar = Sidebar()
        self._sidebar.new_button.clicked.connect(self._on_new_topic)
        self._sidebar.close_button.clicked.connect(self._on_close_topic)
        self._sidebar.list_widget.currentItemChanged.connect(self._on_topic_selected)
        h.addWidget(self._sidebar)
        self._header._settings_btn.clicked.connect(self._on_settings)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {THEME.c.bg};")
        h.addWidget(self._stack, stretch=1)

        placeholder = QLabel("Select a topic from the sidebar,\nor create a new one with + New Topic.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(f"color: {THEME.c.subtext}; font-size: 14px; background: transparent;")
        self._placeholder = placeholder
        self._stack.addWidget(placeholder)

    # ── Topic management ──────────────────────────────────────────────────────

    def _load_existing_topics(self):
        for tm in TopicManager.list_all():
            self._open_topic_session(tm.slug)

    def _open_topic_session(self, slug: str) -> TopicSession:
        session = self._sm.open(slug)
        if slug not in self._panels:
            panel = TopicPanel(session, self._sm)
            panel.iteration_complete.connect(self._on_iteration_complete)
            self._panels[slug] = panel
            self._stack.addWidget(panel)
            item = QListWidgetItem(slug.replace("-", " ").title())
            item.setData(Qt.ItemDataRole.UserRole, slug)
            self._sidebar.list_widget.addItem(item)
        return session

    def _on_new_topic(self):
        dlg = NewTopicDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name = dlg.topic_name
        if not name:
            QMessageBox.warning(self, "Name required", "Please enter a topic name.")
            return
        try:
            tm = TopicManager.create(name, dlg.topic_description)
            self._open_topic_session(tm.slug)
            count = self._sidebar.list_widget.count()
            self._sidebar.list_widget.setCurrentRow(count - 1)
        except ValueError as exc:
            QMessageBox.warning(self, "Topic exists", str(exc))

    def _on_close_topic(self):
        item = self._sidebar.list_widget.currentItem()
        if not item:
            return
        slug = item.data(Qt.ItemDataRole.UserRole)
        row  = self._sidebar.list_widget.row(item)
        self._sidebar.list_widget.takeItem(row)
        if slug in self._panels:
            panel = self._panels.pop(slug)
            self._stack.removeWidget(panel)
            panel.deleteLater()
        self._sm.close(slug)
        self._sidebar.close_button.setEnabled(False)

    def _on_topic_selected(self, current: QListWidgetItem, previous):
        if current is None:
            self._stack.setCurrentIndex(0)
            self._sidebar.close_button.setEnabled(False)
            return
        slug = current.data(Qt.ItemDataRole.UserRole)
        if slug in self._panels:
            self._stack.setCurrentWidget(self._panels[slug])
        self._sidebar.close_button.setEnabled(True)

    def _on_iteration_complete(self, result):
        pass

    def _on_settings(self):
        from groupthink.gui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.exec()

    def _on_settings_changed(self):
        for panel in self._panels.values():
            panel.refresh_meta()

    # ── Theme change ──────────────────────────────────────────────────────────

    def _on_theme_changed(self):
        self.setWindowIcon(groupthink_icon(128, THEME.is_dark))
        c = THEME.c
        self._stack.setStyleSheet(f"background: {c.bg};")
        self._header_div.setStyleSheet(f"background: {c.border};")
        self._placeholder.setStyleSheet(
            f"color: {c.subtext}; font-size: 14px; background: transparent;"
        )

    # ── Startup warnings ──────────────────────────────────────────────────────

    def _show_warnings(self):
        warnings = config.validate()
        if warnings:
            self.statusBar().showMessage(
                "  Some API keys missing — " + warnings[0]
            )
