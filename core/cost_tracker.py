"""
cost_tracker.py — Accumulates and persists LLM cost estimates per topic.

Costs are stored in <topic_dir>/costs.json and updated after every iteration.
All figures are estimates based on public pricing — not billing data.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from groupthink import config
from groupthink.core.llm_router import LLMResponse


@dataclass
class UsageRecord:
    llm:           str
    model:         str
    input_tokens:  int
    output_tokens: int
    cost_usd:      float
    timestamp:     str
    iteration:     int
    phase:         str   # "initial" | "groupthink" | "synthesis"


@dataclass
class CostTracker:
    """
    Loads, accumulates, and persists cost records for one topic.

    Usage:
        ct = CostTracker.load(topic_manager)
        ct.add_responses(result.initial_responses, iteration=1, phase="initial")
        ct.add_responses(result.groupthink_responses, iteration=1, phase="groupthink")
        ct.save()
        print(ct.total_cost())          # float USD
        print(ct.cost_by_llm())         # {"claude": 0.05, "gpt": 0.02, ...}
    """

    topic_dir: Path
    records:   list[UsageRecord] = field(default_factory=list)

    # ── Construction ──────────────────────────────────────────────────────────

    @classmethod
    def load(cls, topic_dir: Path) -> "CostTracker":
        tracker = cls(topic_dir=topic_dir)
        costs_file = topic_dir / "costs.json"
        if costs_file.exists():
            try:
                data = json.loads(costs_file.read_text(encoding="utf-8"))
                tracker.records = [UsageRecord(**r) for r in data.get("records", [])]
            except Exception:
                pass  # corrupt file — start fresh
        return tracker

    def save(self) -> None:
        costs_file = self.topic_dir / "costs.json"
        data = {"records": [asdict(r) for r in self.records]}
        costs_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ── Recording ─────────────────────────────────────────────────────────────

    def add_response(self, response: LLMResponse, iteration: int, phase: str) -> None:
        """Record cost for a single LLMResponse (no-op if tokens are zero)."""
        if not response.ok:
            return
        record = UsageRecord(
            llm=response.llm,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            iteration=iteration,
            phase=phase,
        )
        self.records.append(record)

    def add_responses(
        self, responses: list[LLMResponse], iteration: int, phase: str
    ) -> None:
        for r in responses:
            self.add_response(r, iteration, phase)

    # ── Aggregation ───────────────────────────────────────────────────────────

    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.records)

    def cost_by_llm(self) -> dict[str, float]:
        """Return total cost per LLM service name."""
        totals: dict[str, float] = {}
        for r in self.records:
            totals[r.llm] = totals.get(r.llm, 0.0) + r.cost_usd
        return totals

    def total_tokens(self) -> tuple[int, int]:
        """Return (total_input_tokens, total_output_tokens) across all records."""
        return (
            sum(r.input_tokens for r in self.records),
            sum(r.output_tokens for r in self.records),
        )
