"""The only module allowed to call the AI provider.

Phase 1 adds: model selection (TUTOR_MODEL, FAST_MODEL), prompt caching of the base
instructions and course module, retries with backoff, timeouts, per-plan limits and a cost
log row per call (internal student ID, model, input/cached/output tokens, USD and CHF cost,
latency, prompt version). No code outside this package may import the provider SDK.

Phase 0 makes no AI calls.
"""
