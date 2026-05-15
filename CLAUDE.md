# Groupthink — Project Briefing for Claude Code

This document gives you full context on the Groupthink project so you can
continue building it without needing prior conversation history.

---

## What This App Does

Groupthink is a **desktop research assistant** that:

1. Manages multiple independent research **topics**, each in its own directory
2. Sends research prompts to **multiple LLMs concurrently** (Claude, GPT, Gemini, DeepSeek)
3. Performs **web searches** via the Tavily API to ground research in current sources
4. Runs a **GroupThink iteration**: collects all LLM outputs, sends them back to all
   LLMs asking each to verify facts, improve the research, and summarize — then
   synthesizes a final best summary
5. Saves every output as **plain Markdown files** on the local filesystem, organized
   by topic and iteration number

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | User's primary language |
| GUI | PyQt6 + qasync | Native macOS look; async support for concurrent API calls |
| LLMs | anthropic, openai, google-genai | Claude / GPT / Gemini / DeepSeek (OpenAI-compatible) |
| Web search | tavily-python | Purpose-built for AI research agents |
| Config | python-dotenv | API keys in .env, never hardcoded |
| File I/O | pathlib + aiofiles | All outputs are plain Markdown |

---

## Project Structure

```
groupthink/                        ← project root
├── CLAUDE.md                      ← this file
├── main.py                        ← entry point (Phase 3, not yet built)
├── config.py                      ← API keys, paths, model names ✅
├── .env.example                   ← copy to .env and fill in keys ✅
├── .env                           ← real keys (never commit this)
├── test_phase1.py                 ← 50/50 passing tests ✅
│
├── core/
│   ├── __init__.py
│   ├── topic_manager.py           ← filesystem lifecycle for topics ✅
│   ├── llm_router.py              ← concurrent LLM dispatch ✅
│   ├── groupthink.py              ← GT orchestration (Phase 2, TODO)
│   ├── web_search.py              ← Tavily integration (Phase 2, TODO)
│   └── session_manager.py        ← active session tracking (Phase 2, TODO)
│
├── gui/
│   ├── __init__.py
│   ├── main_window.py             ← app shell (Phase 3, TODO)
│   ├── topic_panel.py             ← per-topic chat/research view (Phase 3, TODO)
│   ├── iteration_view.py          ← side-by-side LLM output display (Phase 3, TODO)
│   └── markdown_renderer.py       ← QWebEngineView Markdown renderer (Phase 3, TODO)
│
└── topics/                        ← all research topic directories live here
    └── <topic-slug>/
        ├── topic.md               ← current topic definition
        ├── topic_v01.md           ← archived prior versions
        ├── sources.md             ← running list of useful sources
        ├── iter_01_claude.md
        ├── iter_01_gpt.md
        ├── iter_01_gemini.md
        ├── iter_01_deepseek.md
        ├── iter_01_groupthink_input.md   ← all outputs combined, sent back to LLMs
        ├── iter_01_groupthink_claude.md  ← each LLM's GT response
        ├── iter_01_groupthink_gpt.md
        ├── iter_01_groupthink_gemini.md
        ├── iter_01_groupthink_deepseek.md
        ├── iter_01_summary.md            ← final synthesized summary
        └── iter_02_...                   ← next iteration
```

---

## What Has Been Built (Phase 1) ✅

### `config.py`
- Reads all API keys from `.env` via `python-dotenv`
- `enabled_llms()` returns only LLMs whose keys are present — safe if some keys are missing
- Configurable model names, max tokens, temperature, and topics directory via env vars
- `validate()` returns human-readable warnings for missing keys

### `core/topic_manager.py` — `TopicManager` class
Full filesystem lifecycle for a single research topic:
- `TopicManager.create(name, description)` — creates slug-named directory, initial `topic.md` and `sources.md`
- `TopicManager.load(slug)` — loads existing topic
- `TopicManager.list_all()` — returns all topics
- `update_topic(content)` — auto-archives old `topic.md` as `topic_v01.md`, `topic_v02.md`, etc.
- `append_source(url, notes)` — appends to `sources.md`
- `write_iter_file(iteration, label, content)` / `read_iter_file(...)` — manages iteration files
- `iter_files_for(iteration)` — returns dict of all files for a given iteration
- `current_iteration()` / `next_iteration()` — iteration number tracking

