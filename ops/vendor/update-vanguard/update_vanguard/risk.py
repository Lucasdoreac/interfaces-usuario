"""Fail-closed risk classification and action-specific gate evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


Risk = Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
Action = Literal["merge", "deploy"]


@dataclass(frozen=True)
class RiskEvidence:
    package_delta: str | None
    project_imports_affected: bool | None
    runtime_delta: str | None
    api_delta: str | None
    persistent_data_affected: bool | None
    tests_complete: bool | None
    backup_restore_verified: bool | None
    rollback_verified: bool | None
    probes_verified: bool | None

    def to_receipt(self) -> dict[str, str | bool | None]:
        return asdict(self)


def classify(evidence: RiskEvidence) -> tuple[Risk, list[str]]:
    """Classify only complete, recognized evidence; unsupported signals are UNKNOWN."""
    unknown: list[str] = []
    for field in ("package_delta", "project_imports_affected", "runtime_delta", "api_delta", "persistent_data_affected"):
        if getattr(evidence, field) is None:
            unknown.append(f"missing {field}")
    if evidence.package_delta not in {None, "none", "patch", "minor", "major"}:
        unknown.append("unrecognized package_delta")
    if evidence.runtime_delta not in {None, "none", "patch", "minor", "major"}:
        unknown.append("unrecognized runtime_delta")
    if evidence.api_delta not in {None, "none", "compatible", "breaking"}:
        unknown.append("unrecognized api_delta")
    if unknown:
        return "UNKNOWN", sorted(set(unknown))

    if (evidence.package_delta == "major" or evidence.runtime_delta == "major"
            or evidence.api_delta == "breaking" or evidence.persistent_data_affected):
        return "HIGH", []
    if (evidence.package_delta == "minor" or evidence.runtime_delta in {"patch", "minor"}
            or evidence.api_delta == "compatible" or evidence.project_imports_affected):
        return "MEDIUM", []
    return "LOW", []


def evaluate_gates(evidence: RiskEvidence, risk: Risk, action: Action, *,
                   phase: Literal["preflight", "post-deploy"] = "preflight",
                   probe_plan_verified: bool | None = None) -> dict[str, object]:
    """Return phase-specific blockers without executing external effects.

    Preflight validates that deployment has an executable probe plan. Actual
    probe results belong to the post-deploy phase and cannot gate the effect
    that produces them.
    """
    blockers: list[str] = []
    evidence_risk, risk_reasons = classify(evidence)
    if evidence_risk != risk:
        blockers.append("declared risk does not match the calculated evidence risk")
    if risk_reasons and risk != "UNKNOWN":
        blockers.append("risk evidence is incomplete or unrecognized")
    if risk == "UNKNOWN":
        blockers.append("risk is UNKNOWN")
    elif risk not in {"LOW", "MEDIUM", "HIGH"}:
        blockers.append("risk value is invalid")
    # The user-facing rollout runs the complete suite after deployment, against
    # the live candidate. Requiring that receipt before merge creates a cycle:
    # validate is only available after deploy, while deploy needs a merged SHA.
    # The post-deploy acceptance gate remains fail-closed until the exact-SHA
    # suite receipt exists.
    if phase == "post-deploy" and evidence.tests_complete is not True:
        blockers.append("complete applicable test suite is not proven")
    # Merge changes the source reference only. Recovery evidence protects the
    # production effect and therefore belongs to deploy preflight/postflight.
    if action == "deploy" and evidence.rollback_verified is not True:
        blockers.append("rollback strategy is not verified")
    if (action == "deploy" and evidence.persistent_data_affected is True
            and evidence.backup_restore_verified is not True):
        blockers.append("persistent-data backup and restore are not verified")
    if action == "deploy" and phase == "preflight" and probe_plan_verified is not True:
        blockers.append("executable post-deploy health probe plan is not verified")
    if action == "deploy" and phase == "post-deploy" and evidence.probes_verified is not True:
        blockers.append("post-deploy health probes are not verified")
    if phase not in {"preflight", "post-deploy"}:
        blockers.append("unsupported deployment gate phase")
    if phase == "post-deploy" and action != "deploy":
        blockers.append("post-deploy phase only supports deployment")
    if action not in {"merge", "deploy"}:
        blockers.append("unsupported action")
    return {"action": action, "phase": phase, "risk": risk, "allowed": not blockers, "blockers": blockers,
            "probe_plan_verified": probe_plan_verified, "evidence": evidence.to_receipt()}
