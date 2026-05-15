"""
markdown_renderer.py — QWebEngineView that renders Markdown with math + theming.

Converts Markdown → HTML using the Python `markdown` library, injects the
current theme CSS, and renders in a WebEngine view with MathJax for LaTeX
math ($...$ inline, $$...$$ display).  Reconnects to THEME.changed so the
background always matches the rest of the UI.
"""

from __future__ import annotations

import markdown as _md
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView

from groupthink.gui.theme import THEME

_MD_PROCESSOR = _md.Markdown(
    extensions=["tables", "fenced_code", "nl2br", "sane_lists"],
    output_format="html",
)

_MATHJAX_CONFIG = """
window.MathJax = {
  tex: {
    inlineMath: [['$', '$']],
    displayMath: [['$$', '$$']],
    processEscapes: true
  },
  options: { skipHtmlTags: ['script','noscript','style','textarea','pre'] }
};
"""
_MATHJAX_CDN = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"


def _to_html(markdown_text: str) -> str:
    from groupthink.gui.theme import markdown_css
    _MD_PROCESSOR.reset()
    body = _MD_PROCESSOR.convert(markdown_text)
    css  = markdown_css(THEME.c)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{css}</style>
<script>{_MATHJAX_CONFIG}</script>
<script async src="{_MATHJAX_CDN}"></script>
</head>
<body>
{body}
</body>
</html>"""


class MarkdownView(QWebEngineView):
    """
    Drop-in view that renders Markdown + LaTeX math, themed to match the UI.

    Usage:
        view = MarkdownView()
        view.set_markdown("## Hello\\n\\n$E = mc^2$")
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_md = ""
        self._apply_bg()
        THEME.changed.connect(self._on_theme_changed)

    def set_markdown(self, text: str) -> None:
        self._current_md = text
        self._apply_bg()
        self.setHtml(_to_html(text), QUrl("about:blank"))

    def clear(self) -> None:
        self._current_md = ""
        self._apply_bg()
        self.setHtml("", QUrl("about:blank"))

    def _apply_bg(self):
        """Set WebEngine page background to match theme — prevents white flash."""
        self.page().setBackgroundColor(QColor(THEME.c.surface))

    def _on_theme_changed(self):
        self._apply_bg()
        if self._current_md:
            self.setHtml(_to_html(self._current_md), QUrl("about:blank"))