### `core/llm_router.py` — `LLMRouter` class
- `LLMResponse` dataclass: `llm`, `content`, `elapsed`, `error`, `model`, `.ok`, `.to_markdown()`
- `BaseLLM` abstract class with `async query(prompt, system) -> LLMResponse`
- Concrete classes: `ClaudeLLM`, `GPTLLM`, `GeminiLLM`, `DeepSeekLLM`
  - All errors are caught and returned as `LLMResponse` with `error` set — never raises
  - Gemini uses `run_in_executor` since `google.genai` is synchronous
  - DeepSeek uses the OpenAI SDK pointed at `https://api.deepseek.com`
- `LLMRouter.query_all(prompt, system, llm_names)` — concurrent fan-out via `asyncio.gather()`
- `LLMRouter.query_one(llm_name, prompt, system)` — single LLM query

---

## Build Plan

### Phase 2 — Web Search + GroupThink Orchestration (NEXT)
Files to build:
- `core/web_search.py` — Tavily search, returns structured results, appends to `sources.md`
- `core/groupthink.py` — the full GT loop:
  1. Run initial query on all LLMs → write `iter_NN_<llm>.md` files
  2. Combine all outputs → write `iter_NN_groupthink_input.md`
  3. Send combined file back to all LLMs with GT instructions (verify, improve, summarize)
  4. Write `iter_NN_groupthink_<llm>.md` files
  5. Synthesize best final summary → write `iter_NN_summary.md`
- `core/session_manager.py` — tracks which topics are open, current iteration state

### Phase 3 — GUI Shell
- `main.py` + `gui/main_window.py` — PyQt6 app with sidebar (topic list) + main panel
- `gui/topic_panel.py` — per-topic view with prompt input, progress indicators
- `gui/iteration_view.py` — displays LLM outputs side by side or tabbed

### Phase 4 — Markdown Rendering
- `gui/markdown_renderer.py` — `QWebEngineView` renders `.md` files as HTML in-app

### Phase 5 — Polish
- API key configuration screen
- Error handling and user-facing messages
- Progress bars / spinners during LLM calls

---

## GroupThink Loop — Detailed Spec

When the user triggers a GroupThink iteration, `groupthink.py` should:

```
1. Get topic context (topic.md + sources.md content)
2. Build research prompt from user's query + topic context
3. [OPTIONAL] Run web search via Tavily, append results to sources.md
4. Fan out to all enabled LLMs concurrently → iter_NN_<llm>.md
5. Combine all LLM outputs into iter_NN_groupthink_input.md
6. Send groupthink_input.md to all LLMs with this system prompt:
     "You are reviewing a multi-model research session. For each claim:
      1. Verify facts and flag any errors or unsupported assertions.
      2. Add new information or perspectives that improve the research.
      3. Write a clear, well-structured summary of the best current understanding."
7. Write iter_NN_groupthink_<llm>.md for each response
8. Synthesize all GT responses into iter_NN_summary.md
9. Return all file paths + an overall ResearchResult object to the caller
```

---

## Key Conventions

- **All file I/O uses `pathlib.Path`** — no raw string paths
- **All LLM calls are async** — use `asyncio.gather()` for concurrency; never call sequentially
- **Errors never crash the app** — LLM errors are captured in `LLMResponse.error`
- **Tests go in `test_phaseN.py`** at the project root — run with `PYTHONPATH=<parent> python test_phaseN.py`
- **No API keys in code** — always read from `config.py` which reads from `.env`
- **Markdown only** — all persistent outputs are `.md` files, human-readable outside the app

---

## Running Tests

```bash
# From the parent directory of groupthink/
PYTHONPATH=/path/to/parent python groupthink/test_phase1.py
```

All 50 Phase 1 tests pass without real API keys.

---

## Dependencies

```bash
pip install anthropic openai google-genai tavily-python python-dotenv aiofiles qasync PyQt6
```
