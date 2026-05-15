"""
iteration_view.py — Tabbed display of LLM outputs for a single GT iteration.

Outer tabs: one per LLM (Claude, GPT, etc.)
Inner tabs: Initial Response / GroupThink Pass
Content:    MarkdownView (themed web view)

One clean rounded border wraps the entire outer tab widget.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from groupthink.core.groupthink import IterationResult
from groupthink.gui.markdown_renderer import MarkdownView
from groupthink.gui.theme import THEME


_LLM_LABELS = {
    "claude":   "Claude",
    "gpt":      "GPT",
    "gemini":   "Gemini",
    "deepseek": "DeepSeek",
}


def _apply_tab_style(tw: QTabWidget) -> None:
    """Force the tab bar background via palette (beats macOS native rendering)."""
    c = THEME.c
    bg = QColor(c.tab_bar)
    pal = tw.palette()
    pal.setColor(QPalette.ColorRole.Window, bg)
    pal.setColor(QPalette.ColorRole.Button, bg)
    tw.setAutoFillBackground(True)
    tw.setPalette(pal)
    bar = tw.tabBar()
    bar.setAutoFillBackground(True)
    bar.setPalette(pal)


def _make_tab_widget() -> QTabWidget:
    tw = QTabWidget()
    _apply_tab_style(tw)
    return tw


def _make_md_view(content: str) -> MarkdownView:
    view = MarkdownView()
    view.set_markdown(content)
    return view


class LLMTab(QWidget):
    """Inner tab: Initial Response + GroupThink Pass for one LLM."""

    def __init__(self, llm: str, initial: Optional[str], gt: Optional[str], parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._inner = _make_tab_widget()
        if initial is not None:
            self._inner.addTab(_make_md_view(initial), "Initial Response")
        if gt is not None:
            self._inner.addTab(_make_md_view(gt), "GroupThink Pass")
        layout.addWidget(self._inner)

        THEME.changed.connect(lambda: _apply_tab_style(self._inner))


class IterationView(QWidget):
    """Outer tabbed view — one tab per LLM, plus Summary."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = _make_tab_widget()
        self._apply_outer_style()
        layout.addWidget(self._tabs)

        THEME.changed.connect(self._apply_outer_style)
        THEME.changed.connect(lambda: _apply_tab_style(self._tabs))

    def _apply_outer_style(self) -> None:
        c = THEME.c
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {c.border};
                border-radius: 8px;
                background: {c.surface};
            }}
            QTabBar::tab {{
                background: {c.tab_bar};
                color: {c.subtext};
                border: 1px solid {c.border};
                border-bottom: none;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                padding: 6px 18px;
                margin-right: 2px;
                font-size: 12px;
                font-weight: 500;
                min-width: 90px;
            }}
            QTabBar::tab:selected {{
                background: {c.surface};
                color: {c.text};
                font-weight: 600;
                border-bottom: 1px solid {c.surface};
                margin-bottom: -1px;
            }}
            QTabBar::tab:hover:!selected {{
                background: {c.surface2};
                color: {c.text};
            }}
        """)

    def clear(self):
        self._tabs.clear()

    def load_result(self, result: IterationResult):
        self.clear()

        initial_map = {r.llm: r for r in result.initial_responses}
        gt_map      = {r.llm: r for r in result.groupthink_responses}
        llms        = list(dict.fromkeys(
            [r.llm for r in result.initial_responses] +
            [r.llm for r in result.groupthink_responses]
        ))

        for llm in llms:
            ir = initial_map.get(llm)
            gr = gt_map.get(llm)
            initial_text = ir.content if ir and ir.ok else (ir.to_markdown() if ir else None)
            gt_text      = gr.content if gr and gr.ok else (gr.to_markdown() if gr else None)
            tab = LLMTab(llm, initial_text, gt_text)
            self._tabs.addTab(tab, _LLM_LABELS.get(llm, llm.upper()))

        if result.summary:
            summary_view = _make_md_view(result.summary)
            self._tabs.addTab(summary_view, "Summary")
            self._tabs.setCurrentIndex(self._tabs.count() - 1)

    def load_from_files(self, topic_manager, iteration: int):
        """Populate by reading files from disk (for previously-run iterations)."""
        from groupthink.core.groupthink import IterationResult
        from groupthink.core.llm_router import LLMResponse

        files = topic_manager.iter_files_for(iteration)
        llms = [k for k in ("claude", "gpt", "gemini", "deepseek") if k in files]

        initial_responses = []
        gt_responses = []
        for llm in llms:
            content = topic_manager.read_iter_file(iteration, llm) or ""
            initial_responses.append(LLMResponse(llm=llm, content=content, elapsed=0, model=""))
            gt_content = topic_manager.read_iter_file(iteration, f"groupthink_{llm}") or ""
            if gt_content:
                gt_responses.append(LLMResponse(llm=llm, content=gt_content, elapsed=0, model=""))

        summary = topic_manager.read_iter_file(iteration, "summary") or ""
        result = IterationResult(
            iteration=iteration,
            topic_slug=topic_manager.slug,
            query=f"Iteration {iteration:02d}",
            initial_responses=initial_responses,
            groupthink_responses=gt_responses,
            summary=summary,
        )
        self.load_result(result)
