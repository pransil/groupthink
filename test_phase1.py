"""
test_phase1.py — Tests for topic_manager and llm_router (Phase 1).

Runs without real API keys:
  - topic_manager: fully testable (filesystem only)
  - llm_router: tests structure, instantiation, error-path (no live calls)
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# ── Point config at a temp dir so tests don't touch real topics ───────────────
import groupthink.config as cfg
_tmp = tempfile.mkdtemp(prefix="groupthink_test_")
cfg.TOPICS_DIR = Path(_tmp)

from groupthink.core.topic_manager import TopicManager, _slugify
from groupthink.core.llm_router import (
    LLMResponse, LLMRouter, build_llms, _LLM_CLASSES,
)

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
# topic_manager tests
# ─────────────────────────────────────────────────────────────────────────────
print("\n── TopicManager ─────────────────────────────────────────────────────")

# slugify
check("slugify basic",        _slugify("Hello World")          == "hello-world")
check("slugify punctuation",  _slugify("AI/ML & NLP!")         == "aiml-nlp")
check("slugify spaces",       _slugify("  lots   of   spaces") == "lots-of-spaces")
check("slugify long name",    len(_slugify("x" * 200))         <= 80)

# create
tm = TopicManager.create("Quantum Computing", "Testing QC research")
check("create: dir exists",       tm.dir.exists())
check("create: topic.md exists",  (tm.dir / "topic.md").exists())
check("create: sources.md exists",(tm.dir / "sources.md").exists())
check("create: slug correct",     tm.slug == "quantum-computing")

# duplicate create
try:
    TopicManager.create("Quantum Computing")
    check("duplicate create raises", False, "no exception raised")
except ValueError:
    check("duplicate create raises", True)

# load
tm2 = TopicManager.load("quantum-computing")
check("load: same slug", tm2.slug == tm.slug)

# load nonexistent
try:
    TopicManager.load("does-not-exist")
    check("load nonexistent raises", False)
except FileNotFoundError:
    check("load nonexistent raises", True)

# list_all
all_topics = TopicManager.list_all()
check("list_all: finds 1 topic", len(all_topics) == 1)

# read/update topic
content = tm.read_topic()
check("read_topic: has title",    "Quantum Computing" in content)
check("initial_iteration: 0",     tm.current_iteration() == 0)

tm.update_topic("# Quantum Computing\n\nUpdated description.\n")
versions = tm.topic_versions()
check("update_topic: archives v1",  len(versions) == 1)
check("update_topic: v01 exists",   versions[0].name == "topic_v01.md")
check("update_topic: new content",  "Updated" in tm.read_topic())

# second update → v02
tm.update_topic("# Quantum Computing\n\nSecond update.\n")
check("update_topic: archives v2",  len(tm.topic_versions()) == 2)

# sources
tm.append_source("https://arxiv.org/abs/quant-ph", "Key paper on QC")
sources = tm.read_sources()
check("append_source: URL present", "arxiv.org" in sources)
check("append_source: notes present","Key paper" in sources)

# iteration files
n = tm.next_iteration()
check("next_iteration: 1", n == 1)

path = tm.write_iter_file(1, "claude", "# Claude response\n\nSome text.")
check("write_iter_file: file exists", path.exists())
check("write_iter_file: correct name", path.name == "iter_01_claude.md")

read_back = tm.read_iter_file(1, "claude")
check("read_iter_file: content match", "Claude response" in read_back)

tm.write_iter_file(1, "gpt",              "# GPT response")
tm.write_iter_file(1, "gemini",           "# Gemini response")
tm.write_iter_file(1, "deepseek",         "# DeepSeek response")
tm.write_iter_file(1, "groupthink_input", "# Combined")
tm.write_iter_file(1, "summary",          "# Summary")

files = tm.iter_files_for(1)
check("iter_files_for: 6 files", len(files) == 6)
check("iter_files_for: has claude",  "claude"  in files)
check("iter_files_for: has summary", "summary" in files)

check("all_iterations: [1]", tm.all_iterations() == [1])
check("current_iteration: 1", tm.current_iteration() == 1)
check("next_iteration: 2", tm.next_iteration() == 2)

# nonexistent read
check("read missing iter_file: None",
      tm.read_iter_file(99, "claude") is None)


# ─────────────────────────────────────────────────────────────────────────────
# llm_router tests  (no live API calls)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── LLMRouter ────────────────────────────────────────────────────────")

# LLMResponse
r_ok  = LLMResponse(llm="claude", content="Hello", elapsed=1.2, model="claude-opus-4-5")
r_err = LLMResponse(llm="gpt",    content="",      elapsed=0.5, error="Timeout", model="gpt-4o")
check("LLMResponse.ok True",         r_ok.ok)
check("LLMResponse.ok False on err", not r_err.ok)
check("to_markdown ok has content",  "Hello" in r_ok.to_markdown())
check("to_markdown err has ERROR",   "ERROR" in r_err.to_markdown())

# Registry completeness
for name in ("claude", "gpt", "gemini", "deepseek"):
    check(f"registry has {name}", name in _LLM_CLASSES)

# build_llms with no keys → empty (keys not set in test env)
built = build_llms(cfg.enabled_llms())
check("build_llms empty when no keys", len(built) == 0)

# LLMRouter with no active LLMs
router = LLMRouter()
check("router active_llms empty", router.active_llms == [])

async def _test_query_all_empty():
    results = await router.query_all("test prompt")
    return results

empty_results = asyncio.run(_test_query_all_empty())
check("query_all empty returns []", empty_results == [])

# Simulate error path by monkey-patching a fake LLM
from groupthink.core.llm_router import BaseLLM
import time

class FakeLLM(BaseLLM):
    name = "fake"
    async def query(self, prompt, system=""):
        return LLMResponse(llm="fake", content="Fake response: " + prompt[:20],
                           elapsed=0.01, model="fake-model")

class ErrorLLM(BaseLLM):
    name = "error"
    async def query(self, prompt, system=""):
        return self._timed_error(time.monotonic(), RuntimeError("API down"))

router2 = LLMRouter.__new__(LLMRouter)
router2._llms = {"fake": FakeLLM(), "error": ErrorLLM()}

async def _test_router2():
    responses = await router2.query_all("Hello world this is a test")
    return responses

responses = asyncio.run(_test_router2())
check("query_all returns 2 responses",   len(responses) == 2)
fake_r  = next(r for r in responses if r.llm == "fake")
error_r = next(r for r in responses if r.llm == "error")
check("fake response ok",                fake_r.ok)
check("fake content correct",            "Fake response" in fake_r.content)
check("error response not ok",           not error_r.ok)
check("error message captured",          "API down" in error_r.error)

# query_one
async def _test_query_one():
    r = await router2.query_one("fake", "Single query test")
    return r

r_one = asyncio.run(_test_query_one())
check("query_one returns correct llm",   r_one.llm == "fake")
check("query_one content present",       len(r_one.content) > 0)

# query_one with bad name
async def _test_query_bad():
    try:
        await router2.query_one("nonexistent", "prompt")
        return False
    except KeyError:
        return True

check("query_one bad name raises KeyError", asyncio.run(_test_query_bad()))


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n── Results: {sum(results)}/{len(results)} passed ──────────────────────────────────────")
if all(results):
    print("All tests passed! ✅")
else:
    failed = [i+1 for i, ok in enumerate(results) if not ok]
    print(f"Failed test indices: {failed}")
    sys.exit(1)

# Cleanup
import shutil
shutil.rmtree(_tmp)
