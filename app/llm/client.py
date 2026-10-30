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


@dataclass
class BatchRequest:
    custom_id: str
    system: list[dict[str, Any]] | str
    messages: list[dict[str, Any]]
    schema: dict[str, Any] | None
    max_tokens: int
    effort: str


@dataclass
class BatchResult:
    custom_id: str
    status: str  # succeeded | errored | canceled | expired
    text: str | None
    usage: Usage | None
    model: str
    error: str | None = None


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

    async def batch_create(self, *, model: str, requests: list[BatchRequest]) -> str: ...

    async def batch_status(self, batch_id: str) -> str:
        """in_progress | ended | canceling"""
        ...

    async def batch_results(self, batch_id: str) -> list[BatchResult]: ...


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

    async def batch_create(self, *, model: str, requests: list[BatchRequest]) -> str:
        def params(r: BatchRequest) -> dict[str, Any]:
            p: dict[str, Any] = {
                "model": model,
                "max_tokens": r.max_tokens,
                "system": r.system,
                "messages": r.messages,
                "output_config": {"effort": r.effort},
            }
            if r.schema is not None:
                p["output_config"]["format"] = {"type": "json_schema", "schema": r.schema}
            return p

        try:
            batch = await self._client.messages.batches.create(
                requests=[{"custom_id": r.custom_id, "params": params(r)} for r in requests]
            )
        except Exception as exc:  # noqa: BLE001
            err = self._translate(exc)
            log.warning("Batch create failed: %s %s", err.code, err.detail)
            raise err from exc
        return batch.id

    async def batch_status(self, batch_id: str) -> str:
        try:
            batch = await self._client.messages.batches.retrieve(batch_id)
        except Exception as exc:  # noqa: BLE001
            raise self._translate(exc) from exc
        return batch.processing_status

    async def batch_results(self, batch_id: str) -> list[BatchResult]:
        out: list[BatchResult] = []
        try:
            async for item in await self._client.messages.batches.results(batch_id):
                kind = item.result.type
                text = None
                usage = None
                model = ""
                error = None
                if kind == "succeeded":
                    msg = item.result.message
                    text = next((b.text for b in msg.content if b.type == "text"), "")
                    usage = _usage_from(msg.usage, msg.model)
                    model = msg.model
                elif kind == "errored":
                    err = getattr(item.result, "error", None)
                    inner = getattr(err, "error", None)
                    error = str(getattr(inner, "message", None) or getattr(err, "type", "error"))[
                        :300
                    ]
                out.append(BatchResult(item.custom_id, kind, text, usage, model, error))
        except Exception as exc:  # noqa: BLE001
            raise self._translate(exc) from exc
        return out


class DisabledProvider:
    available = False

    async def stream(self, **kwargs: Any) -> AsyncIterator[str | Completion]:
        raise LLMUnavailable()
        yield  # pragma: no cover

    async def structured(self, **kwargs: Any) -> tuple[dict[str, Any], Completion]:
        raise LLMUnavailable()

    async def batch_create(self, **kwargs: Any) -> str:
        raise LLMUnavailable()

    async def batch_status(self, batch_id: str) -> str:
        raise LLMUnavailable()

    async def batch_results(self, batch_id: str) -> list[BatchResult]:
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
    # Batch API: custom_id -> JSON-serialisable result (or Exception); batches end at once.
    batch_answers: dict[str, Any] = field(default_factory=dict)
    batches: dict[str, list[BatchRequest]] = field(default_factory=dict)

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
    "Good start. Switzerland is a federal state made up of 26 cantons, and each canton has "
    "its own constitution, parliament and government.\n\n"
    "The federal level deals with matters such as foreign policy, the army and the currency, "
    "while the cantons keep many other responsibilities.\n\n"
    "Can you say in your own words why this is called a federal system?"
)


def _fake_batch_methods():
    async def batch_create(self, *, model: str, requests: list[BatchRequest]) -> str:
        batch_id = f"fake_batch_{len(self.batches) + 1}"
        self.batches[batch_id] = list(requests)
        self.calls.append(FakeCall("batch", model, None, [{"n": len(requests)}]))
        return batch_id

    async def batch_status(self, batch_id: str) -> str:
        return "ended" if batch_id in self.batches else "in_progress"

    async def batch_results(self, batch_id: str) -> list[BatchResult]:
        out = []
        for r in self.batches.get(batch_id, []):
            answer = self.batch_answers.get(r.custom_id)
            if answer is None:
                out.append(BatchResult(r.custom_id, "errored", None, None, "fake"))
            else:
                out.append(
                    BatchResult(
                        r.custom_id,
                        "succeeded",
                        json.dumps(answer),
                        Usage(input_tokens=3000, output_tokens=1500),
                        "fake-batch-model",
                    )
                )
        return out

    return batch_create, batch_status, batch_results


FakeProvider.batch_create, FakeProvider.batch_status, FakeProvider.batch_results = (
    _fake_batch_methods()
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
