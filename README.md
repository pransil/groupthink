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

## Quick Start (pre-built app)

If someone shared a pre-built copy of Groupthink with you:

**Mac**
1. Open the `.dmg` file and drag **Groupthink** to your Applications folder.
2. Double-click Groupthink to launch it.
3. Click **Settings → API Keys** and paste in your API keys (see [Where to get each key](#where-to-get-each-key) below).
4. Click OK — the app is ready to use.

**Windows**
1. Double-click `Groupthink.exe` to run it. (If Windows warns "unrecognized app", click "More info" → "Run anyway".)
2. Click **Settings → API Keys** and paste in your API keys.
3. Click OK — the app is ready to use.

> Keys are saved on your computer in a private settings folder and are never sent anywhere except the respective AI service.

---

## Where to get each key

You need **at least one LLM key** to use the app. Tavily is optional but recommended — without it, responses are based only on each model's training data.

| Service | Sign up / get key | Notes |
|---|---|---|
| **Anthropic (Claude)** | [console.anthropic.com](https://console.anthropic.com) → API Keys | Recommended |
| **OpenAI (GPT)** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | |
| **Google (Gemini)** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Free tier available |
| **DeepSeek** | [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys) | Very affordable |
| **Tavily** | [app.tavily.com](https://app.tavily.com) → API Keys | Web search (optional) |

---

## Using the App

1. **Create a topic** — click **+ New Topic**, give it a name and brief description. This creates a folder where all your research for that topic is saved.
2. **Enter a research prompt** — type your question or research goal in the topic panel.
3. **Run GroupThink** — click the GroupThink button to query all enabled models, run a verification round, and produce a summary. Results appear in the iteration view and are saved automatically.
4. **Iterate** — run additional rounds on the same topic to deepen the research; each iteration builds on the previous.
5. **Adjust models** — click **Settings → Models** to enable/disable individual LLMs or change quality tiers (higher tiers use more capable, more expensive models).

---

## Developer Setup (run from source)

### Requirements

- Python 3.11+
- macOS or Windows
- API keys for whichever LLMs and search you want (see above)

### Install

```bash
# Clone the repo one level up, so the package resolves correctly
git clone https://github.com/pransil/groupthink.git
cd groupthink

# Install dependencies
pip install anthropic openai google-genai tavily-python python-dotenv aiofiles qasync PyQt6 PyQt6-WebEngine
```

### API keys (developer mode)

```bash
cp .env.example .env
# Open .env and fill in your keys, or use Settings → API Keys in the running app
```

### Run

```bash
# From the parent directory of groupthink/
PYTHONPATH=. python groupthink/main.py
```

### Optional `.env` overrides

```
GROUPTHINK_TOPICS_DIR=/path/to/your/topics   # default: groupthink/topics/
MAX_TOKENS=4096
TEMPERATURE=0.7
```

---

## Building the App (for distribution)

The GitHub Actions workflow at `.github/workflows/build.yml` builds both platforms automatically when you push a version tag:

```bash
git tag v1.0.0
git push --tags
```

This produces a Mac `.dmg` and a Windows `.exe` attached to a GitHub release.

To build locally:

```bash
pip install pyinstaller
# Run from the *parent* directory of groupthink/
pyinstaller groupthink/groupthink.spec
# Mac: dist/Groupthink.app
# Windows: dist/Groupthink.exe
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
PYTHONPATH=. python groupthink/test_phase1.py
PYTHONPATH=. python groupthink/test_phase2.py
```

Phase 1 and Phase 2 tests run without real API keys.
