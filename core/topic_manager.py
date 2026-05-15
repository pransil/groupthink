"""
topic_manager.py — Manages topic directories, versioned topic files,
and the naming/creation of all iteration output files.

Directory layout per topic:
    topics/<slug>/
        topic.md                          # Current topic definition
        topic_v01.md, topic_v02.md, ...   # Older versions (auto-archived)
        sources.md                        # Running list of useful sources
        iter_01_claude.md
        iter_01_gpt.md
        iter_01_gemini.md
        iter_01_deepseek.md
        iter_01_groupthink_input.md
        iter_01_groupthink_claude.md
        iter_01_groupthink_gpt.md
        iter_01_groupthink_gemini.md
        iter_01_groupthink_deepseek.md
        iter_01_summary.md
        iter_02_claude.md
        ...
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from groupthink import config


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Convert a topic name to a safe directory name."""
    slug = name.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)       # remove punctuation
    slug = re.sub(r"[\s_]+", "-", slug)         # spaces/underscores → hyphens
    slug = re.sub(r"-+", "-", slug).strip("-")  # collapse hyphens
    return slug[:80]                            # cap length


def _iter_prefix(iteration: int) -> str:
    return f"iter_{iteration:02d}"


# ── TopicManager ──────────────────────────────────────────────────────────────

class TopicManager:
    """
    All filesystem operations for a single research topic.

    Usage:
        tm = TopicManager.create("Quantum Computing and Cryptography")
        # or
        tm = TopicManager.load("quantum-computing-and-cryptography")
    """

    def __init__(self, topic_dir: Path):
        self.dir = topic_dir
        self.slug = topic_dir.name

    # ── Construction ──────────────────────────────────────────────────────────

    @classmethod
    def create(cls, name: str, description: str = "") -> "TopicManager":
        """Create a new topic directory. Raises ValueError if it already exists."""
        slug = _slugify(name)
        topic_dir = config.TOPICS_DIR / slug
        if topic_dir.exists():
            raise ValueError(
                f"Topic '{slug}' already exists. Use TopicManager.load() instead."
            )
        topic_dir.mkdir(parents=True)

        tm = cls(topic_dir)
        # Write initial topic.md
        content = _initial_topic_md(name, description)
        tm._topic_file().write_text(content, encoding="utf-8")
        # Write empty sources.md
        tm._sources_file().write_text(_initial_sources_md(name), encoding="utf-8")
        return tm

    @classmethod
    def load(cls, slug: str) -> "TopicManager":
        """Load an existing topic by its slug."""
        topic_dir = config.TOPICS_DIR / slug
        if not topic_dir.exists():
            raise FileNotFoundError(f"No topic directory found for slug '{slug}'.")
        return cls(topic_dir)

    @classmethod
    def list_all(cls) -> list["TopicManager"]:
        """Return TopicManager instances for every existing topic directory."""
        if not config.TOPICS_DIR.exists():
            return []
        return sorted(
            [cls(d) for d in config.TOPICS_DIR.iterdir() if d.is_dir()],
            key=lambda t: t.slug,
        )

    # ── Topic file ────────────────────────────────────────────────────────────

    def _topic_file(self) -> Path:
        return self.dir / "topic.md"

    def read_topic(self) -> str:
        return self._topic_file().read_text(encoding="utf-8")

    def update_topic(self, new_content: str) -> Path:
        """
        Archive the current topic.md as topic_vNN.md, then write new content.
        Returns the path to the new topic.md.
        """
        current = self._topic_file()
        if current.exists():
            version = self._next_topic_version()
            archive_path = self.dir / f"topic_v{version:02d}.md"
            shutil.copy2(current, archive_path)
        current.write_text(new_content, encoding="utf-8")
        return current

    def _next_topic_version(self) -> int:
        existing = list(self.dir.glob("topic_v*.md"))
        if not existing:
            return 1
        nums = []
        for p in existing:
            m = re.search(r"topic_v(\d+)\.md", p.name)
            if m:
                nums.append(int(m.group(1)))
        return max(nums) + 1 if nums else 1

    def topic_versions(self) -> list[Path]:
        """Return archived topic version files, oldest first."""
        versions = list(self.dir.glob("topic_v*.md"))
        return sorted(versions, key=lambda p: p.name)

    # ── Sources file ──────────────────────────────────────────────────────────

    def _sources_file(self) -> Path:
        return self.dir / "sources.md"

    def read_sources(self) -> str:
        return self._sources_file().read_text(encoding="utf-8")

    def append_source(self, source: str, notes: str = "") -> None:
        """Append a source entry to sources.md."""
        entry = f"\n- {source}"
        if notes:
            entry += f"\n  - {notes}"
        with self._sources_file().open("a", encoding="utf-8") as f:
            f.write(entry + "\n")

    # ── Iteration files ───────────────────────────────────────────────────────

    def current_iteration(self) -> int:
        """Return the highest iteration number present (0 if none)."""
        files = list(self.dir.glob("iter_*.md"))
        if not files:
            return 0
        nums = []
        for p in files:
            m = re.match(r"iter_(\d+)_", p.name)
            if m:
                nums.append(int(m.group(1)))
        return max(nums) if nums else 0

    def next_iteration(self) -> int:
        return self.current_iteration() + 1

    def iter_file(self, iteration: int, label: str) -> Path:
        """
        Return the path for a specific iteration file.
        label examples: 'claude', 'gpt', 'groupthink_input', 'summary'
        """
        fname = f"{_iter_prefix(iteration)}_{label}.md"
        return self.dir / fname

    def write_iter_file(self, iteration: int, label: str, content: str) -> Path:
        """Write content to an iteration file and return the path."""
        path = self.iter_file(iteration, label)
        path.write_text(content, encoding="utf-8")
        return path

    def read_iter_file(self, iteration: int, label: str) -> Optional[str]:
        path = self.iter_file(iteration, label)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def iter_files_for(self, iteration: int) -> dict[str, Path]:
        """Return all files present for a given iteration, keyed by label."""
        prefix = _iter_prefix(iteration)
        result = {}
        for p in sorted(self.dir.glob(f"{prefix}_*.md")):
            label = p.stem[len(prefix) + 1:]  # strip "iter_NN_"
            result[label] = p
        return result

    def all_iterations(self) -> list[int]:
        """Return sorted list of all iteration numbers present."""
        files = list(self.dir.glob("iter_*.md"))
        nums = set()
        for p in files:
            m = re.match(r"iter_(\d+)_", p.name)
            if m:
                nums.add(int(m.group(1)))
        return sorted(nums)

    # ── Repr ──────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"TopicManager(slug={self.slug!r}, iterations={self.all_iterations()})"


# ── File content templates ────────────────────────────────────────────────────

def _initial_topic_md(name: str, description: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = description.strip() if description else "_No description yet._"
    return f"""# {name}

**Created:** {ts}

## Topic Description

{body}

## Research Questions

_Add your research questions here._

## Scope & Constraints

_Define scope, time frame, geographic focus, etc._

## Notes

_Running notes go here._
"""


def _initial_sources_md(name: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""# Sources — {name}

**Created:** {ts}

## Curated Sources

_Sources will be added here as the research progresses._
"""
