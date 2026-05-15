"""
test_live_llms.py — Live integration tests that hit real LLM APIs.

Requires API keys in .env. Each enabled LLM gets a simple prompt
and we verify we get a non-empty response back.

Run from project root:
  PYTHONPATH=/path/to/parent python groupthink/test_live_llms.py
"""

import asyncio
import sys
from pathlib import Path

import groupthink.config as cfg
from groupthink.core.llm_router import LLMRouter, build_llms

PASS = "✅"
FAIL = "❌"
results = []

def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    msg = f"  {status} {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results.append(condition)


PROMPT = "In one sentence, what is the capital of France?"

async def run_live_tests():
    enabled = cfg.enabled_llms()
    print(f"\n── Enabled LLMs: {enabled or '(none)'} ────────────────────────────────")

    if not enabled:
        print("  ⚠️  No API keys found in .env — nothing to test.")
        sys.exit(1)

    llms = build_llms(enabled)
    router = LLMRouter(llms)

    print(f"\n── Live queries: '{PROMPT}' ─────────────────────────────────────────")
    responses = await router.query_all(PROMPT)

    for r in responses:
        label = f"{r.llm} ({r.model})"
        if r.ok:
            preview = r.content.strip().replace("\n", " ")[:80]
            check(f"{label} responded", True, f"{r.elapsed:.2f}s — \"{preview}\"")
            check(f"{label} mentions Paris", "Paris" in r.content or "paris" in r.content.lower())
        else:
            check(f"{label} responded", False, r.error)
            check(f"{label} mentions Paris", False, "skipped — error")

    return responses

responses = asyncio.run(run_live_tests())

print(f"\n── Results: {sum(results)}/{len(results)} passed ──────────────────────────────────────")
if all(results):
    print("All live tests passed! ✅")
else:
    failed = [i + 1 for i, ok in enumerate(results) if not ok]
    print(f"Failed test indices: {failed}")
    sys.exit(1)
