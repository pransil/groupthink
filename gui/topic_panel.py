"""
topic_panel.py — Per-topic research panel.

Layout:
  ┌──────────────────────────────────────────────────────┐
  │ Topic title                              [Cost badge] │
  │ Slug · Iterations · LLMs (meta line)                 │
  ├──────────────────────────────────────────────────────┤
  │ Iteration selector                                    │
  ├──────────────────────────────────────────────────────┤
  │ IterationView (tabbed LLM outputs)          [expand] │
  ├──────────────────────────────────────────────────────┤
  │ ████████████████ progress bar (hidden when idle)     │
  │ status text                                          │
  ├──────────────────────────────────────────────────────┤
  │ [Query input…………………………………]  [Run GroupThink]        │
  │                                [Cancel]              │
  └──────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from groupthink.core.cost_tracker import CostTracker
from groupthink.core.groupthink import IterationResult
from groupthink.core.session_manager import SessionManager, SessionState, TopicSession
from groupthink.core.topic_manager import TopicManager
from groupthink.gui.cost_widget import CostWidget
from groupthink.gui.iteration_view import IterationView
from groupthink.gui.theme import THEME


class TopicPanel(QWidget):
    """
    Full research panel for a single topic session.
    Emits iteration_complete(result) when a GT run finishes.
    """

    iteration_complete = pyqtSignal(object)

    def __init__(self, session: TopicSession, session_manager: SessionManager, parent=None):
        super().__init__(parent)
        self._session = session
        self._sm = session_manager
        self._current_task: Optional[asyncio.Task] = None

        self._build_ui()
        self._refresh_iteration_selector()
        THEME.changed.connect(self._on_theme_changed)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ── Header ────────────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        self._title_label = QLabel(
            self._session.topic.slug.replace("-", " ").title()
        )
        self._title_label.setStyleSheet(
            f"font-size: 20px; font-weight: 700; "
            f"color: {THEME.c.text}; letter-spacing: -0.4px;"
        )
        header_row.addWidget(self._title_label, stretch=1)

        self._cost_widget = CostWidget()
        header_row.addWidget(self._cost_widget, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(header_row)

        self._meta_label = QLabel()
        self._meta_label.setStyleSheet(
            f"color: {THEME.c.subtext}; font-size: 11px;"
        )
        root.addWidget(self._meta_label)
        self._refresh_meta()
        self._refresh_cost()

        # Thin separator
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {THEME.c.border};")
        self._sep = sep
        root.addWidget(sep)

        # ── Iteration selector ────────────────────────────────────────────────
        iter_row = QHBoxLayout()
        iter_label = QLabel("View:")
        iter_label.setStyleSheet(f"color: {THEME.c.subtext}; font-size: 12px;")
        iter_row.addWidget(iter_label)

        self._iter_combo = QComboBox()
        self._iter_combo.setFixedWidth(130)
        self._iter_combo.currentIndexChanged.connect(self._on_iter_selected)
        iter_row.addWidget(self._iter_combo)
        iter_row.addStretch()
        root.addLayout(iter_row)

        # ── Iteration view ────────────────────────────────────────────────────
        self._iter_view = IterationView()
        self._iter_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._iter_view, stretch=1)

        # ── Progress bar ──────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setFixedHeight(3)
        self._progress.setTextVisible(False)
        root.addWidget(self._progress)

        # ── Status line ───────────────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"color: {THEME.c.subtext}; font-size: 11px;"
        )
        root.addWidget(self._status_label)

        # ── Query input + buttons ─────────────────────────────────────────────
        query_row = QHBoxLayout()
        query_row.setSpacing(10)

        input_col = QVBoxLayout()
        input_col.setSpacing(6)

        self._query_input = QPlainTextEdit()
        self._query_input.setPlaceholderText("Enter your research query…")
        self._query_input.setFixedHeight(72)
        self._query_input.setFont(QFont("Helvetica Neue", 13))
        input_col.addWidget(self._query_input)

        from PyQt6.QtWidgets import QLineEdit
        self._search_query_input = QLineEdit()
        self._search_query_input.setPlaceholderText(
            "Web search query (optional — leave blank to use research query above)"
        )
        self._search_query_input.setFixedHeight(30)
        input_col.addWidget(self._search_query_input)

        query_row.addLayout(input_col, stretch=1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)

        self._run_btn = QPushButton("Run GroupThink")
        self._run_btn.setFixedHeight(34)
        self._run_btn.setMinimumWidth(140)
        self._run_btn.clicked.connect(self._on_run_clicked)
        btn_col.addWidget(self._run_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedHeight(30)
        self._cancel_btn.setMinimumWidth(140)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_col.addWidget(self._cancel_btn)

        btn_col.addStretch()

        query_row.addLayout(btn_col)
        root.addLayout(query_row)

    # ── Iteration selector ────────────────────────────────────────────────────

    def _refresh_iteration_selector(self):
        self._iter_combo.blockSignals(True)
        self._iter_combo.clear()
        iterations = self._session.topic.all_iterations()
        for n in iterations:
            self._iter_combo.addItem(f"Iteration {n:02d}", n)
        if iterations:
            self._iter_combo.setCurrentIndex(len(iterations) - 1)
            self._load_iteration(iterations[-1])
        self._iter_combo.blockSignals(False)
        self._refresh_meta()

    def _on_iter_selected(self, index: int):
        if index < 0:
            return
        n = self._iter_combo.itemData(index)
        if n is not None:
            self._load_iteration(n)

    def _load_iteration(self, n: int):
        self._iter_view.load_from_files(self._session.topic, n)

    # ── Running an iteration ──────────────────────────────────────────────────

    def _on_run_clicked(self):
        query = self._query_input.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "No query", "Please enter a research query.")
            return
        search_q = self._search_query_input.text().strip() or None
        self._set_running(True)
        self._current_task = asyncio.ensure_future(self._run_iteration(query, search_q))

    def _on_cancel_clicked(self):
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        self._set_running(False)
        self._status_label.setText("Cancelled.")

    async def _run_iteration(self, query: str, search_query: str | None = None):
        try:
            self._status_label.setText("Running GroupThink iteration…")
            result = await self._sm.run_iteration(self._session, query,
                                                   web_search_query=search_query)

            if result.errors:
                self._status_label.setText(
                    f"Completed with warnings: {result.errors[0]}"
                )
            else:
                self._status_label.setText(
                    f"Iteration {result.iteration:02d} complete — "
                    f"{len(result.successful_llms)} LLMs responded."
                )

            self._iter_view.load_result(result)
            self._refresh_iteration_selector()
            self._refresh_cost()
            self._query_input.clear()
            self.iteration_complete.emit(result)

        except asyncio.CancelledError:
            self._status_label.setText("Cancelled.")
        except Exception as exc:
            self._status_label.setText(f"Error: {exc}")
            QMessageBox.critical(self, "Error", str(exc))
        finally:
            self._set_running(False)

    def _set_running(self, running: bool):
        self._run_btn.setVisible(not running)
        self._cancel_btn.setVisible(running)
        self._progress.setVisible(running)
        self._query_input.setEnabled(not running)
        self._search_query_input.setEnabled(not running)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def refresh_meta(self) -> None:
        """Public slot — call after settings change to update LLM/model display."""
        self._refresh_meta()

    def _refresh_meta(self):
        from groupthink.core.app_settings import SETTINGS
        topic = self._session.topic
        n     = topic.current_iteration()
        llms  = SETTINGS.enabled_llms()
        tiers = [SETTINGS.tier(llm) for llm in llms]
        tier_str = ", ".join(
            f"{llm.capitalize()} ({tier})" for llm, tier in zip(llms, tiers)
        ) or "no LLMs enabled"
        self._meta_label.setText(
            f"{topic.slug}   ·   {n} iteration{'s' if n != 1 else ''}   ·   {tier_str}"
        )

    def _refresh_cost(self):
        tracker = CostTracker.load(self._session.topic.dir)
        self._cost_widget.refresh(tracker)

    def _on_theme_changed(self):
        c = THEME.c
        self._title_label.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {c.text}; letter-spacing: -0.4px;"
        )
        self._meta_label.setStyleSheet(f"color: {c.subtext}; font-size: 11px;")
        self._status_label.setStyleSheet(f"color: {c.subtext}; font-size: 11px;")
        self._sep.setStyleSheet(f"background: {c.border};")
