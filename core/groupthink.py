"""
groupthink.py — GroupThink orchestration loop.

Runs a full GT iteration:
  1. Build research prompt from topic context + user query
  2. (Optional) Web search via Tavily → appended to sources.md
  3. Fan out to all enabled LLMs → iter_NN_<llm>.md
  4. Combine outputs → iter_NN_groupthink_input.md
  5. Send combined file back to all LLMs for verification/improvement
  6. Write iter_NN_groupthink_<llm>.md for each response
  7. Synthesize final summary → iter_NN_summary.md
  8. Return a ResearchResult
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from groupthink import config
from groupthink.core.cost_tracker import CostTracker
from groupthink.core.llm_router import LLMResponse, LLMRouter, build_llms
from groupthink.core.topic_manager import TopicManager
from groupthink.core.web_search import SearchResult, WebSearch


# ── Result objects ────────────────────────────────────────────────────────────

@dataclass
class IterationResult:
    iteration:          int
    topic_slug:         str
    query:              str
    initial_responses:  list[LLMResponse]       = field(default_factory=list)
    groupthink_responses: list[LLMResponse]     = field(default_factory=list)
    search_result:      Optional[SearchResult]  = None
    files:              dict[str, Path]         = field(default_factory=dict)
    summary:            str                     = ""
    errors:             list[str]               = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    @property
    def successful_llms(self) -> list[str]:
        return [r.llm for r in self.initial_responses if r.ok]


# ── Prompts ───────────────────────────────────────────────────────────────────

_WEB_GROUNDING_NOTICE = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LIVE WEB SEARCH — MANDATORY READING BEFORE YOU RESPOND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The web search results in this prompt were retrieved from the live
internet seconds ago. They are REAL articles from REAL URLs.

Your training data has a cutoff date. These results describe events
that occurred AFTER your training cutoff. That does not make them
fabricated — it means the world changed after your training ended.

YOU MUST:
  • Accept web search content as factual and current
  • Report and build on what those sources say
  • Cite the URLs when referencing web content

YOU MUST NOT:
  • Call web-sourced information "hypothetical", "fabricated",
    "hallucinated", or a "scenario"
  • Dismiss web results because you have no training knowledge
    of the events they describe — that is expected and normal
  • Correct web content using your training data
  • Add caveats suggesting the web results might not be real
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

_RESEARCH_SYSTEM = (
    "You are an expert research assistant. Provide thorough, well-structured, "
    "fact-based responses with specific details, examples, and citations where possible. "
    "Organize your response with clear headings and bullet points."
    + _WEB_GROUNDING_NOTICE
)

_GROUPTHINK_SYSTEM = (
    "You are reviewing a multi-model research session.\n\n"
    "Your task:\n"
    "1. Read the live web search results and initial AI responses provided.\n"
    "2. Build on the web-sourced facts — do NOT second-guess or dismiss them.\n"
    "3. Note where AI models disagreed with the web sources and correct them.\n"
    "4. Add analysis, context, and implications based on the verified facts.\n"
    "5. Write a clear, well-structured response grounded in the web evidence.\n"
    + _WEB_GROUNDING_NOTICE
)

_SYNTHESIS_SYSTEM = (
    "You are producing the final synthesis of a multi-model research session.\n\n"
    "YOUR ONLY JOB is to synthesize what the provided web search results and AI responses "
    "actually say. You are a reporter, not a fact-checker against your training data.\n\n"
    "RULES:\n"
    "1. The web search results are the ground truth. Start there.\n"
    "2. Use the AI responses to add analysis and context.\n"
    "3. If an AI response contradicts the web search results, trust the web results.\n"
    "4. Do NOT introduce any information from your training data that isn't in the "
    "provided content — your training data is older than the web results.\n"
    "5. Do NOT use words like 'hypothetical', 'alleged', 'claimed', or 'scenario' "
    "for events described in the web search results — treat them as facts.\n\n"
    "Produce a clear, well-structured summary that faithfully represents the provided content."
    + _WEB_GROUNDING_NOTICE
)


def _build_research_prompt(query: str, topic_content: str, sources_content: str,
                            search_result: Optional[SearchResult] = None) -> str:
    parts = [f"## Research Query\n\n{query}\n"]
    parts.append(f"## Topic Context\n\n{topic_content}\n")
    if sources_content.strip():
        parts.append(f"## Known Sources\n\n{sources_content}\n")
    if search_result and search_result.ok and search_result.results:
        parts.append(f"## Fresh Web Search Results\n\n{search_result.to_markdown()}\n")
    parts.append(
        "Please research this query thoroughly, drawing on the context above "
        "and your own knowledge."
    )
    return "\n".join(parts)


def _build_groupthink_prompt(
    query: str,
    combined_responses: str,
    search_result: Optional[SearchResult] = None,
) -> str:
    parts = [f"## Original Research Query\n\n{query}\n"]
    if search_result and search_result.ok and search_result.results:
        parts.append(
            "## Live Web Search Results (AUTHORITATIVE — retrieved this session)\n\n"
            + search_result.to_markdown() + "\n"
        )
    parts.append(
        "## Initial Responses from Multiple AI Models\n\n"
        + combined_responses + "\n\n"
        "Review the web search results and AI responses above. "
        "Produce an improved analysis that is fully grounded in the web evidence."
    )
    return "\n".join(parts)


def _build_synthesis_prompt(
    query: str,
    gt_responses: list[LLMResponse],
    search_result: Optional[SearchResult] = None,
) -> str:
    parts = [f"## Original Research Query\n\n{query}\n"]
    if search_result and search_result.ok and search_result.results:
        parts.append(
            f"## Live Web Search Results (retrieved this session — treat as authoritative)\n\n"
            f"{search_result.to_markdown()}\n"
        )
    parts.append("## GroupThink Responses from Multiple AI Models\n")
    for r in gt_responses:
        if r.ok:
            parts.append(r.to_markdown())
    parts.append(
        "\nUsing the web search results and GroupThink responses above as your primary source "
        "of truth, synthesize a final definitive summary. Do not introduce facts from your "
        "training data that are not present in the content above."
    )
    return "\n".join(parts)


# ── GroupThink orchestrator ───────────────────────────────────────────────────

class GroupThink:
    """
    Runs a full GroupThink research iteration for a topic.

    Usage:
        gt = GroupThink()
        result = await gt.run(topic, "What are the latest breakthroughs in quantum computing?")
    """

    def __init__(
        self,
        llm_names:           Optional[list[str]]       = None,
        models:              Optional[dict[str, str]]  = None,
        synthesis_llm:       Optional[str]             = None,
        synthesis_extras:    Optional[dict]            = None,
        use_web_search:      bool                      = True,
        search_max_results:  int                       = 5,
        search_full_content: bool                      = False,
    ):
        # Main router: no extended thinking — runs all LLMs for initial + GT passes
        self._router = LLMRouter(llm_names, models=models)
        self._synthesis_llm      = synthesis_llm
        self._synthesis_extras   = synthesis_extras or {}
        self._synthesis_model    = models.get(synthesis_llm, "") if models and synthesis_llm else ""
        self._use_web_search     = use_web_search and bool(config.TAVILY_API_KEY)
        self._search_max_results  = search_max_results
        self._search_full_content = search_full_content
        self._web_search = WebSearch() if self._use_web_search else None

    @property
    def active_llms(self) -> list[str]:
        return self._router.active_llms

    async def run(
        self,
        topic: TopicManager,
        query: str,
        web_search_query: Optional[str] = None,
    ) -> IterationResult:
        """
        Execute a full GroupThink iteration. Returns an IterationResult.
        Never raises — errors are captured in IterationResult.errors.
        """
        iteration = topic.next_iteration()
        result = IterationResult(
            iteration=iteration,
            topic_slug=topic.slug,
            query=query,
        )

        # ── Step 1: Web search (optional) ─────────────────────────────────────
        if self._use_web_search and self._web_search:
            search_q = web_search_query or query
            result.search_result = await self._web_search.search_and_save(
                search_q, topic,
                max_results=self._search_max_results,
                full_content=self._search_full_content,
            )

        cost_tracker = CostTracker.load(topic.dir)

        # ── Step 2: Build research prompt and fan out to all LLMs ─────────────
        topic_content   = topic.read_topic()
        sources_content = topic.read_sources()
        research_prompt = _build_research_prompt(
            query, topic_content, sources_content, result.search_result
        )

        result.initial_responses = await self._router.query_all(
            research_prompt, system=_RESEARCH_SYSTEM
        )

        cost_tracker.add_responses(result.initial_responses, iteration, "initial")

        # Write initial response files
        for r in result.initial_responses:
            label = r.llm
            content = r.to_markdown()
            path = topic.write_iter_file(iteration, label, content)
            result.files[label] = path
            if not r.ok:
                result.errors.append(f"{r.llm} initial query failed: {r.error}")

        # ── Step 3: Combine all outputs → groupthink_input.md ─────────────────
        combined_parts = [f"# GroupThink Input — Iteration {iteration:02d}\n"]
        combined_parts.append(f"**Query:** {query}\n")
        combined_parts.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        for r in result.initial_responses:
            combined_parts.append(r.to_markdown())

        combined_text = "\n".join(combined_parts)
        gt_input_path = topic.write_iter_file(iteration, "groupthink_input", combined_text)
        result.files["groupthink_input"] = gt_input_path

        # ── Step 4: Send combined to all LLMs for GT pass ─────────────────────
        gt_prompt = _build_groupthink_prompt(query, combined_text, result.search_result)
        result.groupthink_responses = await self._router.query_all(
            gt_prompt, system=_GROUPTHINK_SYSTEM
        )

        cost_tracker.add_responses(result.groupthink_responses, iteration, "groupthink")

        # Write GT response files
        for r in result.groupthink_responses:
            label = f"groupthink_{r.llm}"
            content = r.to_markdown()
            path = topic.write_iter_file(iteration, label, content)
            result.files[label] = path
            if not r.ok:
                result.errors.append(f"{r.llm} groupthink query failed: {r.error}")

        # ── Step 5: Synthesize final summary ──────────────────────────────────
        ok_gt = [r for r in result.groupthink_responses if r.ok]
        synthesis_response: Optional[LLMResponse] = None
        if ok_gt:
            synthesis_prompt = _build_synthesis_prompt(query, ok_gt, result.search_result)
            # Use the user-configured synthesis LLM (with its thinking budget if any)
            synthesis_llm = self._synthesis_llm or (
                self.active_llms[0] if self.active_llms else None
            )
            if synthesis_llm:
                synth_llm_instance = build_llms(
                    names=[synthesis_llm],
                    models={synthesis_llm: self._synthesis_model} if self._synthesis_model else None,
                    extras={synthesis_llm: self._synthesis_extras} if self._synthesis_extras else None,
                )[synthesis_llm]
                synthesis_response = await synth_llm_instance.query(
                    synthesis_prompt, system=_SYNTHESIS_SYSTEM
                )
                if synthesis_response.ok:
                    result.summary = synthesis_response.content
                else:
                    result.errors.append(f"Synthesis failed: {synthesis_response.error}")
                    result.summary = "\n\n".join(r.content for r in ok_gt if r.content)
            else:
                result.summary = "\n\n".join(r.content for r in ok_gt if r.content)
        else:
            result.errors.append("All GroupThink responses failed — no summary generated.")

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        summary_content = (
            f"# Research Summary — Iteration {iteration:02d}\n\n"
            f"**Topic:** {topic.slug}\n"
            f"**Query:** {query}\n"
            f"**Date:** {ts}\n\n"
            f"{result.summary}\n"
        )
        summary_path = topic.write_iter_file(iteration, "summary", summary_content)
        result.files["summary"] = summary_path

        if synthesis_response and synthesis_response.ok:
            cost_tracker.add_response(synthesis_response, iteration, "synthesis")
        cost_tracker.save()

        return result
