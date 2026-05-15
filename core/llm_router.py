"""
llm_router.py — Dispatch research queries to multiple LLMs concurrently.

Each LLM is a class implementing the BaseLLM interface:
    async def query(prompt: str, system: str = "") -> LLMResponse

LLMRouter fans out to all enabled LLMs in parallel using asyncio.gather().
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import anthropic
from google import genai as google_genai
from google.genai import types as genai_types
from openai import AsyncOpenAI

from groupthink import config

# Models that require max_completion_tokens instead of max_tokens, and no temperature.
_GPT_COMPLETION_TOKEN_MODELS = {"o1", "o1-mini", "o3", "o3-mini", "o4-mini",
                                 "gpt-5", "gpt-5-mini", "gpt-5-nano"}


# ── Response dataclass ────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    llm:          str
    content:      str
    elapsed:      float
    error:        Optional[str] = None
    model:        str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def cost_usd(self) -> float:
        return config.token_cost(self.model, self.input_tokens, self.output_tokens)

    def to_markdown(self) -> str:
        header = f"## {self.llm.upper()} ({self.model})"
        if not self.ok:
            return f"{header}\n\n**ERROR:** {self.error}\n"
        return f"{header}\n\n{self.content}\n"


# ── Base class ────────────────────────────────────────────────────────────────

class BaseLLM(ABC):
    name: str
    _model: str = ""

    @abstractmethod
    async def query(self, prompt: str, system: str = "") -> LLMResponse:
        ...

    def _timed_error(self, start: float, exc: Exception) -> LLMResponse:
        return LLMResponse(
            llm=self.name,
            content="",
            elapsed=time.monotonic() - start,
            error=str(exc),
            model=self._model,
        )


# ── Claude ────────────────────────────────────────────────────────────────────

class ClaudeLLM(BaseLLM):
    name = "claude"

    def __init__(self, model: Optional[str] = None, thinking_budget: int = 0):
        self._client          = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        self._model           = model or config.MODELS["claude"]
        self._thinking_budget = thinking_budget

    async def query(self, prompt: str, system: str = "") -> LLMResponse:
        start   = time.monotonic()
        budget  = self._thinking_budget
        thinking = budget > 0
        try:
            # Extended thinking: max_tokens must exceed budget
            max_tok = max(config.MAX_TOKENS, budget + 4_096) if thinking else config.MAX_TOKENS
            kwargs: dict = dict(
                model=self._model,
                max_tokens=max_tok,
                messages=[{"role": "user", "content": prompt}],
            )
            if system:
                kwargs["system"] = system
            if thinking:
                kwargs["thinking"]    = {"type": "enabled", "budget_tokens": budget}
                kwargs["temperature"] = 1  # required when extended thinking is on

            msg  = await self._client.messages.create(**kwargs)
            text = "\n\n".join(b.text for b in msg.content if b.type == "text")
            return LLMResponse(
                llm=self.name, content=text,
                elapsed=time.monotonic() - start, model=self._model,
                input_tokens=msg.usage.input_tokens,
                output_tokens=msg.usage.output_tokens,
            )
        except Exception as exc:
            return self._timed_error(start, exc)


# ── GPT ───────────────────────────────────────────────────────────────────────

class GPTLLM(BaseLLM):
    name = "gpt"

    def __init__(self, model: Optional[str] = None, **_):
        self._client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self._model  = model or config.MODELS["gpt"]

    async def query(self, prompt: str, system: str = "") -> LLMResponse:
        start = time.monotonic()
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            reasoning = self._model in _GPT_COMPLETION_TOKEN_MODELS
            kwargs: dict = dict(model=self._model, messages=messages)
            if reasoning:
                kwargs["max_completion_tokens"] = config.MAX_TOKENS
            else:
                kwargs["max_tokens"]  = config.MAX_TOKENS
                kwargs["temperature"] = config.TEMPERATURE

            resp = await self._client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content or ""
            return LLMResponse(
                llm=self.name, content=text,
                elapsed=time.monotonic() - start, model=self._model,
                input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            )
        except Exception as exc:
            return self._timed_error(start, exc)


# ── Gemini ────────────────────────────────────────────────────────────────────

class GeminiLLM(BaseLLM):
    name = "gemini"

    def __init__(self, model: Optional[str] = None, thinking_budget: int = 0):
        self._client          = google_genai.Client(api_key=config.GOOGLE_API_KEY)
        self._model           = model or config.MODELS["gemini"]
        self._thinking_budget = thinking_budget

    async def query(self, prompt: str, system: str = "") -> LLMResponse:
        start    = time.monotonic()
        budget   = self._thinking_budget
        contents = f"{system}\n\n{prompt}" if system else prompt
        try:
            gen_config = None
            if budget > 0:
                gen_config = genai_types.GenerateContentConfig(
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=budget)
                )

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    **({"config": gen_config} if gen_config else {}),
                ),
            )
            text  = response.text
            usage = response.usage_metadata
            return LLMResponse(
                llm=self.name, content=text,
                elapsed=time.monotonic() - start, model=self._model,
                input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            )
        except Exception as exc:
            return self._timed_error(start, exc)


# ── DeepSeek ──────────────────────────────────────────────────────────────────

class DeepSeekLLM(BaseLLM):
    name = "deepseek"

    def __init__(self, model: Optional[str] = None, **_):
        self._client = AsyncOpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
        )
        self._model = model or config.MODELS["deepseek"]

    async def query(self, prompt: str, system: str = "") -> LLMResponse:
        start = time.monotonic()
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            resp = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE,
                messages=messages,
            )
            text = resp.choices[0].message.content or ""
            return LLMResponse(
                llm=self.name, content=text,
                elapsed=time.monotonic() - start, model=self._model,
                input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            )
        except Exception as exc:
            return self._timed_error(start, exc)


# ── Registry ──────────────────────────────────────────────────────────────────

_LLM_CLASSES: dict[str, type[BaseLLM]] = {
    "claude":   ClaudeLLM,
    "gpt":      GPTLLM,
    "gemini":   GeminiLLM,
    "deepseek": DeepSeekLLM,
}


def build_llms(
    names:  Optional[list[str]] = None,
    models: Optional[dict[str, str]] = None,
    extras: Optional[dict[str, dict]] = None,
) -> dict[str, BaseLLM]:
    """
    Instantiate LLM clients.
    - names:  which LLMs to build (default: all enabled)
    - models: override model string per LLM  {"claude": "claude-sonnet-4-6", ...}
    - extras: extra constructor kwargs per LLM  {"claude": {"thinking_budget": 16000}, ...}
    """
    if names is None:
        names = config.enabled_llms()
    result = {}
    for name in names:
        if name not in _LLM_CLASSES:
            raise ValueError(f"Unknown LLM: {name!r}. Choose from {list(_LLM_CLASSES)}")
        model = models.get(name) if models else None
        kw    = extras.get(name, {}) if extras else {}
        result[name] = _LLM_CLASSES[name](model=model, **kw)
    return result


# ── Router ────────────────────────────────────────────────────────────────────

class LLMRouter:
    def __init__(
        self,
        llm_names: Optional[list[str]] = None,
        models:    Optional[dict[str, str]]  = None,
        extras:    Optional[dict[str, dict]] = None,
    ):
        self._llms = build_llms(llm_names, models=models, extras=extras)

    @property
    def active_llms(self) -> list[str]:
        return list(self._llms.keys())

    async def query_all(
        self,
        prompt: str,
        system: str = "",
        llm_names: Optional[list[str]] = None,
    ) -> list[LLMResponse]:
        targets = llm_names or self.active_llms
        tasks   = [self._llms[n].query(prompt, system) for n in targets if n in self._llms]
        return await asyncio.gather(*tasks)

    async def query_one(self, llm_name: str, prompt: str, system: str = "") -> LLMResponse:
        if llm_name not in self._llms:
            raise KeyError(f"LLM {llm_name!r} not in router. Active: {self.active_llms}")
        return await self._llms[llm_name].query(prompt, system)
