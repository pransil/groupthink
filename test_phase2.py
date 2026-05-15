"""
test_phase2.py — Tests for web_search, groupthink, and session_manager (Phase 2).

Section 1: Offline/structural tests (no API keys needed)
Section 2: Live end-to-end GroupThink iteration (requires API keys in .env)

Run from parent directory:
  PYTHONPATH=/path/to/parent python groupthink/test_phase2.py
"""

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import groupthink.config as cfg

# Point config at a temp dir
_tmp = tempfile.mkdtemp(prefix="groupthink_test2_")
cfg.TOPICS_DIR = Path(_tmp)

from groupthink.core.topic_manager import TopicManager
from groupthink.core.llm_router import LLMResponse, LLMRouter
from groupthink.core.web_search import SearchResult, WebSearch
from groupthink.core.groupthink import GroupThink, IterationResult, _build_research_prompt, _build_groupthink_prompt
from groupthink.core.session_manager import SessionManager, SessionState, TopicSession

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


# ─────────────────────────────────────────────────────────────────────────────
# Section 1: Offline tests
# ─────────────────────────────────────────────────────────────────────────────
print("\n── SearchResult ─────────────────────────────────────────────────────")

sr_ok = SearchResult(
    query="test query",
    results=[{"title": "Test", "url": "https://example.com", "content": "Some content", "score": 0.95}],
    answer="A synthesized answer.",
)
sr_err = SearchResult(query="bad query", results=[], answer=None, error="API timeout")

check("SearchResult.ok True",           sr_ok.ok)
check("SearchResult.ok False on error", not sr_err.ok)
check("to_markdown has query",          "test query" in sr_ok.to_markdown())
check("to_markdown has answer",         "synthesized" in sr_ok.to_markdown())
check("to_markdown has url",            "example.com" in sr_ok.to_markdown())
check("to_markdown error has ERROR",    "ERROR" in sr_err.to_markdown())
check("urls() returns list",            sr_ok.urls() == ["https://example.com"])
check("urls() empty on error",          sr_err.urls() == [])


print("\n── WebSearch construction ────────────────────────────────────────────")

# WebSearch raises if no key
old_key = cfg.TAVILY_API_KEY
cfg.TAVILY_API_KEY = ""
try:
    WebSearch()
    check("WebSearch raises without key", False, "no exception")
except RuntimeError:
    check("WebSearch raises without key", True)
cfg.TAVILY_API_KEY = old_key


print("\n── Prompt builders ──────────────────────────────────────────────────")

prompt = _build_research_prompt(
    query="What is quantum entanglement?",
    topic_content="# Quantum Computing\n\nSome topic info.",
    sources_content="## Sources\n\n- arxiv.org",
    search_result=sr_ok,
)
check("research prompt has query",          "quantum entanglement" in prompt)
check("research prompt has topic context",  "Quantum Computing" in prompt)
check("research prompt has sources",        "arxiv.org" in prompt)
check("research prompt has search result",  "synthesized" in prompt)

prompt_no_search = _build_research_prompt("Q", "Topic", "Sources", search_result=None)
check("research prompt without search ok",  "Q" in prompt_no_search)

gt_prompt = _build_groupthink_prompt("original query", "## CLAUDE\n\nSome response")
check("gt prompt has original query",       "original query" in gt_prompt)
check("gt prompt has combined responses",   "CLAUDE" in gt_prompt)


print("\n── IterationResult ──────────────────────────────────────────────────")

ir = IterationResult(iteration=1, topic_slug="test-topic", query="test query")
check("IterationResult.ok with no errors",      ir.ok)
check("IterationResult.successful_llms empty",  ir.successful_llms == [])

ir_with_responses = IterationResult(
    iteration=1, topic_slug="test-topic", query="q",
    initial_responses=[
        LLMResponse(llm="claude", content="Hello", elapsed=1.0, model="claude-opus-4-5"),
        LLMResponse(llm="gpt",    content="",      elapsed=0.5, error="fail", model="gpt-4o"),
    ],
    errors=["gpt failed"],
)
check("IterationResult.ok False with errors",       not ir_with_responses.ok)
check("IterationResult.successful_llms = [claude]", ir_with_responses.successful_llms == ["claude"])


print("\n── SessionManager (offline) ─────────────────────────────────────────")

tm = TopicManager.create("Test Session Topic", "For session tests")
sm = SessionManager()

session = sm.open(tm.slug)
check("open returns TopicSession",          isinstance(session, TopicSession))
check("session slug matches",               session.slug == tm.slug)
check("session starts IDLE",               session.state == SessionState.IDLE)
check("session not running",               not session.is_running)
check("current_iteration is 0",            session.current_iteration == 0)

check("open_slugs has topic",              tm.slug in sm.open_slugs)
check("sessions list has 1",               len(sm.sessions) == 1)
check("get returns session",               sm.get(tm.slug) is session)
check("get unknown returns None",          sm.get("nope") is None)

# open same slug twice returns same object
session2 = sm.open(tm.slug)
check("open same slug returns same obj",   session is session2)

# open_or_create
session3 = sm.open_or_create("Brand New Topic", "desc")
check("open_or_create creates new",        session3.slug == "brand-new-topic")
check("open_slugs has 2 topics",           len(sm.open_slugs) == 2)

sm.close(session3.slug)
check("close removes session",             session3.slug not in sm.open_slugs)
check("other session still open",         tm.slug in sm.open_slugs)

sm.close_all()
check("close_all empties sessions",        sm.open_slugs == [])

# Listener registration
sm2 = SessionManager()
tm2 = TopicManager.create("Listener Topic", "desc")
sm2.open(tm2.slug)

