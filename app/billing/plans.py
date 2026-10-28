"""Plan keys. Prices live in Stripe under these lookup keys; limits live in the
`plans` table and are seeded from here."""

from __future__ import annotations

from dataclasses import dataclass

AI_MONTHLY = "ai_monthly"
AI_ANNUAL = "ai_annual"
HYBRID_MONTHLY = "hybrid_monthly"
ASK_TUTOR_SINGLE = "ask_tutor_single"
EXAM_SPRINT = "exam_sprint"

SUBSCRIPTION_PLANS = (AI_MONTHLY, AI_ANNUAL, HYBRID_MONTHLY)
ADDON_PLANS = (ASK_TUTOR_SINGLE, EXAM_SPRINT)
ALL_PLANS = SUBSCRIPTION_PLANS + ADDON_PLANS


@dataclass(frozen=True)
class PlanDefault:
    key: str
    kind: str
    monthly_message_limit: int | None
    daily_message_limit: int | None
    sort_order: int


PLAN_DEFAULTS = (
    PlanDefault(AI_MONTHLY, "subscription", 300, 60, 10),
    PlanDefault(AI_ANNUAL, "subscription", 300, 60, 20),
    PlanDefault(HYBRID_MONTHLY, "subscription", 500, 80, 30),
    PlanDefault(ASK_TUTOR_SINGLE, "addon", None, None, 40),
    PlanDefault(EXAM_SPRINT, "addon", None, None, 50),
)

FREE_PLAN_MONTHLY_LIMIT = 300
