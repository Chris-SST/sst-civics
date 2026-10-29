"""The only module that imports the AI provider's SDK.

A `Provider` streams text replies and returns structured JSON classifications. The real
implementation wraps the Anthropic SDK; `FakeProvider` scripts responses for tests. Nothing
here logs message content."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass
class Completion:
    text: str
    usage: Usage
    stop_reason: str  # end_turn | max_tokens | refusal | ...
    model: str


class LLMUnavailable(Exception):
    """No API key configured, or the provider is switched off."""


class LLMError(Exception):
    """A provider call failed. `code` is one of timeout, rate_limited, connection, api."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.detail = detail


class Provider(Protocol):
    available: bool

    def stream(
        self,
        *,
        model: str,
        system: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        max_tokens: int,
        effort: str,
        timeout: float,
    ) -> AsyncIterator[str | Completion]: ...

    async def structured(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        max_tokens: int,
        effort: str,
        timeout: float,
    ) -> tuple[dict[str, Any], Completion]: ...


def _usage_from(usage: Any, fallback_model: str) -> Usage:
    return Usage(
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
    )


class AnthropicProvider:
    available = True

    def __init__(self, api_key: str):
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=2)

    def _translate(self, exc: Exception) -> LLMError:
        a = self._anthropic
        if isinstance(exc, a.APITimeoutError):
            return LLMError("timeout")
        if isinstance(exc, a.RateLimitError):
            return LLMError("rate_limited")
        if isinstance(exc, a.APIConnectionError):
            return LLMError("connection")
        if isinstance(exc, a.APIStatusError):
            # The provider's error message describes the request shape (model name, parameter),
            # never the conversation, so it is safe to log.
            reason = ""
            body = getattr(exc, "body", None)
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict):
                    reason = str(err.get("message", ""))[:200]
            return LLMError("api", f"status {exc.status_code} {reason}".strip())
        return LLMError("api", exc.__class__.__name__)

    async def stream(
        self,
        *,
        model: str,
        system: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        max_tokens: int,
        effort: str,
        timeout: float,
    ) -> AsyncIterator[str | Completion]:
        client = self._client.with_options(timeout=timeout)
        try:
            async with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                output_config={"effort": effort},
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
        except Exception as exc:  # noqa: BLE001
            err = self._translate(exc)
            log.warning("AI call failed: %s %s", err.code, err.detail)
            raise err from exc
        text = "".join(b.text for b in final.content if b.type == "text")
        yield Completion(
            text=text,
            usage=_usage_from(final.usage, model),
            stop_reason=final.stop_reason or "end_turn",
            model=final.model or model,
        )

    async def structured(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        max_tokens: int,
        effort: str,
        timeout: float,
    ) -> tuple[dict[str, Any], Completion]:
        client = self._client.with_options(timeout=timeout, max_retries=0)
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                output_config={
                    "effort": effort,
                    "format": {"type": "json_schema", "schema": schema},
                },
            )
        except Exception as exc:  # noqa: BLE001
            err = self._translate(exc)
            log.warning("AI classification failed: %s %s", err.code, err.detail)
            raise err from exc
        text = next((b.text for b in response.content if b.type == "text"), "")
        completion = Completion(
            text=text,
            usage=_usage_from(response.usage, model),
            stop_reason=response.stop_reason or "end_turn",
            model=response.model or model,
        )
        if completion.stop_reason == "refusal" or not text:
            raise LLMError("api", "no structured output")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("api", "invalid json") from exc
        return data, completion


class DisabledProvider:
    available = False

    async def stream(self, **kwargs: Any) -> AsyncIterator[str | Completion]:
        raise LLMUnavailable()
        yield  # pragma: no cover

    async def structured(self, **kwargs: Any) -> tuple[dict[str, Any], Completion]:
        raise LLMUnavailable()


@dataclass
class FakeCall:
    kind: str  # stream | structured
    model: str
    system: Any
    messages: list[dict[str, Any]]


@dataclass
class FakeProvider:
    """Scripted provider for tests. `replies` are consumed in order by `stream`,
    `classifications` by `structured`; when a list runs out the last default is used."""

    replies: list[str | Exception | Completion] = field(default_factory=list)
    classifications: list[dict[str, Any] | Exception] = field(default_factory=list)
    calls: list[FakeCall] = field(default_factory=list)
    available: bool = True
    default_reply: str = "What have you tried so far?"
    default_classification: dict[str, Any] = field(
        default_factory=lambda: {"label": "on_topic", "wellbeing": "none", "coursework": False}
    )

    async def stream(
        self,
        *,
        model: str,
        system: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        max_tokens: int,
        effort: str,
        timeout: float,
    ) -> AsyncIterator[str | Completion]:
        self.calls.append(FakeCall("stream", model, system, messages))
        scripted = self.replies.pop(0) if self.replies else self.default_reply
        if isinstance(scripted, Exception):
            raise scripted
        if isinstance(scripted, Completion):
            for chunk in scripted.text.split(" "):
                yield chunk + " "
            yield scripted
            return
        words = scripted.split(" ")
        for i, w in enumerate(words):
            yield w + (" " if i < len(words) - 1 else "")
        yield Completion(
            text=scripted,
            usage=Usage(input_tokens=1200, output_tokens=len(words) * 2, cache_read_tokens=1000),
            stop_reason="end_turn",
            model=model,
        )

    async def structured(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        max_tokens: int,
        effort: str,
        timeout: float,
    ) -> tuple[dict[str, Any], Completion]:
        self.calls.append(FakeCall("structured", model, system, messages))
        scripted = (
            self.classifications.pop(0) if self.classifications else self.default_classification
        )
        if isinstance(scripted, Exception):
            raise scripted
        return scripted, Completion(
            text=json.dumps(scripted),
            usage=Usage(input_tokens=400, output_tokens=20),
            stop_reason="end_turn",
            model=model,
        )


DEMO_REPLY = (
    "Good start. Remember the log law \\(\\log_a(xy) = \\log_a x + \\log_a y\\).\n\n"
    "If \\(2^x = 10\\), taking logs of both sides gives\n\n"
    "\\[ x = \\log_2 10 = \\frac{\\ln 10}{\\ln 2} \\]\n\n"
    "What do you get to three significant figures?"
)

_provider: Provider | None = None


def get_provider() -> Provider:
    global _provider
    if _provider is None:
        settings = get_settings()
        if settings.llm_fake and settings.app_env in ("dev", "test"):
            _provider = FakeProvider(default_reply=DEMO_REPLY)
        elif settings.anthropic_api_key:
            _provider = AnthropicProvider(settings.anthropic_api_key)
        else:
            _provider = DisabledProvider()
    return _provider


def set_provider(provider: Provider | None) -> None:
    """Tests inject a FakeProvider; None resets to the settings-based default."""
    global _provider
    _provider = provider
