"""
session_manager.py — Tracks open research topics and their current state.

SessionManager is a lightweight in-memory registry that the GUI
will use to know which topics are open, what iteration each is on,
and whether a GroupThink run is in progress.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from groupthink.core.app_settings import SETTINGS
from groupthink.core.groupthink import GroupThink, IterationResult
from groupthink.core.topic_manager import TopicManager


class SessionState(Enum):
    IDLE       = auto()   # No active run
    RUNNING    = auto()   # GT iteration in progress
    ERROR      = auto()   # Last run ended with errors


@dataclass
class TopicSession:
    topic:          TopicManager
    state:          SessionState        = SessionState.IDLE
    last_result:    Optional[IterationResult] = None
    error_message:  str                 = ""

    @property
    def slug(self) -> str:
        return self.topic.slug

    @property
    def current_iteration(self) -> int:
        return self.topic.current_iteration()

    @property
    def is_running(self) -> bool:
        return self.state == SessionState.RUNNING


# Callback type: called when a session's state changes
OnSessionChange = Callable[["TopicSession"], None]


class SessionManager:
    """
    Manages the set of open topic sessions in memory.

    Usage:
        sm = SessionManager()
        session = sm.open("my-topic-slug")
        result  = await sm.run_iteration(session, "What is the latest research on X?")
    """

    def __init__(self, llm_names: Optional[list[str]] = None, use_web_search: bool = True):
        self._sessions: dict[str, TopicSession] = {}
        self._llm_names = llm_names
        self._use_web_search = use_web_search
        self._listeners: list[OnSessionChange] = []

    # ── Session lifecycle ─────────────────────────────────────────────────────

    def open(self, slug: str) -> TopicSession:
        """Load a topic and register it as an open session."""
        if slug in self._sessions:
            return self._sessions[slug]
        topic = TopicManager.load(slug)
        session = TopicSession(topic=topic)
        self._sessions[slug] = session
        return session

    def open_or_create(self, name: str, description: str = "") -> TopicSession:
        """Open an existing topic or create a new one."""
        from groupthink.core.topic_manager import _slugify
        slug = _slugify(name)
        if slug in self._sessions:
            return self._sessions[slug]
        try:
            topic = TopicManager.load(slug)
        except FileNotFoundError:
            topic = TopicManager.create(name, description)
        session = TopicSession(topic=topic)
        self._sessions[slug] = session
        return session

    def close(self, slug: str) -> None:
        """Remove a topic from the open sessions."""
        self._sessions.pop(slug, None)

    def close_all(self) -> None:
        self._sessions.clear()

    @property
    def open_slugs(self) -> list[str]:
        return list(self._sessions.keys())

    @property
    def sessions(self) -> list[TopicSession]:
        return list(self._sessions.values())

    def get(self, slug: str) -> Optional[TopicSession]:
        return self._sessions.get(slug)

    # ── Running iterations ────────────────────────────────────────────────────

    async def run_iteration(
        self,
        session: TopicSession,
        query: str,
        web_search_query: Optional[str] = None,
    ) -> IterationResult:
        """
        Run a GroupThink iteration for the given session.
        Updates session state and notifies listeners.
        Never raises — errors are in IterationResult.errors.
        """
        if session.is_running:
            raise RuntimeError(f"Session '{session.slug}' is already running.")

        session.state = SessionState.RUNNING
        session.error_message = ""
        self._notify(session)

        try:
            gt = GroupThink(
                llm_names=SETTINGS.enabled_llms(),
                models=SETTINGS.model_map(),
                synthesis_llm=SETTINGS.synthesis_llm(),
                synthesis_extras=SETTINGS.synthesis_extras(),
                use_web_search=self._use_web_search,
                search_max_results=SETTINGS.search_max_results(),
                search_full_content=SETTINGS.search_full_content(),
            )
            result = await gt.run(session.topic, query, web_search_query)
            session.last_result = result
            session.state = SessionState.ERROR if result.errors else SessionState.IDLE
            if result.errors:
                session.error_message = "; ".join(result.errors)
        except Exception as exc:
            result = IterationResult(
                iteration=session.current_iteration,
                topic_slug=session.slug,
                query=query,
                errors=[str(exc)],
            )
            session.last_result = result
            session.state = SessionState.ERROR
            session.error_message = str(exc)
        finally:
            self._notify(session)

        return result

    # ── Change listeners (for GUI reactivity) ─────────────────────────────────

    def add_listener(self, callback: OnSessionChange) -> None:
        """Register a callback to be called whenever a session state changes."""
        self._listeners.append(callback)

    def remove_listener(self, callback: OnSessionChange) -> None:
        self._listeners.remove(callback)

    def _notify(self, session: TopicSession) -> None:
        for cb in self._listeners:
            try:
                cb(session)
            except Exception:
                pass

    # ── Convenience: list all available topics ────────────────────────────────

    @staticmethod
    def list_all_topics() -> list[TopicManager]:
        return TopicManager.list_all()
