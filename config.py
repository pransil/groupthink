"""
config.py — Central configuration for Groupthink.

API keys are read from a .env file in the project root (groupthink/).
Copy .env.example to .env and fill in your keys.
The topics root directory is also configurable here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────────────
# Project root = the directory containing this file
PROJECT_ROOT = Path(__file__).parent.resolve()

# Load .env from project root
load_dotenv(PROJECT_ROOT / ".env", override=True)

# Where all topic directories live (can override via GROUPTHINK_TOPICS_DIR in .env)
TOPICS_DIR = Path(os.getenv("GROUPTHINK_TOPICS_DIR", str(PROJECT_ROOT / "topics")))

# ── API Keys ───────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY     = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY", "")
TAVILY_API_KEY     = os.getenv("TAVILY_API_KEY", "")

# ── Model Tiers ────────────────────────────────────────────────────────────────
# Three quality/cost tiers per LLM.
# "high"   — deep-thinking / most capable (thinking budgets defined in app_settings.py)
# "medium" — standard capable model
# "quick"  — fast and cheap, still very good
#
# Claude:   high & medium both use sonnet-4-6, differing only in thinking budget
# GPT:      gpt-5 family
# Gemini:   3.1-pro (high) → 2.5-pro (medium, default) → 2.5-flash (quick)
# DeepSeek: reasoner R1 (high, default) → chat V3 (medium/quick)
MODEL_TIERS: dict[str, dict[str, str]] = {
    "claude": {
        "high":   "claude-sonnet-4-6",         # extended thinking: high budget
        "medium": "claude-sonnet-4-6",          # extended thinking: medium budget
        "quick":  "claude-haiku-4-5-20251001",  # no thinking
    },
    "gpt": {
        "high":   "gpt-5",
        "medium": "gpt-5-mini",
        "quick":  "gpt-5-nano",
    },
    "gemini": {
        "high":   "gemini-3.1-pro-preview",     # thinking: HIGH
        "medium": "gemini-2.5-pro",             # thinking: MEDIUM  (default)
        "quick":  "gemini-2.5-flash",           # thinking: MEDIUM
    },
    "deepseek": {
        "high":   "deepseek-reasoner",          # R1  (default)
        "medium": "deepseek-chat",              # V3
        "quick":  "deepseek-chat",              # V3
    },
}

# ── Model Names (env override fallback only — AppSettings drives normal usage) ──
MODELS = {
    "claude":   os.getenv("CLAUDE_MODEL",   MODEL_TIERS["claude"]["high"]),
    "gpt":      os.getenv("GPT_MODEL",      MODEL_TIERS["gpt"]["high"]),
    "gemini":   os.getenv("GEMINI_MODEL",   MODEL_TIERS["gemini"]["medium"]),
    "deepseek": os.getenv("DEEPSEEK_MODEL", MODEL_TIERS["deepseek"]["high"]),
}

# DeepSeek uses the OpenAI-compatible endpoint
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ── Pricing ────────────────────────────────────────────────────────────────────
# Cost per 1M tokens (input_usd, output_usd). Approximate — verify at each
# provider's pricing page. Used only for display estimates, not billing.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Claude  (input $/1M, output $/1M)
    "claude-sonnet-4-6":         ( 3.00, 15.00),
    "claude-haiku-4-5-20251001": ( 0.80,  4.00),
    "claude-haiku-4-5":          ( 0.80,  4.00),
    "claude-opus-4-7":           (15.00, 75.00),
    "claude-opus-4-5":           (15.00, 75.00),
    # GPT — approximate, verify at platform.openai.com/pricing
    "gpt-5":                     (25.00, 75.00),
    "gpt-5-mini":                ( 2.00,  8.00),
    "gpt-5-nano":                ( 0.30,  1.20),
    "o3":                        (10.00, 40.00),
    "gpt-4o":                    ( 2.50, 10.00),
    "gpt-4o-mini":               ( 0.15,  0.60),
    # Gemini — approximate, verify at ai.google.dev/pricing
    "gemini-3.1-pro-preview":    ( 3.00, 12.00),
    "gemini-2.5-pro":            ( 1.25,  5.00),
    "gemini-2.5-flash":          ( 0.075, 0.30),
    "gemini-2.0-flash":          ( 0.075, 0.30),
    # DeepSeek
    "deepseek-reasoner":         ( 0.55,  2.19),
    "deepseek-chat":             ( 0.14,  0.28),
}

def token_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD for the given token counts."""
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return 0.0
    input_price, output_price = pricing
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000

# ── LLM Defaults ──────────────────────────────────────────────────────────────
MAX_TOKENS     = int(os.getenv("MAX_TOKENS", "4096"))
TEMPERATURE    = float(os.getenv("TEMPERATURE", "0.7"))

# ── Enabled LLMs ──────────────────────────────────────────────────────────────
# Only LLMs with a key present are active — avoids errors if a key is missing.
def enabled_llms() -> list[str]:
    candidates = {
        "claude":   ANTHROPIC_API_KEY,
        "gpt":      OPENAI_API_KEY,
        "gemini":   GOOGLE_API_KEY,
        "deepseek": DEEPSEEK_API_KEY,
    }
    return [name for name, key in candidates.items() if key]

# ── Sanity check (imported at startup) ────────────────────────────────────────
def validate() -> list[str]:
    """Return a list of warning strings for any missing keys."""
    warnings = []
    if not ANTHROPIC_API_KEY:
        warnings.append("ANTHROPIC_API_KEY not set — Claude will be disabled.")
    if not OPENAI_API_KEY:
        warnings.append("OPENAI_API_KEY not set — GPT will be disabled.")
    if not GOOGLE_API_KEY:
        warnings.append("GOOGLE_API_KEY not set — Gemini will be disabled.")
    if not DEEPSEEK_API_KEY:
        warnings.append("DEEPSEEK_API_KEY not set — DeepSeek will be disabled.")
    if not TAVILY_API_KEY:
        warnings.append("TAVILY_API_KEY not set — web search will be disabled.")
    return warnings
