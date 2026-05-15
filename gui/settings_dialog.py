"""
settings_dialog.py — LLM configuration dialog.

Shows a row per LLM with:
  [✓] LLM name   [tier dropdown]   model + thinking detail

Emits settings_changed after the user clicks OK and prefs are saved.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from groupthink import config
from groupthink.core.app_settings import SETTINGS, TIER_LABELS, _THINKING_BUDGETS
from groupthink.gui.theme import THEME

_LLM_ORDER  = ("claude", "gpt", "gemini", "deepseek")
_LLM_LABELS = {"claude": "Claude", "gpt": "GPT", "gemini": "Gemini", "deepseek": "DeepSeek"}
_TIER_ORDER = ("high", "medium", "quick")


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LLM Settings")
        self.setMinimumWidth(580)

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24, 20, 24, 20)

        desc = QLabel("Choose which LLMs are active and which model tier each uses.")
        desc.setStyleSheet(f"color: {THEME.c.subtext}; font-size: 12px;")
        root.addWidget(desc)

        # ── Grid: enabled | name | tier | model detail ────────────────────────
        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        for col, text in enumerate(("", "LLM", "Tier", "Model / effort")):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color: {THEME.c.subtext}; font-size: 11px; font-weight: 600;"
            )
            grid.addWidget(lbl, 0, col)

        self._checkboxes:   dict[str, QCheckBox] = {}
        self._tier_combos:  dict[str, QComboBox] = {}
        self._detail_labels: dict[str, QLabel]   = {}

        api_enabled = set(config.enabled_llms())

        for row, llm in enumerate(_LLM_ORDER, start=1):
            # Checkbox
            cb = QCheckBox()
            cb.setChecked(SETTINGS.is_enabled(llm))
            cb.setEnabled(llm in api_enabled)
            self._checkboxes[llm] = cb
            grid.addWidget(cb, row, 0)

            # LLM name
            name_lbl = QLabel(_LLM_LABELS[llm])
            if llm not in api_enabled:
                name_lbl.setStyleSheet(f"color: {THEME.c.subtext};")
                name_lbl.setToolTip("No API key configured")
            grid.addWidget(name_lbl, row, 1)

            # Tier dropdown — labels are per-LLM from TIER_LABELS
            combo = QComboBox()
            combo.setMinimumWidth(240)
            current_tier = SETTINGS.tier(llm)
            llm_tier_labels = TIER_LABELS.get(llm, {})
            for i, tier_key in enumerate(_TIER_ORDER):
                label = llm_tier_labels.get(tier_key, tier_key.capitalize())
                combo.addItem(label, tier_key)
                if tier_key == current_tier:
                    combo.setCurrentIndex(i)
            self._tier_combos[llm] = combo
            grid.addWidget(combo, row, 2)

            # Model detail label (monospace, updates live)
            detail = QLabel(SETTINGS.tier_display(llm, current_tier))
            detail.setStyleSheet(self._detail_style())
            self._detail_labels[llm] = detail
            grid.addWidget(detail, row, 3)

            combo.currentIndexChanged.connect(
                lambda _, llm=llm: self._refresh_detail(llm)
            )

        root.addWidget(grid_wrap)

        # ── Synthesis / thinking LLM ──────────────────────────────────────────
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
            display = _LLM_LABELS[llm]
            budget  = _THINKING_BUDGETS.get(llm, {}).get(SETTINGS.tier(llm), 0)
            suffix  = f"  ·  thinking: {'high' if budget >= 16_000 else 'medium'}" if budget else ""
            self._synth_combo.addItem(f"{display}{suffix}", llm)
            if llm == current_synth:
                self._synth_combo.setCurrentIndex(self._synth_combo.count() - 1)
        synth_row.addWidget(self._synth_combo, 2, 1)

        root.addWidget(synth_wrap)

        # ── Web Search ────────────────────────────────────────────────────────
        ws_wrap = QWidget()
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

        # Max results row
        results_row = QHBoxLayout()
        results_row.setSpacing(10)
        results_label = QLabel("Max search results:")
        results_row.addWidget(results_label)
        self._search_results_spin = QSpinBox()
        self._search_results_spin.setRange(1, 20)
        self._search_results_spin.setValue(SETTINGS.search_max_results())
        self._search_results_spin.setFixedWidth(70)
        results_row.addWidget(self._search_results_spin)
        results_row.addWidget(QLabel("(1–20, default 10)"))
        results_row.addStretch()
        ws_layout.addLayout(results_row)

        # Full content toggle
        self._full_content_cb = QCheckBox(
            "Use full article content  (more accurate for current events, uses more tokens)"
        )
        self._full_content_cb.setChecked(SETTINGS.search_full_content())
        ws_layout.addWidget(self._full_content_cb)

        root.addWidget(ws_wrap)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        THEME.changed.connect(self._on_theme)

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
        for llm in _LLM_ORDER:
            SETTINGS.set_enabled(llm, self._checkboxes[llm].isChecked())
            SETTINGS.set_tier(llm, self._tier_combos[llm].currentData())
        SETTINGS.set_synthesis_llm(self._synth_combo.currentData())
        SETTINGS.set_search_max_results(self._search_results_spin.value())
        SETTINGS.set_search_full_content(self._full_content_cb.isChecked())
        SETTINGS.save()
        self.settings_changed.emit()
        super().accept()
