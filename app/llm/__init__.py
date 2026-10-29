"""The only package that talks to the AI provider.

- `client.py` wraps the provider SDK (streaming replies, structured JSON classification),
  maps its errors to `LLMError`, and offers `FakeProvider` for tests. Nothing else imports
  the SDK.
- `prompts.py` loads versioned prompt files from `prompts/`; no prompt text lives in code.
- `pricing.py` holds list prices for cost logging.
- `service.py` assembles the layered prompt (base, course module, student context), caches
  the first two layers, runs the gatekeeper and summary calls, streams tutor replies, and
  writes one `llm_calls` row per call with tokens, cost in USD and CHF, latency and prompt
  version, raising cost alerts when thresholds are crossed.

Nothing in this package logs message content, and no name, email or identifier is ever
sent to the provider.
"""
