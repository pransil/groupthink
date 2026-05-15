"""
settings_dialog.py — App settings: two tabs.

  Models tab  — LLM enable/tier selection, synthesis LLM, web search options.
  API Keys tab — Enter / update API keys; saved to PROJECT_ROOT/.env and
                 reloaded into the running process without a restart.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from groupthink import config
from groupthink.core.app_settings import SETTINGS, TIER_LABELS, _THINKING_BUDGETS
from groupthink.gui.theme import THEME

_LLM_ORDER  = ("claude", "gpt", "gemini", "deepseek")
_LLM_LABELS = {"claude": "Claude", "gpt": "GPT", "gemini": "Gemini", "deepseek": "DeepSeek"}
_TIER_ORDER = ("high", "medium", "quick")

_KEY_FIELDS = [
    ("ANTHROPIC_API_KEY",  "Claude (Anthropic)",  "console.anthropic.com",            "https://console.anthropic.com"),
    ("OPENAI_API_KEY",     "GPT (OpenAI)",         "platform.openai.com/api-keys",     "https://platform.openai.com/api-keys"),
    ("GOOGLE_API_KEY",     "Gemini (Google)",      "aistudio.google.com/apikey",       "https://aistudio.google.com/apikey"),
    ("DEEPSEEK_API_KEY",   "DeepSeek",             "platform.deepseek.com/api_keys",   "https://platform.deepseek.com/api_keys"),
    ("TAVILY_API_KEY",     "Tavily (web search)",  "app.tavily.com",                   "https://app.tavily.com"),
]


def _write_env(new_keys: dict[str, str]) -> None:
    """Update PROJECT_ROOT/.env in place, preserving comments and other keys."""
    env_path = config.PROJECT_ROOT / ".env"
    original_lines: list[str] = env_path.read_text().splitlines() if env_path.exists() else []

    written: set[str] = set()
    out_lines: list[str] = []

    for line in original_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in new_keys:
                out_lines.append(f"{key}={new_keys[key]}")
                written.add(key)
                continue
        out_lines.append(line)

    for key, val in new_keys.items():
        if key not in written:
            out_lines.append(f"{key}={val}")

    env_path.write_text("\n".join(out_lines) + "\n")


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(600)

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 16, 20, 16)

        tabs = QTabWidget()
        tabs.addTab(self._build_models_tab(), "Models")
        tabs.addTab(self._build_keys_tab(),   "API Keys")
        root.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        THEME.changed.connect(self._on_theme)

    # ── Models tab ────────────────────────────────────────────────────────────

    def _build_models_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        desc = QLabel("Choose which LLMs are active and which model tier each uses.")
        desc.setStyleSheet(f"color: {THEME.c.subtext}; font-size: 12px;")
        layout.addWidget(desc)

        # Grid: enabled | name | tier | model detail
        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        for col, text in enumerate(("", "LLM", "Tier", "Model / effort")):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {THEME.c.subtext}; font-size: 11px; font-weight: 600;")
            grid.addWidget(lbl, 0, col)

        self._checkboxes:    dict[str, QCheckBox] = {}
        self._tier_combos:   dict[str, QComboBox] = {}
        self._detail_labels: dict[str, QLabel]    = {}

        api_enabled = set(config.enabled_llms())

        for row, llm in enumerate(_LLM_ORDER, start=1):
            cb = QCheckBox()
            cb.setChecked(SETTINGS.is_enabled(llm))
            cb.setEnabled(llm in api_enabled)
            self._checkboxes[llm] = cb
            grid.addWidget(cb, row, 0)

            name_lbl = QLabel(_LLM_LABELS[llm])
            if llm not in api_enabled:
                name_lbl.setStyleSheet(f"color: {THEME.c.subtext};")
                name_lbl.setToolTip("No API key configured — add one in the API Keys tab")
            grid.addWidget(name_lbl, row, 1)

            combo = QComboBox()
            combo.setMinimumWidth(240)
            current_tier = SETTINGS.tier(llm)
            for i, tier_key in enumerate(_TIER_ORDER):
                label = TIER_LABELS.get(llm, {}).get(tier_key, tier_key.capitalize())
                combo.addItem(label, tier_key)
                if tier_key == current_tier:
                    combo.setCurrentIndex(i)
            self._tier_combos[llm] = combo
            grid.addWidget(combo, row, 2)

            detail = QLabel(SETTINGS.tier_display(llm, current_tier))
            detail.setStyleSheet(self._detail_style())
            self._detail_labels[llm] = detail
            grid.addWidget(detail, row, 3)

            combo.currentIndexChanged.connect(lambda _, llm=llm: self._refresh_detail(llm))

        layout.addWidget(grid_wrap)

        # Synthesis LLM
        synth_wrap = QWidget()
        synth_row  = QGridLayout(synth_wrap)
        synth_row.setContentsMargins(0, 4, 0, 0)
        synth_row.setHorizontalSpacing(14)

        synth_hdr = QLabel("Synthesis & extended thinking LLM")
        synth_hdr.setStyleSheet(f"color: {THEME.c.text}; font-weight: 600; font-size: 13px;")
        synth_row.addWidget(synth_hdr, 0, 0, 1, 2)

        synth_desc = QLabel(
            "This LLM runs the final synthesis step and is the only one that uses extended thinking.\n"
            "All other LLMs run without thinking budgets on every call."
        )
        synth_desc.setStyleSheet(f"color: {THEME.c.subtext}; font-size: 11px;")
        synth_row.addWidget(synth_desc, 1, 0, 1, 2)

        synth_label = QLabel("Synthesis LLM:")
        synth_row.addWidget(synth_label, 2, 0)

        self._synth_combo = QComboBox()
        self._synth_combo.setMinimumWidth(220)
        current_synth = SETTINGS._synthesis_llm
        for llm in _LLM_ORDER:
            budget = _THINKING_BUDGETS.get(llm, {}).get(SETTINGS.tier(llm), 0)
            suffix = f"  ·  thinking: {'high' if budget >= 16_000 else 'medium'}" if budget else ""
            self._synth_combo.addItem(f"{_LLM_LABELS[llm]}{suffix}", llm)
            if llm == current_synth:
                self._synth_combo.setCurrentIndex(self._synth_combo.count() - 1)
        synth_row.addWidget(self._synth_combo, 2, 1)
        layout.addWidget(synth_wrap)

        # Web search
        ws_wrap   = QWidget()
        ws_layout = QVBoxLayout(ws_wrap)
        ws_layout.setContentsMargins(0, 4, 0, 0)
        ws_layout.setSpacing(8)

        ws_hdr = QLabel("Web Search")
        ws_hdr.setStyleSheet(f"color: {THEME.c.text}; font-weight: 600; font-size: 13px;")
        ws_layout.addWidget(ws_hdr)

        ws_desc = QLabel(
            "Tavily searches the live web before each iteration and injects results into the LLM prompts.\n"
            "More results and full content improve accuracy for current-events queries."
        )
        ws_desc.setStyleSheet(f"color: {THEME.c.subtext}; font-size: 11px;")
        ws_layout.addWidget(ws_desc)

        results_row = QHBoxLayout()
        results_row.setSpacing(10)
        results_row.addWidget(QLabel("Max search results:"))
        self._search_results_spin = QSpinBox()
        self._search_results_spin.setRange(1, 20)
        self._search_results_spin.setValue(SETTINGS.search_max_results())
        self._search_results_spin.setFixedWidth(70)
        results_row.addWidget(self._search_results_spin)
        results_row.addWidget(QLabel("(1–20, default 10)"))
        results_row.addStretch()
        ws_layout.addLayout(results_row)

        self._full_content_cb = QCheckBox(
            "Use full article content  (more accurate for current events, uses more tokens)"
        )
        self._full_content_cb.setChecked(SETTINGS.search_full_content())
        ws_layout.addWidget(self._full_content_cb)
        layout.addWidget(ws_wrap)

        layout.addStretch()
        return w

    # ── API Keys tab ──────────────────────────────────────────────────────────

    def _build_keys_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(4)
        layout.setContentsMargins(16, 16, 16, 16)

        intro = QLabel(
            "Enter your API keys below. Keys are saved to your computer and sent only to "
            "the respective AI service — never stored anywhere else."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {THEME.c.subtext}; font-size: 12px;")
        layout.addWidget(intro)

        form_wrap = QWidget()
        form = QFormLayout(form_wrap)
        form.setSpacing(10)
        form.setContentsMargins(0, 12, 0, 12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._key_edits: dict[str, QLineEdit] = {}

        current_keys = {
            "ANTHROPIC_API_KEY": config.ANTHROPIC_API_KEY,
            "OPENAI_API_KEY":    config.OPENAI_API_KEY,
            "GOOGLE_API_KEY":    config.GOOGLE_API_KEY,
            "DEEPSEEK_API_KEY":  config.DEEPSEEK_API_KEY,
            "TAVILY_API_KEY":    config.TAVILY_API_KEY,
        }

        for env_var, label, url_text, url_href in _KEY_FIELDS:
            row_widget = QWidget()
            row = QVBoxLayout(row_widget)
            row.setSpacing(3)
            row.setContentsMargins(0, 0, 0, 0)

            # Key input + show/hide toggle
            input_row = QHBoxLayout()
            input_row.setSpacing(6)

            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setPlaceholderText("Paste key here…")
            edit.setText(current_keys.get(env_var, ""))
            edit.setMinimumWidth(340)
            self._key_edits[env_var] = edit
            input_row.addWidget(edit)

            toggle = QPushButton("Show")
            toggle.setFixedWidth(70)
            toggle.setCheckable(True)
            toggle.toggled.connect(
                lambda checked, e=edit, b=toggle: (
                    e.setEchoMode(
                        QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
                    ),
                    b.setText("Hide" if checked else "Show"),
                )
            )
            input_row.addWidget(toggle)
            row.addLayout(input_row)

            # Clickable link
            link = QLabel(f'Get a key: <a href="{url_href}">{url_text}</a>')
            link.setOpenExternalLinks(True)
            link.setStyleSheet(f"color: {THEME.c.subtext}; font-size: 11px;")
            row.addWidget(link)

            form.addRow(f"{label}:", row_widget)

        layout.addWidget(form_wrap)

        note = QLabel("You need at least one LLM key. Tavily is optional (enables live web search).")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {THEME.c.subtext}; font-size: 11px; font-style: italic;")
        layout.addWidget(note)
        layout.addStretch()
        return w

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _detail_style(self) -> str:
        return (
            f"color: {THEME.c.subtext}; font-size: 11px; "
            f"font-family: 'SF Mono', 'Menlo', monospace;"
        )

    def _refresh_detail(self, llm: str) -> None:
        tier = self._tier_combos[llm].currentData()
        self._detail_labels[llm].setText(SETTINGS.tier_display(llm, tier))

    def _on_theme(self) -> None:
        style = self._detail_style()
        for lbl in self._detail_labels.values():
            lbl.setStyleSheet(style)

    def accept(self) -> None:
        # Save model settings
        for llm in _LLM_ORDER:
            SETTINGS.set_enabled(llm, self._checkboxes[llm].isChecked())
            SETTINGS.set_tier(llm, self._tier_combos[llm].currentData())
        SETTINGS.set_synthesis_llm(self._synth_combo.currentData())
        SETTINGS.set_search_max_results(self._search_results_spin.value())
        SETTINGS.set_search_full_content(self._full_content_cb.isChecked())
        SETTINGS.save()

        # Save API keys if any field is non-empty
        new_keys = {env_var: self._key_edits[env_var].text().strip()
                    for env_var, *_ in _KEY_FIELDS}
        if any(new_keys.values()):
            _write_env(new_keys)
            config.reload_keys()

        self.settings_changed.emit()
        super().accept()
