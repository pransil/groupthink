# Groupthink

A desktop research assistant that sends your questions to multiple AI models simultaneously, then runs a "GroupThink" round where each model reviews and improves on the others' answers — producing a final synthesized summary grounded in current web sources.

---

## What It Does

1. **Multi-model fan-out** — your research prompt is sent concurrently to Claude, GPT, Gemini, and DeepSeek.
2. **Web search grounding** — optional Tavily search fetches current sources before querying the models.
3. **GroupThink iteration** — all model responses are combined and sent back to every model, asking each to verify facts, add new information, and improve the overall research.
4. **Synthesized summary** — the best understanding from all models is distilled into a single final summary.
5. **Persistent topics** — all outputs are saved as plain Markdown files, organized by topic and iteration number, so your research accumulates over time.

---

## Requirements

- Python 3.11+
- macOS (PyQt6 native; other platforms untested)
- API keys for whichever LLMs and search you want to use (see below)

---

## Installation

```bash
# Clone the repo
git clone https://github.com/pransil/groupthink.git
cd groupthink

# Install dependencies
pip install anthropic openai google-genai tavily-python python-dotenv aiofiles qasync PyQt6
```

---

## API Keys

Groupthink reads all credentials from a `.env` file in the project root. The app works with any subset of keys — models without a key are automatically disabled.

### Step 1 — Create your `.env` file

```bash
cp .env.example .env
```

### Step 2 — Fill in your keys

Open `.env` in any text editor and add the keys for the services you want:

```
ANTHROPIC_API_KEY=sk-ant-...        # Claude
OPENAI_API_KEY=sk-...               # GPT
GOOGLE_API_KEY=AIza...              # Gemini
DEEPSEEK_API_KEY=sk-...             # DeepSeek
TAVILY_API_KEY=tvly-...             # Web search
```

**The `.env` file is listed in `.gitignore` and will never be committed.**

### Where to get each key

| Service | Where to get it |
|---|---|
| **Anthropic (Claude)** | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| **OpenAI (GPT)** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **Google (Gemini)** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| **DeepSeek** | [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys) |
| **Tavily** | [app.tavily.com](https://app.tavily.com) → API Keys |

You need at least one LLM key to use the app. Tavily is optional but recommended — without it, responses are based on each model's training data only.

---

## Running

```bash
python main.py
```

The app opens a native desktop window. From there:

1. **Create a topic** — give it a name and brief description; this creates a dedicated directory under `topics/` where all research for that topic is saved.
2. **Enter a research prompt** — type your question or research goal in the topic panel.
3. **Run GroupThink** — click the GroupThink button to fan out to all enabled models, run the verification round, and produce a summary. Results appear in the iteration view and are saved to disk automatically.
4. **Iterate** — run additional rounds on the same topic to deepen the research; each iteration builds on the previous.

---

## Optional Configuration

You can override defaults in your `.env` file:

```
GROUPTHINK_TOPICS_DIR=/path/to/your/topics   # default: groupthink/topics/
CLAUDE_MODEL=claude-sonnet-4-6
GPT_MODEL=gpt-4o
GEMINI_MODEL=gemini-2.5-pro
DEEPSEEK_MODEL=deepseek-reasoner
MAX_TOKENS=4096
TEMPERATURE=0.7
```

---

## Output Files

All research is saved as plain Markdown under `topics/<topic-slug>/`:

```
topics/my-topic/
├── topic.md                          ← current topic definition
├── sources.md                        ← running list of web sources
├── iter_01_claude.md                 ← Claude's initial response
├── iter_01_gpt.md
├── iter_01_gemini.md
├── iter_01_deepseek.md
├── iter_01_groupthink_input.md       ← all responses combined
├── iter_01_groupthink_claude.md      ← each model's verification pass
├── iter_01_groupthink_gpt.md
├── iter_01_groupthink_gemini.md
├── iter_01_groupthink_deepseek.md
├── iter_01_summary.md                ← final synthesized summary
└── iter_02_...                       ← next iteration
```

Files are human-readable outside the app — open them in any Markdown viewer or editor.

---

## Running Tests

```bash
# From the parent directory of groupthink/
PYTHONPATH=/path/to/parent python groupthink/test_phase1.py
PYTHONPATH=/path/to/parent python groupthink/test_phase2.py
```

Phase 1 and Phase 2 tests run without real API keys.
