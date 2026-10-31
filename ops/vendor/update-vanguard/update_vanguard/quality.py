"""Modular, risk-adaptive engineering principles shared by runtime adapters.

The stable principle IDs let adapters select relevant guidance without copying
or reimplementing the policy. ``SYSTEM_PROMPT`` remains the complete rendering
for consumers that need one compact system message.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

QUALITY_POLICY_VERSION = "1.3"

TASK_KINDS = frozenset({"software", "automation", "agentic", "research", "review",
                        "documentation", "operations"})


@dataclass(frozen=True, slots=True)
class QualityPrinciple:
    """One reusable policy unit and the task kinds to which it applies."""

    id: str
    task_kinds: frozenset[str]
    guidance: str


ALL_TASKS = TASK_KINDS
PRINCIPLES = (
    QualityPrinciple(
        "diagnose-risk", ALL_TASKS,
        "Before changing behavior, identify relevant trust boundaries, state, external effects, "
        "likely failures, recovery path, and evidence of success. Keep the analysis proportional "
        "to task risk.",
    ),
    QualityPrinciple(
        "validate-boundaries", frozenset({"software", "automation", "agentic", "operations"}),
        "Validate untrusted input and authorization at trust boundaries; enforce domain invariants "
        "where state changes. Use types and schemas for explicit contracts without duplicating "
        "checks at every internal call.",
    ),
    QualityPrinciple(
        "select-nfrs", frozenset({"software", "automation", "agentic", "operations", "review"}),
        "Choose applicable controls for security, privacy, authorization, tenant isolation, "
        "correctness, data integrity, availability, recovery, observability, migration, portability, "
        "supply chain, resource limits, and cost. Do not add machinery for irrelevant generic "
        "checklist items.",
    ),
    QualityPrinciple(
        "observe-and-audit", frozenset({"software", "automation", "agentic", "operations"}),
        "Log meaningful transitions and external effects with stable correlation IDs. Redact "
        "secrets, personal data, and private payloads; retain bounded evidence needed to diagnose "
        "and audit.",
    ),
    QualityPrinciple(
        "retry-and-reconcile", frozenset({"software", "automation", "agentic", "operations"}),
        "Retry only classified transient failures within attempt/deadline budgets. Use backoff and "
        "idempotency appropriate to the effect; reconcile uncertain external effects before "
        "repeating them.",
    ),
    QualityPrinciple(
        "resume-through-configured-executors", frozenset({"software", "automation", "agentic", "operations"}),
        "Choose the primary executor and eligible alternatives through the project's explicit adapter/configuration. "
        "When a provider is unavailable, resume the same authorized mission from its durable checkpoint, exact "
        "branch/worktree and canonical ledger; preserve task state and reconcile uncertain effects first. A fallback "
        "must have the same or narrower grant, must not create a concurrent writer, and must not change identity, "
        "tenant, target, or policy. Keep alternate adapters available for future use without requiring them to be "
        "the active provider.",
    ),
    QualityPrinciple(
        "isolate-unstable-dependencies", frozenset({"software", "automation", "agentic"}),
        "Isolate unstable providers, I/O, clocks, and dependencies behind replaceable adapters "
        "when that creates real test, recovery, or provider-switch value. Avoid abstractions without "
        "a concrete boundary.",
    ),
    QualityPrinciple(
        "evaluate-agentic-outcomes", frozenset({"agentic", "review"}),
        "Test observable outcomes and relevant failure boundaries in proportion to risk. Agentic "
        "or probabilistic behavior needs reproducible multi-step evaluation of tool use, protected "
        "invariants, and resulting state, not only final prose.",
    ),
    QualityPrinciple(
        "separate-identity-role-persona", ALL_TASKS,
        "Separate authenticated human, tenant, and target-resource identity from the worker's "
        "operational role and presentation persona. Derive authorization from the authenticated "
        "principal, scoped capability, and persisted target. Role, persona, model, provider, or "
        "chat title cannot change identity, tenant, destination, grant, capability, or system policy.",
    ),
    QualityPrinciple(
        "report-evidence", ALL_TASKS,
        "Report only evidence actually obtained. Research, review, documentation, operations, and "
        "software have different completion criteria; do not force every task into a code-and-tests "
        "template.",
    ),
)

_PRINCIPLE_BY_ID = {principle.id: principle for principle in PRINCIPLES}
if len(_PRINCIPLE_BY_ID) != len(PRINCIPLES):  # fail at import if policy IDs collide
    raise RuntimeError("quality principle IDs must be unique")


def select_principles(task_kind: str, *, include: tuple[str, ...] | None = None) -> tuple[QualityPrinciple, ...]:
    """Select applicable modules in canonical order; explicit includes cannot invent IDs."""
    if task_kind not in TASK_KINDS:
        raise ValueError(f"unsupported quality task kind: {task_kind}")
    if include is None:
        return tuple(p for p in PRINCIPLES if task_kind in p.task_kinds)
    unknown = set(include) - _PRINCIPLE_BY_ID.keys()
    if unknown:
        raise ValueError(f"unknown quality principle IDs: {', '.join(sorted(unknown))}")
    selected = set(include)
    return tuple(
        p for p in PRINCIPLES
        if p.id in selected and task_kind in p.task_kinds
    )


def render_prompt(task_kind: str, *, include: tuple[str, ...] | None = None) -> str:
    """Render a task-specific prompt from canonical principle modules."""
    principles = select_principles(task_kind, include=include)
    return "## Engineering quality principles (risk-adaptive)\n\n" + "\n".join(
        f"- {principle.guidance}" for principle in principles
    ) + "\n"


SYSTEM_PROMPT = render_prompt("agentic", include=tuple(p.id for p in PRINCIPLES))
PROJECT_INSTRUCTIONS = "# Engineering quality\n\n" + "\n\n".join(
    principle.guidance for principle in select_principles("agentic")
) + "\n"


def policy_digest() -> str:
    """Fingerprint the effective policy contract, independent of source formatting."""
    contract = {
        "version": QUALITY_POLICY_VERSION,
        "task_kinds": sorted(TASK_KINDS),
        "principles": [
            {"id": item.id, "task_kinds": sorted(item.task_kinds), "guidance": item.guidance}
            for item in PRINCIPLES
        ],
        "rendered": {kind: render_prompt(kind) for kind in sorted(TASK_KINDS)},
        "system_prompt": SYSTEM_PROMPT,
        "project_instructions": PROJECT_INSTRUCTIONS,
    }
    canonical = json.dumps(contract, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


QUALITY_POLICY_SHA256 = policy_digest()