events = []
sm2.add_listener(lambda s: events.append(s.state))
sm2.remove_listener(sm2._listeners[0])
check("remove_listener works",             len(sm2._listeners) == 0)

# list_all_topics
all_topics = SessionManager.list_all_topics()
check("list_all_topics returns list",      isinstance(all_topics, list))
check("list_all_topics non-empty",         len(all_topics) >= 2)


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Mock GroupThink run (no live API)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── GroupThink mock run ──────────────────────────────────────────────")

async def _mock_gt_run():
    tm3 = TopicManager.create("Mock GT Topic", "Testing the GT loop")
    sm3 = SessionManager(use_web_search=False)
    session = sm3.open(tm3.slug)

    # Patch LLMRouter.query_all to return fake responses
    fake_responses = [
        LLMResponse(llm="claude", content="Claude's research findings.", elapsed=1.0, model="claude-opus-4-5"),
        LLMResponse(llm="gpt",    content="GPT's research findings.",    elapsed=0.9, model="gpt-4o"),
    ]
    fake_gt_responses = [
        LLMResponse(llm="claude", content="Claude's verified analysis.", elapsed=1.1, model="claude-opus-4-5"),
        LLMResponse(llm="gpt",    content="GPT's verified analysis.",    elapsed=1.0, model="gpt-4o"),
    ]
    fake_summary = LLMResponse(llm="claude", content="Final synthesized summary.", elapsed=1.5, model="claude-opus-4-5")

    call_count = [0]

    async def fake_query_all(prompt, system="", llm_names=None):
        call_count[0] += 1
        return fake_responses if call_count[0] == 1 else fake_gt_responses

    async def fake_query_one(llm_name, prompt, system=""):
        return fake_summary

    with patch.object(LLMRouter, "query_all", side_effect=fake_query_all), \
         patch.object(LLMRouter, "query_one", side_effect=fake_query_one), \
         patch.object(LLMRouter, "active_llms", new_callable=lambda: property(lambda self: ["claude", "gpt"])):

        events = []
        sm3.add_listener(lambda s: events.append(s.state))
        result = await sm3.run_iteration(session, "What is quantum entanglement?")

    return result, session, tm3, events

result, session, tm3, events = asyncio.run(_mock_gt_run())

check("mock run ok",                        result.ok)
check("iteration is 1",                     result.iteration == 1)
check("2 initial responses",                len(result.initial_responses) == 2)
check("2 gt responses",                     len(result.groupthink_responses) == 2)
check("summary not empty",                  len(result.summary) > 0)
check("summary has content",                "Final synthesized" in result.summary)
check("files dict has claude",              "claude" in result.files)
check("files dict has gpt",                "gpt" in result.files)
check("files dict has groupthink_input",    "groupthink_input" in result.files)
check("files dict has groupthink_claude",   "groupthink_claude" in result.files)
check("files dict has summary",             "summary" in result.files)
check("all files exist on disk",            all(p.exists() for p in result.files.values()))
check("claude file has content",            "Claude's research" in result.files["claude"].read_text())
check("summary file has query",             "quantum entanglement" in result.files["summary"].read_text())
check("session state is IDLE after run",    session.state == SessionState.IDLE)
check("session last_result set",            session.last_result is result)
check("listener got RUNNING then IDLE",     events == [SessionState.RUNNING, SessionState.IDLE])
check("topic current_iteration is 1",       session.current_iteration == 1)

# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Live end-to-end GT run (skipped if no keys)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Live GroupThink run ──────────────────────────────────────────────")

enabled = cfg.enabled_llms()
if not enabled:
    print("  ⚠️  No API keys — skipping live test.")
else:
    print(f"  Using LLMs: {enabled}")

    async def _live_gt_run():
        tm_live = TopicManager.create(
            "Phase 2 Live Test",
            "Testing the full GroupThink pipeline with real LLMs.",
        )
        sm_live = SessionManager(use_web_search=bool(cfg.TAVILY_API_KEY))
        session_live = sm_live.open(tm_live.slug)
        result_live = await sm_live.run_iteration(
            session_live,
            "In 2-3 sentences, what is the James Webb Space Telescope best known for?",
        )
        return result_live, session_live

    live_result, live_session = asyncio.run(_live_gt_run())

    check("live run completes",                 True)
    check("live iteration is 1",                live_result.iteration == 1)
    check(f"live got {len(enabled)} responses", len(live_result.initial_responses) == len(enabled))
    check("live all initial ok",                all(r.ok for r in live_result.initial_responses),
          ", ".join(r.error or "" for r in live_result.initial_responses if not r.ok))
    check("live all gt ok",                     all(r.ok for r in live_result.groupthink_responses),
          ", ".join(r.error or "" for r in live_result.groupthink_responses if not r.ok))
    check("live summary mentions Webb",         "Webb" in live_result.summary or "telescope" in live_result.summary.lower())
    check("live summary file exists",           live_result.files.get("summary", Path("/no")).exists())
    check("live session IDLE after run",        live_session.state == SessionState.IDLE)

    if live_result.search_result:
        check("live search ok",                 live_result.search_result.ok)
    else:
        check("live search skipped (no key)",   not bool(cfg.TAVILY_API_KEY))

    print(f"\n  Summary preview: {live_result.summary[:200].strip()}...")


# ─────────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n── Results: {sum(results)}/{len(results)} passed ──────────────────────────────────────")
if all(results):
    print("All Phase 2 tests passed! ✅")
else:
    failed = [i + 1 for i, ok in enumerate(results) if not ok]
    print(f"Failed test indices: {failed}")
    sys.exit(1)

import shutil
shutil.rmtree(_tmp)
