"""
app_settings.py — Persistent user preferences for LLM enable/disable and model tier.

Saved as app_settings.json in the project root.
Access via the module-level SETTINGS singleton.
"""

from __future__ import annotations

import json

from groupthink import config

_SETTINGS_FILE = config.PROJECT_ROOT / "app_settings.json"
_LLMS = ("claude", "gpt", "gemini", "deepseek")
_VALID_TIERS = ("high", "medium", "quick")

# Thinking token budgets per LLM per tier (0 = no thinking / not applicable).
# Claude:  high/medium both use sonnet-4-6, differentiated only by budget.
# Gemini:  all tiers use thinking; budget scales with tier.
_THINKING_BUDGETS: dict[str, dict[str, int]] = {
    "claude": {"high": 16_000, "medium": 4_000, "quick": 0},
    "gemini": {"high": 24_576, "medium": 8_192,  "quick": 8_192},
}

# Per-LLM tier labels shown in the settings dialog (overrides generic labels).
TIER_LABELS: dict[str, dict[str, str]] = {
    "claude": {
        "high":   "High  — sonnet-4-6, thinking: high",
        "medium": "Medium  — sonnet-4-6, thinking: medium",
        "quick":  "Quick  — haiku-4-5",
    },
    "gpt": {
        "high":   "High  — gpt-5",
        "medium": "Medium  — gpt-5-mini",
        "quick":  "Quick  — gpt-5-nano",
    },
    "gemini": {
        "high":   "High  — 3.1 pro, thinking: high",
        "medium": "Medium  — 2.5 pro, thinking: medium",
        "quick":  "Quick  — 2.5 flash, thinking: medium",
    },
    "deepseek": {
        "high":   "High  — reasoner R1  (default)",
        "medium": "Medium  — chat V3",
        "quick":  "Quick  — chat V3",
    },
}

# Default tier per LLM.
_DEFAULT_TIERS: dict[str, str] = {
    "claude":   "high",    # sonnet-4-6 with high thinking
    "gpt":      "high",    # gpt-5
    "gemini":   "medium",  # 2.5-pro with medium thinking
    "deepseek": "high",    # reasoner R1
}

# Which LLM performs the final synthesis and gets extended thinking on that call.
_DEFAULT_SYNTHESIS_LLM = "claude"

# Web search defaults
_DEFAULT_SEARCH_MAX_RESULTS  = 10
_DEFAULT_SEARCH_FULL_CONTENT = False   # True = full article text (slower, more accurate)


class AppSettings:
    def __init__(self):
        self._enabled:             dict[str, bool] = {llm: True for llm in _LLMS}
        self._tiers:               dict[str, str]  = dict(_DEFAULT_TIERS)
        self._synthesis_llm:       str             = _DEFAULT_SYNTHESIS_LLM
        self._search_max_results:  int             = _DEFAULT_SEARCH_MAX_RESULTS
        self._search_full_content: bool            = _DEFAULT_SEARCH_FULL_CONTENT
        self._load()

    def _load(self) -> None:
        if not _SETTINGS_FILE.exists():
            return
        try:
            data = json.loads(_SETTINGS_FILE.read_text())
            for llm in _LLMS:
                if llm in data.get("enabled", {}):
                    self._enabled[llm] = bool(data["enabled"][llm])
                tier = data.get("tiers", {}).get(llm)
                if tier in _VALID_TIERS:
                    self._tiers[llm] = tier
            sl = data.get("synthesis_llm")
            if sl in _LLMS:
                self._synthesis_llm = sl
            if "search_max_results" in data:
                self._search_max_results = max(1, min(20, int(data["search_max_results"])))
            if "search_full_content" in data:
                self._search_full_content = bool(data["search_full_content"])
        except Exception:
            pass

    def save(self) -> None:
        _SETTINGS_FILE.write_text(
            json.dumps({
                "enabled":             self._enabled,
                "tiers":               self._tiers,
                "synthesis_llm":       self._synthesis_llm,
                "search_max_results":  self._search_max_results,
                "search_full_content": self._search_full_content,
            }, indent=2)
        )

    # ── Enabled ───────────────────────────────────────────────────────────────

    def is_enabled(self, llm: str) -> bool:
        return self._enabled.get(llm, True)

    def set_enabled(self, llm: str, value: bool) -> None:
        self._enabled[llm] = value

    # ── Tiers ─────────────────────────────────────────────────────────────────

    def tier(self, llm: str) -> str:
        return self._tiers.get(llm, _DEFAULT_TIERS.get(llm, "medium"))

    def set_tier(self, llm: str, tier: str) -> None:
        if tier in _VALID_TIERS:
            self._tiers[llm] = tier

    # ── Derived ───────────────────────────────────────────────────────────────

    def model_for(self, llm: str) -> str:
        tier = self.tier(llm)
        return config.MODEL_TIERS.get(llm, {}).get(tier, config.MODELS.get(llm, ""))

    def thinking_budget_for(self, llm: str) -> int:
        tier = self.tier(llm)
        return _THINKING_BUDGETS.get(llm, {}).get(tier, 0)

    def tier_display(self, llm: str, tier: str) -> str:
        """Short description of a tier used in the settings model-name column."""
        model  = config.MODEL_TIERS.get(llm, {}).get(tier, "")
        budget = _THINKING_BUDGETS.get(llm, {}).get(tier, 0)
        if budget > 0:
            level = "high" if budget >= 16_000 else "medium"
            return f"{model}  ·  thinking: {level}"
        return model

    def enabled_llms(self) -> list[str]:
        """LLMs that are both user-enabled and have an API key configured."""
        api_enabled = set(config.enabled_llms())
        return [llm for llm in _LLMS if llm in api_enabled and self.is_enabled(llm)]

    def model_map(self) -> dict[str, str]:
        """Map of llm -> model string for all currently enabled LLMs."""
        return {llm: self.model_for(llm) for llm in self.enabled_llms()}

    # ── Synthesis LLM ─────────────────────────────────────────────────────────

    def synthesis_llm(self) -> str:
        """The LLM that runs the final synthesis step (falls back to first enabled)."""
        enabled = self.enabled_llms()
        if self._synthesis_llm in enabled:
            return self._synthesis_llm
        return enabled[0] if enabled else "claude"

    def set_synthesis_llm(self, llm: str) -> None:
        if llm in _LLMS:
            self._synthesis_llm = llm

    def synthesis_model(self) -> str:
        return self.model_for(self.synthesis_llm())

    def synthesis_extras(self) -> dict:
        """thinking_budget for the synthesis LLM — applied only on the synthesis call."""
        llm    = self.synthesis_llm()
        budget = self.thinking_budget_for(llm)
        return {"thinking_budget": budget} if budget > 0 else {}

    # ── Web search ────────────────────────────────────────────────────────────

    def search_max_results(self) -> int:
        return self._search_max_results

    def set_search_max_results(self, n: int) -> None:
        self._search_max_results = max(1, min(20, n))

    def search_full_content(self) -> bool:
        return self._search_full_content

    def set_search_full_content(self, v: bool) -> None:
        self._search_full_content = v


SETTINGS = AppSettings()
