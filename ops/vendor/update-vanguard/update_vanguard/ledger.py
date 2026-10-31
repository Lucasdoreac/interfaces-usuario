"""Local durable job state and append-only transition receipts.

PARADIGMA: persistência de intenção e recuperação idempotente de jobs.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

STATES = {"planned", "blocked", "running", "uncertain", "completed", "failed", "rolled_back", "cancelled"}
TRANSITIONS = {
    "planned": {"blocked", "running", "cancelled"},
    "blocked": {"planned", "cancelled"},
    "running": {"uncertain", "completed", "failed", "rolled_back", "cancelled", "blocked", "planned"},
    "uncertain": {"blocked", "completed", "failed", "rolled_back"},
    "completed": {"rolled_back"},
    "failed": {"planned", "cancelled"},
    "rolled_back": set(),
    "cancelled": set(),
}



def mission_branches(claims: list[dict[str, Any]], mission_id: int) -> set[str]:
    """The PR branch a mission is linked to: its branch claims, else the one holder of its claims.

    Every caller that ties a merged or closed PR to a mission uses this one link (the gate's
    merge release, ``release --merged-pr``, the reconcile report), so a missing branch claim
    cannot break one of them and not the others. Holders are branch names by convention; a
    mission's claims share one holder (``claim_scope_refusal``).
    """
    own = [claim for claim in claims if int(claim["mission_id"]) == mission_id]
    branches = {claim["target"] for claim in own if claim["kind"] == "branch"}
    if branches:
        return branches
    holders = {claim["holder"] for claim in own}
    return holders if len(holders) == 1 else set()


def _valid_resume_on(value: Any) -> bool:
    import datetime

    if not isinstance(value, str) or not RESUME_ON.fullmatch(value):
        return False
    if value.startswith("date:"):
        try:
            datetime.date.fromisoformat(value[5:])
        except ValueError:
            return False
    return True

class JobLimitError(ValueError):
    pass


class CanonicalPlanError(ValueError):
    """A canonical plan cannot be refreshed without invalidating active work."""


class EffectConflictError(ValueError):
    """An effect key was reused for a different intent or uncertain replay."""


class GrantError(ValueError):
    """A production-effect grant is missing, revoked or outside its scope."""


# Top-level receipt sections the planner owns and rebuilds on every refresh.
# Any other section belongs to a mission (units, unit receipts) and survives.
CORE_RECEIPT_SECTIONS = frozenset({"inventory", "plan", "policy_version", "execution"})

# Operations whose external effect must name the grant that authorized it.
GRANTED_EFFECT_OPERATIONS = frozenset({"updates.deploy", "updates.rollback"})


class ClaimConflictError(ValueError):
    """Another mission/holder holds an overlapping file or branch claim."""

    def __init__(self, message: str, conflicts: list[dict[str, Any]]):
        super().__init__(message)
        self.conflicts = conflicts


class ClaimAuthorityError(ValueError):
    """The caller may not release this claim (not its holder, no evidence, no discard)."""


SCHEMA_VERSION = 2
CLAIM_KINDS = frozenset({"path", "branch"})
# completed/failed: the holder ends its run; merged: integration gate with PR
# evidence; discarded: explicit owner discard of the candidate.
CLAIM_RELEASE_REASONS = frozenset({"completed", "failed", "merged", "discarded", "orphan_mission", "pr_closed"})
# Releases no holder or gate can make: the owner runs them, with a proof recorded on the claim.
OWNER_RELEASE_REASONS = frozenset({"orphan_mission", "pr_closed"})
# Failures the harness itself observes, each with its one classification. A worker
# checkpoint may cite only these, and its classification is looked up, never chosen:
# a worker that invents a code (event 253, "MergeGrantUnsupported") is refused.
FAILURE_CLASSIFICATION = {
    "ClaimsNotMeasured": "transient", "ClaimsRefused": "auto_correctable",
    "HeadNotPublished": "transient", "CheckoutFailed": "transient",
    "GateNotConfigured": "auto_correctable", "MergeFailed": "unknown",
    "DeployUncertainAfterRecover": "uncertain_effect", "DeployUncertainUnreconciled": "uncertain_effect",
    "RecoverFailed": "uncertain_effect", "MergedReleaseRecovered": "external_proof",
    "MergeNotObserved": "uncertain_effect", "WorktreeCleanupFailed": "auto_correctable",
    "PostMergeFailed": "auto_correctable", "ReportTimeout": "transient",
}
# Who appended an agent-mission event. An event without a writer predates this field
# or bypassed the ledger API; readers can tell the two from a recorded one.
CHECKPOINT_WRITERS = frozenset({"gate", "agent_run", "worker"})
MISSION_EVENT_TYPES = frozenset({
    "accepted", "claimed", "checkpoint", "review_requested", "review_completed",
    "repair_requested", "repair_completed", "delivery_requested", "delivery_completed",
    "waiting", "resumed", "completed", "blocked", "failed", "claim_released", "woken",
    "mission_created", "gate_started", "gate_passed", "gate_failed",
})
_HOLDER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@+-]{0,127}")
# What resumes a parked mission: a PR leaving OPEN, a claim's release, or a date.
RESUME_ON = re.compile(r"(pr|claim):[1-9][0-9]{0,9}|date:[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _claim_target(kind: str, target: str) -> str:
    """Normalize a claim target; a path claim covers everything below it."""
    if kind not in CLAIM_KINDS:
        raise ValueError(f"claim kind must be one of {sorted(CLAIM_KINDS)}")
    if not isinstance(target, str) or not target or len(target) > 512 or "\x00" in target or "\\" in target:
        raise ValueError("claim target must be a 1-512 character path or branch")
    if kind == "branch":
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", target) or len(target) > 128
                or ".." in target.split("/")):
            raise ValueError("claim branch is invalid")
        return target
    absolute = target.startswith("/")
    parts = [part for part in target.split("/") if part not in {"", "."}]
    if not parts or ".." in parts:
        raise ValueError("claim path must name at least one component and no '..'")
    return ("/" if absolute else "") + "/".join(parts)


def claim_targets_overlap(kind: str, left: str, right: str) -> bool:
    """Branches match exactly; a path overlaps itself, its parents and its children."""
    if kind == "branch":
        return left == right
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _derived_event_id(*parts: Any) -> str:
    return hashlib.sha256(":".join(str(part) for part in parts).encode()).hexdigest()[:32]


class Ledger:
    # Newest independent-review receipts kept in the canonical plan; older SHAs
    # fall out and must be reviewed again before they can be merged.
    MAX_INDEPENDENT_REVIEWS = 256

    def __init__(self, path: Path):
        if path.parent.is_symlink() or path.is_symlink():
            raise ValueError("update ledger path must not follow symlinks")
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = self._connect()
        try:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS update_jobs (
                    job_id TEXT PRIMARY KEY, project_root TEXT NOT NULL, head_sha TEXT,
                    state TEXT NOT NULL, receipt_json TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS update_transitions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                    from_state TEXT, to_state TEXT NOT NULL, reason TEXT NOT NULL,
                    at REAL NOT NULL, receipt_json TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES update_jobs(job_id)
                );
                CREATE TABLE IF NOT EXISTS update_effects (
                    job_id TEXT NOT NULL, effect_key TEXT NOT NULL, kind TEXT NOT NULL,
                    state TEXT NOT NULL, intent_json TEXT NOT NULL, result_json TEXT,
                    attempt INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL,
                    updated_at REAL NOT NULL, PRIMARY KEY(job_id,effect_key),
                    FOREIGN KEY(job_id) REFERENCES update_jobs(job_id)
                );
                CREATE TABLE IF NOT EXISTS update_project_plans (
                    project_root TEXT PRIMARY KEY, job_id TEXT NOT NULL UNIQUE,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES update_jobs(job_id)
                );
                CREATE TABLE IF NOT EXISTS update_mission_events (
                    mission_id INTEGER NOT NULL, event_id TEXT NOT NULL,
                    job_id TEXT, source_sha TEXT,
                    event_type TEXT NOT NULL, event_json TEXT NOT NULL,
                    event_sha256 TEXT NOT NULL, created_at REAL NOT NULL,
                    PRIMARY KEY(mission_id,event_id),
                    FOREIGN KEY(job_id) REFERENCES update_jobs(job_id)
                );
                CREATE INDEX IF NOT EXISTS update_mission_events_job
                    ON update_mission_events(job_id,created_at,event_id);
                CREATE TABLE IF NOT EXISTS update_grants (
                    grant_id TEXT PRIMARY KEY, project_root TEXT NOT NULL,
                    environment TEXT NOT NULL, grant_json TEXT NOT NULL,
                    grant_sha256 TEXT NOT NULL, issued_at REAL NOT NULL,
                    revoked_at REAL, revocation_json TEXT
                );
                CREATE INDEX IF NOT EXISTS update_grants_scope
                    ON update_grants(project_root,environment,revoked_at);
                CREATE TABLE IF NOT EXISTS update_claims (
                    claim_id INTEGER PRIMARY KEY AUTOINCREMENT, project_root TEXT NOT NULL,
                    kind TEXT NOT NULL, target TEXT NOT NULL,
                    mission_id INTEGER NOT NULL, holder TEXT NOT NULL,
                    acquired_at REAL NOT NULL, released_at REAL, release_reason TEXT,
                    released_by TEXT, release_json TEXT
                );
                CREATE TABLE IF NOT EXISTS update_missions (
                    mission_id INTEGER PRIMARY KEY, title TEXT NOT NULL, created_at REAL NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS update_claims_active
                    ON update_claims(project_root,kind,target) WHERE released_at IS NULL;
                CREATE INDEX IF NOT EXISTS update_claims_mission
                    ON update_claims(mission_id,released_at);
                CREATE TABLE IF NOT EXISTS update_claim_waiters (
                    mission_id INTEGER NOT NULL, project_root TEXT NOT NULL,
                    kind TEXT NOT NULL, target TEXT NOT NULL,
                    registered_at REAL NOT NULL, woken_at REAL, woken_by_claim INTEGER,
                    PRIMARY KEY(mission_id,project_root,kind,target)
                );
            """)
            self._migrate(db)
        finally:
            db.close()

    @staticmethod
    def _migrate(db: sqlite3.Connection) -> None:
        """Bring an older ledger to SCHEMA_VERSION without losing any row.

        Version 2 lets mission events exist without a canonical plan (agent
        missions that only hold claims). SQLite cannot drop NOT NULL in place,
        so the events table is rebuilt row-for-row inside one transaction.
        """
        if db.execute("PRAGMA user_version").fetchone()[0] >= SCHEMA_VERSION:
            return
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
                columns = {row["name"]: row["notnull"]
                           for row in db.execute("PRAGMA table_info(update_mission_events)")}
                if columns.get("job_id") or columns.get("source_sha"):
                    db.execute("""
                        CREATE TABLE update_mission_events_v2 (
                            mission_id INTEGER NOT NULL, event_id TEXT NOT NULL,
                            job_id TEXT, source_sha TEXT,
                            event_type TEXT NOT NULL, event_json TEXT NOT NULL,
                            event_sha256 TEXT NOT NULL, created_at REAL NOT NULL,
                            PRIMARY KEY(mission_id,event_id),
                            FOREIGN KEY(job_id) REFERENCES update_jobs(job_id)
                        )""")
                    db.execute("INSERT INTO update_mission_events_v2 SELECT * FROM update_mission_events")
                    db.execute("DROP TABLE update_mission_events")
                    db.execute("ALTER TABLE update_mission_events_v2 RENAME TO update_mission_events")
                    db.execute("CREATE INDEX IF NOT EXISTS update_mission_events_job "
                               "ON update_mission_events(job_id,created_at,event_id)")
                db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            db.commit()
        except BaseException:
            db.rollback()
            raise

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        db = self._connect()
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def stable_id(project_root: str, head_sha: str | None, plan: dict[str, Any]) -> str:
        payload = json.dumps([project_root, head_sha, plan], sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:24]

    def create(self, project_root: str, head_sha: str | None, receipt: dict[str, Any], state: str = "planned",
               *, max_daily_jobs: int | None = None, max_concurrent_jobs: int | None = None) -> str:
        if state not in STATES:
            raise ValueError(f"invalid state: {state}")
        job_id = self.stable_id(project_root, head_sha, receipt)
        now = time.time()
        encoded = json.dumps(receipt, sort_keys=True, ensure_ascii=False)
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT receipt_json FROM update_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                if max_concurrent_jobs is not None:
                    active_count = db.execute(
                        "SELECT count(*) AS n FROM update_jobs WHERE project_root=? AND state IN ('planned','running','uncertain')",
                        (project_root,),
                    ).fetchone()["n"]
                    if active_count >= max_concurrent_jobs:
                        db.rollback()
                        raise JobLimitError(f"concurrent update-job limit reached ({max_concurrent_jobs})")
                if max_daily_jobs is not None:
                    utc_day_start = now - (now % 86400)
                    daily_count = db.execute(
                        "SELECT count(*) AS n FROM update_jobs WHERE project_root=? AND created_at>=?",
                        (project_root, utc_day_start),
                    ).fetchone()["n"]
                    if daily_count >= max_daily_jobs:
                        db.rollback()
                        raise JobLimitError(f"daily update-job limit reached ({max_daily_jobs})")
                db.execute("INSERT INTO update_jobs VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                           (job_id, project_root, head_sha, state, encoded, now, now))
                db.execute("INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) VALUES (?,NULL,?,?,?,?)",
                           (job_id, state, "plan created", now, encoded))
            db.commit()
        return job_id

    def canonical_plan(self, project_root: str) -> dict[str, Any] | None:
        with self._session() as db:
            row = db.execute(
                "SELECT j.* FROM update_project_plans p JOIN update_jobs j ON j.job_id=p.job_id "
                "WHERE p.project_root=?", (project_root,),
            ).fetchone()
            return self._decode(row) if row else None

    def adopt_project_identity(self, legacy_root: str, project_id: str) -> int:
        """Migrate one checkout-local ledger identity without changing job IDs."""
        if not legacy_root or not project_id or legacy_root == project_id:
            return 0
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            old_count = db.execute(
                "SELECT count(*) AS n FROM update_jobs WHERE project_root=?", (legacy_root,),
            ).fetchone()["n"]
            if not old_count:
                db.commit()
                return 0
            collision = db.execute(
                "SELECT 1 FROM update_jobs WHERE project_root=? LIMIT 1", (project_id,),
            ).fetchone()
            pointer_collision = db.execute(
                "SELECT 1 FROM update_project_plans WHERE project_root=?", (project_id,),
            ).fetchone()
            if collision or pointer_collision:
                db.rollback()
                raise CanonicalPlanError("legacy project identity conflicts with an existing canonical ledger")
            db.execute("UPDATE update_jobs SET project_root=? WHERE project_root=?",
                       (project_id, legacy_root))
            db.execute("UPDATE update_project_plans SET project_root=? WHERE project_root=?",
                       (project_id, legacy_root))
            db.commit()
            return old_count

    def is_canonical_plan(self, project_root: str, job_id: str) -> bool:
        with self._session() as db:
            row = db.execute(
                "SELECT 1 FROM update_project_plans WHERE project_root=? AND job_id=?",
                (project_root, job_id),
            ).fetchone()
            return row is not None

    def claim_test_execution(self, job_id: str, *, adapter: str = "docker-uv") -> dict[str, Any]:
        """Atomically fence plan refreshes before isolated execution begins."""
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT project_root,head_sha,state,receipt_json,version FROM update_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(job_id)
            pointer = db.execute(
                "SELECT job_id FROM update_project_plans WHERE project_root=?", (row["project_root"],),
            ).fetchone()
            if pointer is not None and pointer["job_id"] != job_id:
                db.rollback()
                raise CanonicalPlanError("job is historical; only the canonical plan may execute")
            if row["state"] not in {"planned", "blocked"}:
                db.rollback()
                raise CanonicalPlanError("canonical plan is not available for a new test execution")
            receipt = json.loads(row["receipt_json"])
            execution = receipt.get("execution", {})
            if isinstance(execution, dict) and execution.get("status") in {"failed", "cancelled"}:
                db.rollback()
                raise CanonicalPlanError("refresh the canonical plan before retrying a failed test")
            plan = receipt.get("plan", {})
            if not isinstance(plan, dict) or plan.get("head_sha") != row["head_sha"]:
                db.rollback()
                raise CanonicalPlanError("canonical plan does not match its source HEAD")
            execution = dict(execution) if isinstance(execution, dict) else {}
            execution.update({"status": "preparing", "adapter": adapter, "source_sha": row["head_sha"]})
            receipt["execution"] = execution
            encoded = json.dumps(receipt, sort_keys=True, ensure_ascii=False)
            changed = db.execute(
                "UPDATE update_jobs SET state='running',receipt_json=?,version=version+1,updated_at=? "
                "WHERE job_id=? AND version=?",
                (encoded, now, job_id, row["version"]),
            ).rowcount
            if changed != 1:
                db.rollback()
                raise RuntimeError("concurrent test execution claim")
            db.execute(
                "INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) "
                "VALUES (?,?,?,?,?,?)",
                (job_id, row["state"], "running", "isolated test execution claimed", now, encoded),
            )
            db.commit()
        result = self.get(job_id)
        if result is None:
            raise RuntimeError("claimed canonical plan disappeared")
        return result

    def claim_code_gate(self, job_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
        """Fence plan refreshes while the exact-source canonical code gate runs."""
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT project_root,head_sha,state,receipt_json,version FROM update_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(job_id)
            pointer = db.execute(
                "SELECT job_id FROM update_project_plans WHERE project_root=?", (row["project_root"],),
            ).fetchone()
            if pointer is not None and pointer["job_id"] != job_id:
                db.rollback()
                raise CanonicalPlanError("job is historical; only the canonical plan may execute")
            if row["state"] not in {"planned", "blocked"}:
                db.rollback()
                raise CanonicalPlanError("canonical plan is not available for code validation")
            plan = receipt.get("plan")
            if not isinstance(plan, dict) or plan.get("head_sha") != row["head_sha"]:
                db.rollback()
                raise CanonicalPlanError("canonical code gate receipt does not match the source HEAD")
            encoded = json.dumps(receipt, sort_keys=True, ensure_ascii=False)
            changed = db.execute(
                "UPDATE update_jobs SET state='running',receipt_json=?,version=version+1,updated_at=? "
                "WHERE job_id=? AND version=?",
                (encoded, now, job_id, row["version"]),
            ).rowcount
            if changed != 1:
                db.rollback()
                raise RuntimeError("concurrent canonical code gate claim")
            db.execute(
                "INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) "
                "VALUES (?,?,?,?,?,?)",
                (job_id, row["state"], "running", "canonical code gate claimed", now, encoded),
            )
            db.commit()
        result = self.get(job_id)
        if result is None:
            raise RuntimeError("claimed canonical code gate plan disappeared")
        return result

    def finish_code_gate(self, job_id: str, receipt: dict[str, Any], new_state: str,
                         *, reason: str = "canonical plan gates recalculated after code validation",
                         expected_version: int | None = None) -> dict[str, Any]:
        """Persist the code-gate result and leave running state in one transaction."""
        if new_state not in {"planned", "blocked"}:
            raise ValueError("code-gate completion state must be planned or blocked")
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT project_root,head_sha,state,version FROM update_jobs WHERE job_id=?", (job_id,),
            ).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(job_id)
            pointer = db.execute(
                "SELECT job_id FROM update_project_plans WHERE project_root=?", (row["project_root"],),
            ).fetchone()
            if pointer is not None and pointer["job_id"] != job_id:
                db.rollback()
                raise CanonicalPlanError("job is historical; only the canonical plan may execute")
            if row["state"] != "running":
                db.rollback()
                raise CanonicalPlanError("canonical code gate has no active claim")
            if expected_version is not None and row["version"] != expected_version:
                # The caller built `receipt` from an older read; writing it
                # would drop whatever was appended since.
                db.rollback()
                raise RuntimeError("concurrent canonical code gate completion")
            plan = receipt.get("plan")
            if not isinstance(plan, dict) or plan.get("head_sha") != row["head_sha"]:
                db.rollback()
                raise CanonicalPlanError("canonical code gate result does not match the source HEAD")
            encoded = json.dumps(receipt, sort_keys=True, ensure_ascii=False)
            changed = db.execute(
                "UPDATE update_jobs SET state=?,receipt_json=?,version=version+1,updated_at=? "
                "WHERE job_id=? AND version=?",
                (new_state, encoded, now, job_id, row["version"]),
            ).rowcount
            if changed != 1:
                db.rollback()
                raise RuntimeError("concurrent canonical code gate completion")
            db.execute(
                "INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) "
                "VALUES (?,?,?,?,?,?)",
                (job_id, "running", new_state, reason, now, encoded),
            )
            db.commit()
        result = self.get(job_id)
        if result is None:
            raise RuntimeError("completed canonical code gate plan disappeared")
        return result

    def refresh_canonical_plan(self, project_root: str, head_sha: str | None,
                               receipt: dict[str, Any], state: str = "planned", *,
                               max_daily_jobs: int | None = None,
                               max_concurrent_jobs: int | None = None) -> str:
        """Create once, then refresh one project plan in place with an append-only revision."""
        if state not in {"planned", "blocked"}:
            raise ValueError("canonical plan state must be planned or blocked")
        encoded = json.dumps(receipt, sort_keys=True, ensure_ascii=False)
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            pointer = db.execute(
                "SELECT job_id FROM update_project_plans WHERE project_root=?", (project_root,),
            ).fetchone()
            job_id = pointer["job_id"] if pointer else None
            if job_id is None:
                # Adopt the newest legacy plan/job before applying creation quotas.
                legacy = db.execute(
                    "SELECT job_id FROM update_jobs WHERE project_root=? "
                    "ORDER BY created_at DESC,updated_at DESC LIMIT 1", (project_root,),
                ).fetchone()
                if legacy:
                    job_id = legacy["job_id"]
                    db.execute("INSERT INTO update_project_plans VALUES (?,?,?,?)",
                               (project_root, job_id, now, now))
                else:
                    if max_concurrent_jobs is not None and max_concurrent_jobs < 1:
                        db.rollback()
                        raise JobLimitError("concurrent update-job limit reached")
                    if max_daily_jobs is not None:
                        utc_day_start = now - (now % 86400)
                        count = db.execute(
                            "SELECT count(*) AS n FROM update_jobs WHERE project_root=? AND created_at>=?",
                            (project_root, utc_day_start),
                        ).fetchone()["n"]
                        if count >= max_daily_jobs:
                            db.rollback()
                            raise JobLimitError(f"daily update-job limit reached ({max_daily_jobs})")
                    job_id = self.stable_id(project_root, head_sha, receipt)
                    db.execute("INSERT INTO update_jobs VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                               (job_id, project_root, head_sha, state, encoded, now, now))
                    db.execute("INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) "
                               "VALUES (?,NULL,?,?,?,?)", (job_id, state, "canonical plan created", now, encoded))
                    db.execute("INSERT INTO update_project_plans VALUES (?,?,?,?)",
                               (project_root, job_id, now, now))
                    db.commit()
                    return job_id

            # A refresh may not race an executor or strand an ambiguous external effect.
            jobs = db.execute(
                "SELECT job_id,state,receipt_json FROM update_jobs WHERE project_root=?", (project_root,),
            ).fetchall()
            for row in jobs:
                data = json.loads(row["receipt_json"])
                execution = data.get("execution", {}) if isinstance(data, dict) else {}
                if (row["state"] in {"running", "uncertain"}
                        or (isinstance(execution, dict)
                            and (execution.get("status") == "running" or execution.get("current")))):
                    db.rollback()
                    raise CanonicalPlanError("an update job is active or uncertain; recover it before refreshing")
            unresolved = db.execute(
                "SELECT 1 FROM update_effects e JOIN update_jobs j ON j.job_id=e.job_id "
                "WHERE j.project_root=? AND e.state IN ('intent','dispatching','uncertain') LIMIT 1",
                (project_root,),
            ).fetchone()
            if unresolved:
                db.rollback()
                raise CanonicalPlanError("an external effect is unresolved; reconcile it before refreshing")

            row = db.execute(
                "SELECT state,head_sha,receipt_json,version FROM update_jobs WHERE job_id=? AND project_root=?",
                (job_id, project_root),
            ).fetchone()
            if row is None:
                db.rollback()
                raise CanonicalPlanError("canonical plan pointer is invalid")
            old_state = row["state"]
            previous = json.loads(row["receipt_json"])
            carried = {key: value for key, value in previous.items()
                       if key not in CORE_RECEIPT_SECTIONS and key not in receipt} \
                if isinstance(previous, dict) else {}
            if carried:
                encoded = json.dumps({**receipt, **carried}, sort_keys=True, ensure_ascii=False)
            if row["head_sha"] == head_sha and row["receipt_json"] == encoded and old_state == state:
                db.commit()
                return job_id
            old_head = row["head_sha"] or "unknown"
            changed = db.execute(
                "UPDATE update_jobs SET head_sha=?,state=?,receipt_json=?,version=version+1,updated_at=? "
                "WHERE job_id=? AND version=?",
                (head_sha, state, encoded, now, job_id, row["version"]),
            ).rowcount
            if changed != 1:
                db.rollback()
                raise RuntimeError("concurrent canonical plan refresh")
            reason = f"canonical plan refreshed: {old_head} -> {head_sha or 'unknown'}"
            db.execute("INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) "
                       "VALUES (?,?,?,?,?,?)", (job_id, old_state, state, reason, now, encoded))
            db.execute("UPDATE update_project_plans SET updated_at=? WHERE project_root=?",
                       (now, project_root))
            db.commit()
        return job_id

    def transition(self, job_id: str, new_state: str, reason: str, receipt: dict[str, Any] | None = None) -> None:
        if new_state not in STATES:
            raise ValueError(f"invalid state: {new_state}")
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,receipt_json,version FROM update_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            old_state = row["state"]
            if new_state not in TRANSITIONS[old_state]:
                raise ValueError(f"invalid transition: {old_state} -> {new_state}")
            data = receipt if receipt is not None else json.loads(row["receipt_json"])
            encoded = json.dumps(data, sort_keys=True, ensure_ascii=False)
            changed = db.execute("UPDATE update_jobs SET state=?,receipt_json=?,version=version+1,updated_at=? WHERE job_id=? AND version=?",
                                 (new_state, encoded, now, job_id, row["version"])).rowcount
            if changed != 1:
                raise RuntimeError("concurrent update-job transition")
            db.execute("INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) VALUES (?,?,?,?,?,?)",
                       (job_id, old_state, new_state, reason, now, encoded))
            db.commit()

    def record(self, job_id: str, event: str, receipt: dict[str, Any]) -> None:
        """Append execution evidence without changing the job's policy state."""
        if not event or len(event) > 200:
            raise ValueError("ledger event must contain 1-200 characters")
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,version FROM update_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            encoded = json.dumps(receipt, sort_keys=True, ensure_ascii=False)
            changed = db.execute(
                "UPDATE update_jobs SET receipt_json=?,version=version+1,updated_at=? WHERE job_id=? AND version=?",
                (encoded, now, job_id, row["version"]),
            ).rowcount
            if changed != 1:
                raise RuntimeError("concurrent update-job receipt write")
            db.execute(
                "INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) VALUES (?,?,?,?,?,?)",
                (job_id, row["state"], row["state"], event, now, encoded),
            )
            db.commit()

    def record_supervision(self, job_id: str, receipt: dict[str, Any]) -> bool:
        """Atomically append one bounded supervisor receipt to the canonical plan.

        Returns False for an identical replay. A request ID can never be reused
        for different evidence, and the receipt must refer to this job's SHA.
        """
        if not isinstance(receipt, dict):
            raise ValueError("supervision receipt must be an object")
        allowed = {
            "request_id", "source_sha", "stage", "classification", "attempt",
            "diagnostic", "review", "repair", "next_step", "at",
        }
        if set(receipt) - allowed:
            raise ValueError("supervision receipt contains unknown fields")
        request_id = receipt.get("request_id")
        if not isinstance(request_id, str) or not re.fullmatch(r"[a-f0-9]{32}", request_id):
            raise ValueError("supervision request_id must be 32 lowercase hex characters")
        if receipt.get("stage") not in {"plan", "review", "repair", "validate", "merge", "deploy", "probe", "post_deploy", "recovery"}:
            raise ValueError("invalid supervision stage")
        if receipt.get("classification") not in {"auto_correctable", "transient", "external_proof", "uncertain_effect", "unknown"}:
            raise ValueError("invalid supervision classification")
        if type(receipt.get("attempt")) is not int or receipt["attempt"] < 1:
            raise ValueError("supervision attempt must be a positive integer")
        if receipt.get("next_step") not in {"diagnose", "review", "repair", "retry", "reconcile", "await_external", "complete"}:
            raise ValueError("invalid supervision next_step")
        diagnostic = receipt.get("diagnostic")
        if diagnostic is not None:
            if (not isinstance(diagnostic, dict) or set(diagnostic) - {"gate", "exit_code", "output_sha256", "failure_id"}
                    or not isinstance(diagnostic.get("gate"), str)
                    or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", diagnostic["gate"])):
                raise ValueError("diagnostic must contain only a stable gate ID, exit code and output digest")
            if "exit_code" in diagnostic and type(diagnostic["exit_code"]) is not int:
                raise ValueError("diagnostic exit_code must be an integer")
            if "output_sha256" in diagnostic and (not isinstance(diagnostic["output_sha256"], str)
                    or not re.fullmatch(r"[a-f0-9]{64}", diagnostic["output_sha256"])):
                raise ValueError("diagnostic output_sha256 must be a SHA-256 digest")
            if "failure_id" in diagnostic and (not isinstance(diagnostic["failure_id"], str)
                    or not re.fullmatch(r"[a-f0-9]{64}", diagnostic["failure_id"])):
                raise ValueError("diagnostic failure_id must be a SHA-256 digest")
        review = receipt.get("review")
        if review is not None and (not isinstance(review, dict)
                or set(review) - {"status", "review_id", "verdict", "report_sha256", "findings_count",
                                  "guard_review", "candidate_sha"}
                or review.get("status") not in {"pending", "completed", "failed"}
                or ("review_id" in review and (not isinstance(review["review_id"], str)
                    or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", review["review_id"])) )
                or ("verdict" in review and review["verdict"] not in {"passed", "findings", "blocked"})
                or ("report_sha256" in review and (not isinstance(review["report_sha256"], str)
                    or not re.fullmatch(r"[a-f0-9]{64}", review["report_sha256"])))
                or ("findings_count" in review and (type(review["findings_count"]) is not int
                    or not 0 <= review["findings_count"] <= 20))
                or ("guard_review" in review and type(review["guard_review"]) is not bool)):
            raise ValueError("review must contain only a status and stable review ID")
        if review is not None and "candidate_sha" in review and (
                not isinstance(review["candidate_sha"], str)
                or not re.fullmatch(r"[a-f0-9]{40}", review["candidate_sha"])):
            raise ValueError("review candidate_sha must be a full lowercase commit SHA")
        repair = receipt.get("repair")
        if repair is not None and (not isinstance(repair, dict)
                or set(repair) - {"status", "change_sha", "patch_sha256"}
                or repair.get("status") not in {"pending", "applied", "rejected", "not_needed"}
                or ("change_sha" in repair and (not isinstance(repair["change_sha"], str)
                    or not re.fullmatch(r"[a-f0-9]{40,64}", repair["change_sha"])) )
                or ("patch_sha256" in repair and (not isinstance(repair["patch_sha256"], str)
                    or not re.fullmatch(r"[a-f0-9]{64}", repair["patch_sha256"])) )):
            raise ValueError("repair must contain only a status and change SHA")
        if "at" in receipt and (type(receipt["at"]) not in {int, float}):
            raise ValueError("supervision at must be a numeric timestamp")
        encoded_item = self._effect_json(receipt, "supervision receipt")
        item = json.loads(encoded_item)
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,head_sha,receipt_json,version FROM update_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(job_id)
            if not row["head_sha"] or item.get("source_sha") != row["head_sha"]:
                db.rollback()
                raise CanonicalPlanError("supervision receipt SHA does not match its canonical job")
            plan = json.loads(row["receipt_json"])
            if not isinstance(plan.get("plan"), dict) or plan["plan"].get("head_sha") != row["head_sha"]:
                db.rollback()
                raise CanonicalPlanError("canonical plan SHA is missing or inconsistent")
            supervision = plan.setdefault("supervision", {"attempts": []})
            if not isinstance(supervision, dict) or not isinstance(supervision.setdefault("attempts", []), list):
                db.rollback()
                raise CanonicalPlanError("canonical supervision receipt is malformed")
            candidate_sha = item.get("review", {}).get("candidate_sha") if isinstance(item.get("review"), dict) else None
            if candidate_sha is not None and not any(
                    isinstance(entry, dict)
                    and entry.get("source_sha") == row["head_sha"]
                    and isinstance(entry.get("repair"), dict)
                    and entry["repair"].get("change_sha") == candidate_sha
                    and entry["repair"].get("status") == "pending"
                    for entry in supervision["attempts"]):
                db.rollback()
                raise CanonicalPlanError("candidate review does not bind to a pending repair receipt")
            existing = next((entry for entry in supervision["attempts"]
                             if isinstance(entry, dict) and entry.get("request_id") == request_id), None)
            if existing is not None:
                if existing != item:
                    db.rollback()
                    raise EffectConflictError("supervision request_id reused for different evidence")
                db.commit()
                return False
            supervision["attempts"].append(item)
            encoded_plan = json.dumps(plan, sort_keys=True, ensure_ascii=False, allow_nan=False)
            changed = db.execute(
                "UPDATE update_jobs SET receipt_json=?,version=version+1,updated_at=? WHERE job_id=? AND version=?",
                (encoded_plan, now, job_id, row["version"]),
            ).rowcount
            if changed != 1:
                db.rollback()
                raise RuntimeError("concurrent supervision receipt write")
            db.execute(
                "INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) VALUES (?,?,?,?,?,?)",
                (job_id, row["state"], row["state"], "supervisor receipt appended", now, encoded_item),
            )
            db.commit()
            return True

    @staticmethod
    def _review_identity(value: Any, label: str) -> dict[str, str]:
        if (not isinstance(value, dict) or set(value) != {"provider", "model"}
                or not isinstance(value.get("provider"), str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}", value["provider"])
                or not isinstance(value.get("model"), str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,119}", value["model"])):
            raise ValueError(f"independent review {label} must contain only provider and model")
        return value

    @classmethod
    def _validate_independent_review(cls, receipt: Any) -> dict[str, Any]:
        if not isinstance(receipt, dict):
            raise ValueError("independent review receipt must be an object")
        required = {"request_id", "candidate_sha", "base_sha", "diff_sha256", "status",
                    "findings_count", "findings_sha256", "reviewer", "author"}
        if not required <= set(receipt) or set(receipt) - required - {"review_id", "at"}:
            raise ValueError("independent review receipt fields are not the closed schema")
        for key, pattern in (("request_id", r"[0-9a-f]{32}"), ("candidate_sha", r"[0-9a-f]{40}"),
                             ("base_sha", r"[0-9a-f]{40}"), ("diff_sha256", r"[0-9a-f]{64}"),
                             ("findings_sha256", r"[0-9a-f]{64}")):
            if not isinstance(receipt[key], str) or not re.fullmatch(pattern, receipt[key]):
                raise ValueError(f"independent review {key} is invalid")
        if receipt["status"] not in {"passed", "findings", "blocked"}:
            raise ValueError("independent review status is invalid")
        count = receipt["findings_count"]
        if type(count) is not int or not 0 <= count <= 20:
            raise ValueError("independent review findings_count is invalid")
        if (receipt["status"] == "passed") != (count == 0) and receipt["status"] != "blocked":
            raise ValueError("independent review status disagrees with its findings")
        cls._review_identity(receipt["reviewer"], "reviewer")
        cls._review_identity(receipt["author"], "author")
        if "review_id" in receipt and (not isinstance(receipt["review_id"], str)
                                       or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", receipt["review_id"])):
            raise ValueError("independent review review_id is invalid")
        if "at" in receipt and type(receipt["at"]) not in {int, float}:
            raise ValueError("independent review at must be a numeric timestamp")
        return receipt

    def record_independent_review(self, job_id: str, receipt: dict[str, Any]) -> bool:
        """Append one LLM review receipt for an exact candidate SHA to the canonical plan.

        The receipt carries only digests and identities: the candidate and base
        SHAs, the SHA-256 of the reviewed diff and of the findings, and the
        provider/model of reviewer and author. Returns False for an identical
        replay; a request ID can never be reused for different evidence.
        """
        item = json.loads(self._effect_json(self._validate_independent_review(receipt),
                                            "independent review receipt"))
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT project_root,state,receipt_json,version FROM update_jobs WHERE job_id=?", (job_id,),
            ).fetchone()
            if row is None:
                db.rollback()
                raise CanonicalPlanError("independent review canonical plan does not exist")
            pointer = db.execute(
                "SELECT job_id FROM update_project_plans WHERE project_root=?", (row["project_root"],),
            ).fetchone()
            if pointer is None or pointer["job_id"] != job_id:
                db.rollback()
                raise CanonicalPlanError("independent review cannot attach to a historical plan")
            plan = json.loads(row["receipt_json"])
            reviews = plan.setdefault("independent_reviews", []) if isinstance(plan, dict) else None
            if not isinstance(reviews, list):
                db.rollback()
                raise CanonicalPlanError("canonical independent review history is malformed")
            existing = next((entry for entry in reviews if isinstance(entry, dict)
                             and entry.get("request_id") == item["request_id"]), None)
            if existing is not None:
                db.rollback()
                if existing != item:
                    raise EffectConflictError("independent review request_id reused for different evidence")
                return False
            reviews.append(item)
            del reviews[:-self.MAX_INDEPENDENT_REVIEWS]
            encoded_plan = json.dumps(plan, sort_keys=True, ensure_ascii=False, allow_nan=False)
            changed = db.execute(
                "UPDATE update_jobs SET receipt_json=?,version=version+1,updated_at=? WHERE job_id=? AND version=?",
                (encoded_plan, now, job_id, row["version"]),
            ).rowcount
            if changed != 1:
                db.rollback()
                raise RuntimeError("concurrent independent review write")
            db.execute(
                "INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) VALUES (?,?,?,?,?,?)",
                (job_id, row["state"], row["state"],
                 f"independent review recorded {item['candidate_sha'][:12]} {item['status']}",
                 now, json.dumps(item, sort_keys=True, ensure_ascii=False)),
            )
            db.commit()
            return True

    def independent_review_verdict(self, project_root: str, candidate_sha: str, *,
                                   diff_sha256: str | None = None) -> dict[str, Any]:
        """Decide whether the exact candidate SHA has a passing, independent review.

        Only the newest receipt for that SHA counts, so a later finding supersedes
        an earlier pass. A different SHA never inherits a receipt.
        """
        def refuse(reason: str, receipt: dict[str, Any] | None = None) -> dict[str, Any]:
            return {"allowed": False, "candidate_sha": candidate_sha, "reason": reason, "receipt": receipt}

        if not isinstance(candidate_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", candidate_sha):
            return refuse("candidate SHA must be a full lowercase commit SHA")
        plan = self.canonical_plan(project_root)
        reviews = plan["receipt"].get("independent_reviews") if plan else None
        matching = [entry for entry in reviews if isinstance(entry, dict)
                    and entry.get("candidate_sha") == candidate_sha] if isinstance(reviews, list) else []
        if not matching:
            return refuse("no independent review receipt for this exact SHA")
        latest = matching[-1]
        try:
            self._validate_independent_review(latest)
        except ValueError as exc:
            return refuse(f"independent review receipt is malformed: {exc}", latest)
        if latest["status"] != "passed":
            return refuse(f"latest independent review is {latest['status']}", latest)
        reviewer = {key: value.lower() for key, value in latest["reviewer"].items()}
        author = {key: value.lower() for key, value in latest["author"].items()}
        if reviewer == author:
            return refuse("reviewer provider/model is the same as the author", latest)
        if diff_sha256 is not None and latest["diff_sha256"] != diff_sha256:
            return refuse("reviewed diff digest does not match the candidate diff", latest)
        return {"allowed": True, "candidate_sha": candidate_sha, "reason": None, "receipt": latest}

    def record_mission_event(
        self, *, job_id: str | None, mission_id: int, event_id: str, source_sha: str | None,
        event_type: str, checkpoint: dict[str, Any],
    ) -> bool:
        """Append one bounded owner mission checkpoint to the canonical mission journal.

        The Postgres queue may schedule/resume a worker, but this append-only
        journal is the authoritative cross-executor mission timeline. The
        checkpoint contains only typed operational facts, never prompt text,
        credentials, or arbitrary model output. With ``job_id`` and
        ``source_sha`` the event binds to that canonical plan and SHA; with
        neither it is an agent-mission event (claims, run outcome) that no
        plan gate reads.
        """
        event = self._mission_event(job_id=job_id, mission_id=mission_id, event_id=event_id,
                                    source_sha=source_sha, event_type=event_type, checkpoint=checkpoint)
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                appended = self._append_mission_event(db, event, time.time())
            except BaseException:
                db.rollback()
                raise
            db.commit()
        return appended

    @staticmethod
    def _mission_event(*, job_id: str | None, mission_id: int, event_id: str, source_sha: str | None,
                       event_type: str, checkpoint: dict[str, Any]) -> dict[str, Any]:
        """Validate one mission event; the result is what the journal stores."""
        if (job_id is None) != (source_sha is None):
            raise ValueError("mission event binds both a canonical job and its SHA, or neither")
        if job_id is not None and (not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{24}", job_id)):
            raise ValueError("mission event requires a canonical update job ID")
        if type(mission_id) is not int or mission_id < 1:
            raise ValueError("mission ID must be a positive integer")
        if not isinstance(event_id, str) or not re.fullmatch(r"[0-9a-f]{32}", event_id):
            raise ValueError("mission event ID must be 32 lowercase hex characters")
        if source_sha is not None and (not isinstance(source_sha, str)
                                       or not re.fullmatch(r"[0-9a-f]{40}", source_sha)):
            raise ValueError("mission event source SHA must be a full commit SHA")
        if not isinstance(event_type, str) or event_type not in MISSION_EVENT_TYPES:
            raise ValueError("unsupported mission event type")
        if not isinstance(checkpoint, dict) or not checkpoint or set(checkpoint) - {
            "stage", "attempt", "next_step", "branch", "worktree", "pr_number",
            "head_sha", "request_id", "output_sha256", "classification", "files",
            "error_type", "wait_seconds", "status", "claim_ids", "release_reason", "title",
            "woken_by", "exit_code", "holder", "session_id", "quota_selection", "link", "actor",
            "writer", "reason", "resume_on",
        }:
            raise ValueError("mission checkpoint contains unsupported fields")
        if "reason" in checkpoint and (not isinstance(checkpoint["reason"], str)
                                       or not 1 <= len(checkpoint["reason"].strip()) <= 300
                                       or not checkpoint["reason"].isprintable()):
            raise ValueError("mission checkpoint reason is invalid")
        if "resume_on" in checkpoint and not _valid_resume_on(checkpoint["resume_on"]):
            raise ValueError("mission checkpoint resume_on is invalid")
        if "link" in checkpoint and checkpoint["link"] not in {"owner_statement"}:
            raise ValueError("mission checkpoint link is invalid")
        if "actor" in checkpoint and (not isinstance(checkpoint["actor"], str)
                                      or not _HOLDER.fullmatch(checkpoint["actor"])):
            raise ValueError("mission checkpoint actor is invalid")
        if "writer" in checkpoint and checkpoint["writer"] not in CHECKPOINT_WRITERS:
            raise ValueError("mission checkpoint writer is invalid")
        if checkpoint.get("writer") == "worker":
            if job_id is not None or "actor" not in checkpoint:
                raise ValueError("a worker checkpoint is an agent-mission event with its actor")
            error_type = checkpoint.get("error_type")
            if error_type is not None and error_type not in FAILURE_CLASSIFICATION:
                raise ValueError(f"error type {error_type!r} is not one the harness produces")
            if checkpoint.get("classification") != (FAILURE_CLASSIFICATION.get(error_type) if error_type else None):
                raise ValueError("a worker checkpoint's classification comes from its error type")
        stage = checkpoint.get("stage")
        if not isinstance(stage, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", stage):
            raise ValueError("mission checkpoint stage is invalid")
        if "attempt" in checkpoint and (type(checkpoint["attempt"]) is not int or not 1 <= checkpoint["attempt"] <= 100):
            raise ValueError("mission checkpoint attempt is invalid")
        if "next_step" in checkpoint and (not isinstance(checkpoint["next_step"], str)
                                           or checkpoint["next_step"] not in {
            "diagnose", "review", "repair", "validate", "merge", "deploy", "probe",
            "wait", "retry", "reconcile", "complete",
        }):
            raise ValueError("mission checkpoint next step is invalid")
        if "branch" in checkpoint and (
            not isinstance(checkpoint["branch"], str)
            or len(checkpoint["branch"]) > 128
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", checkpoint["branch"])
            or ".." in checkpoint["branch"].split("/")
        ):
            raise ValueError("mission checkpoint branch is invalid")
        if "worktree" in checkpoint and (
            not isinstance(checkpoint["worktree"], str) or not checkpoint["worktree"].startswith("/")
            or len(checkpoint["worktree"]) > 512 or "\x00" in checkpoint["worktree"]
        ):
            raise ValueError("mission checkpoint worktree is invalid")
        if "pr_number" in checkpoint and (type(checkpoint["pr_number"]) is not int or checkpoint["pr_number"] < 1):
            raise ValueError("mission checkpoint PR number is invalid")
        for key, pattern in (("head_sha", r"[0-9a-f]{40}"),
                             ("request_id", r"[0-9a-f]{32}"),
                             ("output_sha256", r"[0-9a-f]{64}")):
            if key in checkpoint and (not isinstance(checkpoint[key], str)
                                       or not re.fullmatch(pattern, checkpoint[key])):
                raise ValueError(f"mission checkpoint {key} is invalid")
        if "classification" in checkpoint and (
            not isinstance(checkpoint["classification"], str) or checkpoint["classification"] not in {
            "auto_correctable", "transient", "external_proof", "uncertain_effect", "unknown",
        }):
            raise ValueError("mission checkpoint classification is invalid")
        if "files" in checkpoint and (
            not isinstance(checkpoint["files"], list) or len(checkpoint["files"]) > 20
            or any(not isinstance(path, str) or not path or len(path) > 240
                   or path.startswith("/") or ".." in Path(path).parts or "\\" in path
                   for path in checkpoint["files"])
        ):
            raise ValueError("mission checkpoint file list is invalid")
        if "error_type" in checkpoint and (
            not isinstance(checkpoint["error_type"], str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]{0,79}", checkpoint["error_type"])
        ):
            raise ValueError("mission checkpoint error type is invalid")
        if "wait_seconds" in checkpoint and (
            type(checkpoint["wait_seconds"]) is not int or not 0 <= checkpoint["wait_seconds"] <= 86400
        ):
            raise ValueError("mission checkpoint wait is invalid")
        if "status" in checkpoint and (not isinstance(checkpoint["status"], str) or checkpoint["status"] not in {
            "pending", "running", "waiting", "completed", "blocked", "failed",
        }):
            raise ValueError("mission checkpoint status is invalid")
        if "claim_ids" in checkpoint and (
            not isinstance(checkpoint["claim_ids"], list) or not 1 <= len(checkpoint["claim_ids"]) <= 50
            or any(type(item) is not int or item < 1 for item in checkpoint["claim_ids"])
        ):
            raise ValueError("mission checkpoint claim IDs are invalid")
        if "release_reason" in checkpoint and checkpoint["release_reason"] not in CLAIM_RELEASE_REASONS:
            raise ValueError("mission checkpoint release reason is invalid")
        if "woken_by" in checkpoint and (type(checkpoint["woken_by"]) is not int or checkpoint["woken_by"] < 1):
            raise ValueError("mission checkpoint woken_by is invalid")
        if "exit_code" in checkpoint and (type(checkpoint["exit_code"]) is not int
                                          or not -255 <= checkpoint["exit_code"] <= 255):
            raise ValueError("mission checkpoint exit code is invalid")
        if "holder" in checkpoint and (not isinstance(checkpoint["holder"], str)
                                       or not _HOLDER.fullmatch(checkpoint["holder"])):
            raise ValueError("mission checkpoint holder is invalid")
        if "session_id" in checkpoint and (not isinstance(checkpoint["session_id"], str)
                                           or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", checkpoint["session_id"])):
            raise ValueError("mission checkpoint session ID is invalid")
        if "quota_selection" in checkpoint:
            selection = checkpoint["quota_selection"]
            if (not isinstance(selection, dict) or set(selection) != {"executor", "reason", "weights", "selection_key"}
                    or (selection["executor"] is not None
                        and (not isinstance(selection["executor"], str)
                             or selection["executor"] not in {"codex", "claude"}))
                    or not isinstance(selection["reason"], str)
                    or selection["reason"] not in {"primary_unknown_attempt", "proportional_capacity", "all_unavailable"}
                    or not isinstance(selection["weights"], dict)
                    or not isinstance(selection["selection_key"], str)
                    or not 1 <= len(selection["selection_key"]) <= 160):
                raise ValueError("mission quota selection is invalid")
            weights = selection["weights"]
            if (any(name not in {"codex", "claude"} or type(weight) not in {int, float}
                    or not math.isfinite(weight) or weight <= 0 or weight > 1
                    for name, weight in weights.items())
                    or (selection["reason"] == "proportional_capacity"
                        and (not weights or selection["executor"] is None))
                    or (selection["reason"] == "all_unavailable"
                        and (weights or selection["executor"] is not None))
                    or (selection["reason"] == "primary_unknown_attempt"
                        and (weights or selection["executor"] is None))
                    or (weights and not math.isclose(math.fsum(weights.values()), 1.0, rel_tol=1e-12))):
                raise ValueError("mission quota selection weights are invalid")
        encoded = json.dumps(checkpoint, sort_keys=True, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > 8192:
            raise ValueError("mission checkpoint exceeds 8 KiB")
        return {
            "mission_id": mission_id, "event_id": event_id, "job_id": job_id,
            "source_sha": source_sha, "event_type": event_type, "checkpoint": checkpoint,
        }

    @staticmethod
    def _append_mission_event(db: sqlite3.Connection, event: dict[str, Any], now: float) -> bool:
        """Insert a validated event inside the caller's write transaction.

        Returns False for an exact replay; a reused event ID with different
        content is a conflict.
        """
        mission_id, event_id = event["mission_id"], event["event_id"]
        job_id, source_sha, event_type = event["job_id"], event["source_sha"], event["event_type"]
        event_json = json.dumps(event, sort_keys=True, ensure_ascii=False, allow_nan=False)
        event_sha256 = hashlib.sha256(event_json.encode("utf-8")).hexdigest()
        prior = db.execute(
            "SELECT event_sha256 FROM update_mission_events WHERE mission_id=? AND event_id=?",
            (mission_id, event_id),
        ).fetchone()
        if prior is not None:
            if prior["event_sha256"] != event_sha256:
                raise EffectConflictError("mission event ID reused for different evidence")
            # The append may have committed before its mailbox response was
            # written. Acknowledge that exact durable fact even if the plan
            # advanced meanwhile; only a new append needs current-SHA proof.
            return False
        if job_id is None:
            db.execute(
                "INSERT INTO update_mission_events VALUES (?,?,?,?,?,?,?,?)",
                (mission_id, event_id, None, None, event_type, event_json, event_sha256, now),
            )
            return True
        row = db.execute(
            "SELECT project_root,head_sha,receipt_json,state,version FROM update_jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise CanonicalPlanError("mission event canonical plan does not exist")
        receipt = json.loads(row["receipt_json"])
        plan = receipt.get("plan") if isinstance(receipt, dict) else None
        if (row["head_sha"] != source_sha or not isinstance(plan, dict)
                or plan.get("head_sha") != source_sha):
            raise CanonicalPlanError("mission event SHA does not match its canonical plan")
        pointer = db.execute(
            "SELECT job_id FROM update_project_plans WHERE project_root=?",
            (row["project_root"],),
        ).fetchone()
        if pointer is not None and pointer["job_id"] != job_id:
            raise CanonicalPlanError("mission event cannot attach to a historical plan")
        db.execute(
            "INSERT INTO update_mission_events VALUES (?,?,?,?,?,?,?,?)",
            (mission_id, event_id, job_id, source_sha, event_type, event_json, event_sha256, now),
        )
        changed = db.execute(
            "UPDATE update_jobs SET version=version+1,updated_at=? WHERE job_id=? AND version=?",
            (now, job_id, row["version"]),
        ).rowcount
        if changed != 1:
            raise RuntimeError("concurrent canonical mission event write")
        db.execute(
            "INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) "
            "VALUES (?,?,?,?,?,?)",
            (job_id, row["state"], row["state"], f"mission {event_type} {event_id[:12]}",
             now, event_json),
        )
        return True

    @staticmethod
    def _claim_owner(project_root: str, mission_id: int, holder: str) -> None:
        if not isinstance(project_root, str) or not project_root or len(project_root) > 512 or "\x00" in project_root:
            raise ValueError("claim project must be a 1-512 character identity")
        if type(mission_id) is not int or mission_id < 1:
            raise ValueError("mission ID must be a positive integer")
        if not isinstance(holder, str) or not _HOLDER.fullmatch(holder):
            raise ValueError("claim holder is invalid")

    @staticmethod
    def _decode_claim(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        evidence = result.pop("release_json")
        result["release_evidence"] = json.loads(evidence) if evidence else None
        return result

    def acquire_claims(self, *, project_root: str, mission_id: int, holder: str,
                       targets: list[tuple[str, str]], wait: bool = False) -> dict[str, Any]:
        """Take every (kind, target) for one mission/holder, or none of them.

        A target conflicts with an active claim of another mission or holder
        on the same project when the branches are equal or one path contains
        the other. The same owner re-acquiring is an idempotent replay. On
        conflict nothing is taken; with ``wait`` the mission is registered as
        a waiter so the release that frees the target records ``woken`` for it.
        """
        self._claim_owner(project_root, mission_id, holder)
        if not isinstance(targets, list) or not 1 <= len(targets) <= 50:
            raise ValueError("claim requires 1-50 targets")
        wanted: list[tuple[str, str]] = []
        for kind, target in targets:
            item = (kind, _claim_target(kind, target))
            if item not in wanted:
                wanted.append(item)
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                active = db.execute(
                    "SELECT * FROM update_claims WHERE project_root=? AND released_at IS NULL", (project_root,),
                ).fetchall()
                conflicts: list[dict[str, Any]] = []
                owned: dict[tuple[str, str], int] = {}
                for kind, target in wanted:
                    for row in active:
                        if row["kind"] != kind or not claim_targets_overlap(kind, target, row["target"]):
                            continue
                        if (row["mission_id"], row["holder"]) != (mission_id, holder):
                            conflicts.append({"kind": kind, "target": target, "claim": self._decode_claim(row)})
                        elif row["target"] == target:
                            owned[(kind, target)] = row["claim_id"]
                if conflicts:
                    if not wait:
                        db.rollback()
                        raise ClaimConflictError("claim held by another mission or holder", conflicts)
                    blocked = sorted({(item["kind"], item["target"]) for item in conflicts})
                    for kind, target in blocked:
                        db.execute(
                            "INSERT INTO update_claim_waiters VALUES (?,?,?,?,?,NULL,NULL) "
                            "ON CONFLICT(mission_id,project_root,kind,target) DO UPDATE SET "
                            "registered_at=excluded.registered_at,woken_at=NULL,woken_by_claim=NULL",
                            (mission_id, project_root, kind, target, now),
                        )
                    self._append_mission_event(db, self._mission_event(
                        job_id=None, source_sha=None, mission_id=mission_id,
                        event_id=_derived_event_id("waiting", mission_id, project_root, blocked, now),
                        event_type="waiting",
                        checkpoint={"stage": "claim", "status": "waiting", "next_step": "wait",
                                    "holder": holder,
                                    "claim_ids": sorted({item["claim"]["claim_id"] for item in conflicts})},
                    ), now)
                    db.commit()
                    raise ClaimConflictError("claim held by another mission or holder; waiting", conflicts)
                acquired: list[int] = []
                for kind, target in wanted:
                    if (kind, target) in owned:
                        continue
                    acquired.append(db.execute(
                        "INSERT INTO update_claims(project_root,kind,target,mission_id,holder,acquired_at) "
                        "VALUES (?,?,?,?,?,?)", (project_root, kind, target, mission_id, holder, now),
                    ).lastrowid)
                    db.execute("DELETE FROM update_claim_waiters WHERE mission_id=? AND project_root=? "
                               "AND kind=? AND target=?", (mission_id, project_root, kind, target))
                if acquired:
                    self._append_mission_event(db, self._mission_event(
                        job_id=None, source_sha=None, mission_id=mission_id,
                        event_id=_derived_event_id("claimed", *acquired), event_type="claimed",
                        checkpoint={"stage": "claim", "status": "running", "holder": holder,
                                    "claim_ids": acquired},
                    ), now)
                ids = [*owned.values(), *acquired]
                rows = db.execute(
                    f"SELECT * FROM update_claims WHERE claim_id IN ({','.join('?' * len(ids))}) ORDER BY claim_id",
                    ids,
                ).fetchall()
                db.commit()
            except ClaimConflictError:
                raise
            except BaseException:
                db.rollback()
                raise
        return {"claims": [self._decode_claim(row) for row in rows], "replayed": not acquired}

    def release_claims(self, *, mission_id: int, reason: str, released_by: str,
                       project_root: str | None = None, holder: str | None = None,
                       targets: list[tuple[str, str]] | None = None,
                       pr_number: int | None = None, merge_sha: str | None = None,
                       owner_discard: bool = False, owner_release: bool = False,
                       proof: dict[str, Any] | None = None) -> dict[str, Any]:
        """Release a mission's active claims and wake the missions waiting on them.

        Who may release: the holder (``completed``/``failed``), the integration
        gate with PR evidence (``merged``), the owner's explicit discard
        (``discarded``), or an owner release with its recorded ``proof``:
        ``orphan_mission`` (the mission is not in this ledger, checked here) and
        ``pr_closed`` (the PR number and the head SHA it closed at). Only ledger
        rows change; worktrees and Git changes are never touched. Releasing
        already-released claims is a replay.
        """
        if reason not in CLAIM_RELEASE_REASONS:
            raise ValueError(f"release reason must be one of {sorted(CLAIM_RELEASE_REASONS)}")
        if type(mission_id) is not int or mission_id < 1:
            raise ValueError("mission ID must be a positive integer")
        if not isinstance(released_by, str) or not _HOLDER.fullmatch(released_by):
            raise ValueError("release actor is invalid")
        if (reason == "discarded") != owner_discard:
            raise ClaimAuthorityError("only an explicit owner discard releases with reason 'discarded'")
        if (reason in OWNER_RELEASE_REASONS) != owner_release:
            raise ClaimAuthorityError(f"only an explicit owner release uses {sorted(OWNER_RELEASE_REASONS)}")
        evidence: dict[str, Any] = {"released_by": released_by}
        if owner_release:
            if not isinstance(proof, dict):
                raise ClaimAuthorityError("an owner release records its proof")
            if reason == "pr_closed" and (type(proof.get("pr_number")) is not int
                                          or not re.fullmatch(r"[0-9a-f]{40}", str(proof.get("head_sha")))):
                raise ClaimAuthorityError("pr_closed release requires the PR number and head SHA it closed at")
            evidence["proof"] = proof
        if reason == "merged":
            if type(pr_number) is not int or pr_number < 1 or not isinstance(merge_sha, str) \
                    or not re.fullmatch(r"[0-9a-f]{40}", merge_sha):
                raise ClaimAuthorityError("merged release requires the PR number and its full merge SHA")
            evidence.update({"pr_number": pr_number, "merge_sha": merge_sha})
        elif reason in {"completed", "failed"} and (not isinstance(holder, str) or not _HOLDER.fullmatch(holder)):
            raise ClaimAuthorityError("holder release must name the holder")
        selected = None if targets is None else {(kind, _claim_target(kind, target)) for kind, target in targets}
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if reason == "orphan_mission" and db.execute(
                        "SELECT 1 FROM update_missions WHERE mission_id=?", (mission_id,)).fetchone():
                    raise ClaimAuthorityError(f"mission {mission_id} exists in this ledger; "
                                              "release its claims through the mission (discard, merge, holder)")
                query = "SELECT * FROM update_claims WHERE mission_id=? AND released_at IS NULL"
                params: list[Any] = [mission_id]
                if project_root is not None:
                    query += " AND project_root=?"
                    params.append(project_root)
                rows = [row for row in db.execute(query + " ORDER BY claim_id", params).fetchall()
                        if selected is None or (row["kind"], row["target"]) in selected]
                if reason in {"completed", "failed"}:
                    foreign = [row["claim_id"] for row in rows if row["holder"] != holder]
                    if foreign:
                        raise ClaimAuthorityError(f"claims {foreign} belong to another holder")
                if not rows:
                    db.commit()
                    return {"released": [], "woken": [], "replayed": True}
                encoded = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
                for row in rows:
                    db.execute(
                        "UPDATE update_claims SET released_at=?,release_reason=?,released_by=?,release_json=? "
                        "WHERE claim_id=? AND released_at IS NULL",
                        (now, reason, released_by, encoded, row["claim_id"]),
                    )
                ids = [row["claim_id"] for row in rows]
                checkpoint: dict[str, Any] = {"stage": "claim", "status": "completed", "claim_ids": ids,
                                              "release_reason": reason, "holder": rows[0]["holder"]}
                if pr_number is not None and reason == "merged":
                    checkpoint["pr_number"] = pr_number
                self._append_mission_event(db, self._mission_event(
                    job_id=None, source_sha=None, mission_id=mission_id,
                    event_id=_derived_event_id("claim_released", *ids), event_type="claim_released",
                    checkpoint=checkpoint,
                ), now)
                woken: list[int] = []
                for waiter in db.execute(
                        "SELECT * FROM update_claim_waiters WHERE woken_at IS NULL ORDER BY registered_at").fetchall():
                    if waiter["mission_id"] == mission_id:
                        continue
                    freed = next((row for row in rows if row["project_root"] == waiter["project_root"]
                                  and row["kind"] == waiter["kind"]
                                  and claim_targets_overlap(row["kind"], row["target"], waiter["target"])), None)
                    if freed is None:
                        continue
                    db.execute(
                        "UPDATE update_claim_waiters SET woken_at=?,woken_by_claim=? WHERE mission_id=? "
                        "AND project_root=? AND kind=? AND target=?",
                        (now, freed["claim_id"], waiter["mission_id"], waiter["project_root"],
                         waiter["kind"], waiter["target"]),
                    )
                    self._append_mission_event(db, self._mission_event(
                        job_id=None, source_sha=None, mission_id=waiter["mission_id"],
                        event_id=_derived_event_id("woken", waiter["mission_id"], freed["claim_id"]),
                        event_type="woken",
                        checkpoint={"stage": "claim", "status": "pending", "next_step": "retry",
                                    "claim_ids": [freed["claim_id"]], "woken_by": mission_id},
                    ), now)
                    if waiter["mission_id"] not in woken:
                        woken.append(waiter["mission_id"])
                released = db.execute(
                    f"SELECT * FROM update_claims WHERE claim_id IN ({','.join('?' * len(ids))}) ORDER BY claim_id",
                    ids,
                ).fetchall()
                db.commit()
            except BaseException:
                if db.in_transaction:
                    db.rollback()
                raise
        return {"released": [self._decode_claim(row) for row in released], "woken": woken, "replayed": False}

    def release_merged_branch(self, *, project_root: str, branch: str, pr_number: int, merge_sha: str,
                              released_by: str) -> dict[str, Any]:
        """Integration hook: a merged PR releases every claim of the mission holding its branch."""
        branch = _claim_target("branch", branch)
        active = self.claims(project_root=project_root)
        claimed = {int(c["mission_id"]) for c in active if c["kind"] == "branch" and c["target"] == branch}
        linked = claimed or {mission for mission in {int(c["mission_id"]) for c in active}
                             if branch in mission_branches(active, mission)}
        if len(linked) != 1:  # none, or a holder shared by several missions: never pick one
            return {"released": [], "woken": [], "replayed": not linked}
        return self.release_claims(mission_id=linked.pop(), project_root=project_root, reason="merged",
                                   released_by=released_by, pr_number=pr_number, merge_sha=merge_sha)

    def claims(self, *, project_root: str | None = None, mission_id: int | None = None,
               active_only: bool = True) -> list[dict[str, Any]]:
        query, params = "SELECT * FROM update_claims WHERE 1=1", []
        if project_root is not None:
            query += " AND project_root=?"
            params.append(project_root)
        if mission_id is not None:
            query += " AND mission_id=?"
            params.append(mission_id)
        if active_only:
            query += " AND released_at IS NULL"
        with self._session() as db:
            return [self._decode_claim(row) for row in db.execute(query + " ORDER BY claim_id", params)]

    def create_mission(self, title: str) -> int:
        """Allocate a monotonic mission ID and preserve its human supplied title."""
        title = title.strip()
        if not title or len(title) > 240:
            raise ValueError("mission title must contain 1 to 240 characters")
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT max(mission_id) FROM ("
                             "SELECT mission_id FROM update_missions UNION ALL "
                             "SELECT mission_id FROM update_mission_events UNION ALL "
                             "SELECT mission_id FROM update_claims)").fetchone()
            mission_id = int(row[0] or 0) + 1
            now = time.time()
            db.execute("INSERT INTO update_missions(mission_id,title,created_at) VALUES(?,?,?)",
                       (mission_id, title, now))
            event = self._mission_event(job_id=None, source_sha=None, mission_id=mission_id,
                                        event_id=_derived_event_id("mission-created", mission_id, title),
                                        event_type="mission_created",
                                        checkpoint={"stage": "mission", "title": title, "status": "pending"})
            self._append_mission_event(db, event, now)
            db.commit()
        return mission_id

    def has_mission(self, mission_id: int) -> bool:
        """Whether this ledger allocated ``mission_id`` (``create_mission``)."""
        with self._session() as db:
            return db.execute("SELECT 1 FROM update_missions WHERE mission_id=?",
                              (mission_id,)).fetchone() is not None

    def mission_events(self, mission_id: int) -> list[dict[str, Any]]:
        """Read one mission's canonical append-only event stream."""
        if type(mission_id) is not int or mission_id < 1:
            raise ValueError("mission ID must be a positive integer")
        with self._session() as db:
            rows = db.execute(
                "SELECT event_json,created_at FROM update_mission_events "
                "WHERE mission_id=? ORDER BY created_at,event_id", (mission_id,),
            ).fetchall()
        result = []
        for row in rows:
            event = json.loads(row["event_json"])
            event["created_at"] = row["created_at"]
            result.append(event)
        return result

    def record_grant(self, *, grant_id: str, project_root: str, environment: str,
                     principals: list[str], operations: list[str], basis: str,
                     issued_by: str, source_sha: str | None = None,
                     expires_at: float | None = None) -> dict[str, Any]:
        """Persist one immutable owner grant for production effects.

        The grant names who may act, on which project and environment, which
        effectful operations, and optionally one exact source SHA. Recording
        never widens an existing grant: reusing an ID for different content is
        a conflict, and revocation is a separate append.
        """
        if not isinstance(grant_id, str) or not re.fullmatch(r"[0-9a-f]{32}", grant_id):
            raise ValueError("grant ID must be 32 lowercase hex characters")
        if not isinstance(project_root, str) or not project_root or len(project_root) > 240:
            raise ValueError("grant project identity is invalid")
        if not isinstance(environment, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", environment):
            raise ValueError("grant environment is invalid")
        if (not isinstance(principals, list) or not 1 <= len(principals) <= 10
                or any(not isinstance(item, str)
                       or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:._-]{0,79}", item)
                       for item in principals)):
            raise ValueError("grant principals are invalid")
        if (not isinstance(operations, list) or not operations
                or any(item not in GRANTED_EFFECT_OPERATIONS for item in operations)):
            raise ValueError("grant operations must be granted production effects")
        if source_sha is not None and (not isinstance(source_sha, str)
                                       or not re.fullmatch(r"[0-9a-f]{40}", source_sha)):
            raise ValueError("grant source SHA must be a full commit SHA")
        if expires_at is not None and (not isinstance(expires_at, (int, float)) or expires_at <= 0):
            raise ValueError("grant expiry is invalid")
        for label, value in (("basis", basis), ("issuer", issued_by)):
            if not isinstance(value, str) or not value.strip() or len(value) > 240 or "\x00" in value:
                raise ValueError(f"grant {label} is invalid")
        grant = {
            "grant_id": grant_id, "project_root": project_root, "environment": environment,
            "principals": sorted(set(principals)), "operations": sorted(set(operations)),
            "source_sha": source_sha, "expires_at": expires_at,
            "basis": basis, "issued_by": issued_by,
        }
        encoded = self._effect_json(grant, "grant")
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT grant_sha256 FROM update_grants WHERE grant_id=?",
                               (grant_id,)).fetchone()
            if prior is not None:
                db.rollback()
                if prior["grant_sha256"] != digest:
                    raise EffectConflictError("grant ID reused for a different scope")
                return self.grant(grant_id) or {}
            db.execute("INSERT INTO update_grants VALUES (?,?,?,?,?,?,NULL,NULL)",
                       (grant_id, project_root, environment, encoded, digest, now))
            db.commit()
        return self.grant(grant_id) or {}

    def revoke_grant(self, grant_id: str, *, reason: str, revoked_by: str) -> dict[str, Any]:
        """Revoke a grant once; later effects naming it are denied."""
        for label, value in (("reason", reason), ("revoker", revoked_by)):
            if not isinstance(value, str) or not value.strip() or len(value) > 240 or "\x00" in value:
                raise ValueError(f"grant revocation {label} is invalid")
        encoded = json.dumps({"reason": reason, "revoked_by": revoked_by}, sort_keys=True,
                             ensure_ascii=False)
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE update_grants SET revoked_at=?,revocation_json=? "
                "WHERE grant_id=? AND revoked_at IS NULL",
                (time.time(), encoded, grant_id),
            ).rowcount
            if changed != 1 and db.execute("SELECT 1 FROM update_grants WHERE grant_id=?",
                                           (grant_id,)).fetchone() is None:
                db.rollback()
                raise KeyError(grant_id)
            db.commit()
        return self.grant(grant_id) or {}

    def grant(self, grant_id: str) -> dict[str, Any] | None:
        with self._session() as db:
            row = db.execute("SELECT * FROM update_grants WHERE grant_id=?", (grant_id,)).fetchone()
        return self._decode_grant(row) if row else None

    def grants(self, project_root: str) -> list[dict[str, Any]]:
        with self._session() as db:
            rows = db.execute("SELECT * FROM update_grants WHERE project_root=? ORDER BY issued_at,grant_id",
                              (project_root,)).fetchall()
        return [self._decode_grant(row) for row in rows]

    def authorize_effect(self, *, project_root: str, environment: str, operation: str,
                         actor_id: str, source_sha: str, grant_id: str | None = None,
                         now: float | None = None) -> dict[str, Any]:
        """Return the authority reference for one effect, or raise `GrantError`.

        A named grant must itself cover the request. Without a name, exactly
        the active grants covering the request are considered; ambiguity is a
        denial rather than a choice.
        """
        if operation not in GRANTED_EFFECT_OPERATIONS:
            raise GrantError(f"{operation} is not a granted production effect")
        moment = time.time() if now is None else now
        if grant_id is not None:
            candidate = self.grant(grant_id)
            if candidate is None:
                raise GrantError("named grant does not exist")
            candidates = [candidate]
        else:
            candidates = [item for item in self.grants(project_root)
                          if item["environment"] == environment]
            if not candidates:
                raise GrantError("no production-effect grant exists for this project and environment")

        def denial(item: dict[str, Any]) -> str | None:
            if item["project_root"] != project_root:
                return "grant does not cover this project"
            if item["environment"] != environment:
                return "grant does not cover this environment"
            if item["revoked_at"] is not None:
                return "grant was revoked"
            if item["expires_at"] is not None and item["expires_at"] <= moment:
                return "grant expired"
            if operation not in item["operations"]:
                return "grant does not cover this operation"
            if actor_id not in item["principals"]:
                return "grant does not cover this principal"
            if item["source_sha"] is not None and item["source_sha"] != source_sha:
                return "grant is bound to a different source SHA"
            return None

        covering = [item for item in candidates if denial(item) is None]
        if not covering:
            reasons = sorted({denial(item) or "" for item in candidates})
            raise GrantError("; ".join(reasons))
        if len(covering) > 1:
            raise GrantError("several active grants cover this effect; name one explicitly")
        item = covering[0]
        return {"grant_id": item["grant_id"], "grant_sha256": item["grant_sha256"],
                "actor_id": actor_id, "operation": operation, "project_root": project_root,
                "environment": environment, "source_sha": source_sha}

    @staticmethod
    def _decode_grant(row: sqlite3.Row) -> dict[str, Any]:
        grant = json.loads(row["grant_json"])
        grant["grant_sha256"] = row["grant_sha256"]
        grant["issued_at"] = row["issued_at"]
        grant["revoked_at"] = row["revoked_at"]
        grant["revocation"] = json.loads(row["revocation_json"]) if row["revocation_json"] else None
        return grant

    @staticmethod
    def _effect_json(value: dict[str, Any], label: str) -> str:
        """Serialize bounded, credential-free effect metadata for recovery."""
        forbidden = re.compile(r"token|secret|password|cookie|authorization|api[_-]?key", re.IGNORECASE)

        def check(item: Any) -> None:
            if isinstance(item, dict):
                for key, child in item.items():
                    if not isinstance(key, str) or forbidden.search(key):
                        raise ValueError(f"{label} must not contain credential fields")
                    check(child)
            elif isinstance(item, list):
                for child in item:
                    check(child)
            elif item is not None and not isinstance(item, (str, int, float, bool)):
                raise ValueError(f"{label} must contain JSON-compatible values")

        if not isinstance(value, dict):
            raise ValueError(f"{label} must be a JSON object")
        check(value)
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > 64 * 1024:
            raise ValueError(f"{label} exceeds 64 KiB")
        return encoded

    def prepare_effect(self, job_id: str, effect_key: str, kind: str,
                       intent: dict[str, Any]) -> dict[str, Any]:
        """Durably record intent before a remote effect; never authorize replay.

        Repeating the same call is an idempotent read of the original effect.
        Different payloads, or an unresolved intent, cannot be overwritten.
        """
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,160}", effect_key):
            raise ValueError("effect_key must be a stable, safe identifier")
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,63}", kind):
            raise ValueError("effect kind must be a stable capability identifier")
        encoded_intent = self._effect_json(intent, "effect intent")
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM update_jobs WHERE job_id=?", (job_id,)).fetchone() is None:
                db.rollback()
                raise KeyError(job_id)
            row = db.execute(
                "SELECT * FROM update_effects WHERE job_id=? AND effect_key=?", (job_id, effect_key)
            ).fetchone()
            if row is not None:
                if row["kind"] != kind or row["intent_json"] != encoded_intent:
                    db.rollback()
                    raise EffectConflictError("effect key already belongs to a different intent")
                result = self._decode_effect(row)
                db.commit()
                return result
            db.execute(
                "INSERT INTO update_effects(job_id,effect_key,kind,state,intent_json,created_at,updated_at) "
                "VALUES(?,?,?,'intent',?,?,?)",
                (job_id, effect_key, kind, encoded_intent, now, now),
            )
            receipt = {"effect_key": effect_key, "kind": kind, "state": "intent",
                       "intent": json.loads(encoded_intent)}
            db.execute(
                "INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) "
                "SELECT ?,state,state,?,?,? FROM update_jobs WHERE job_id=?",
                (job_id, f"effect intent persisted: {kind}", now,
                 json.dumps(receipt, sort_keys=True, ensure_ascii=False), job_id),
            )
            db.commit()
        return {"job_id": job_id, "effect_key": effect_key, "kind": kind, "state": "intent",
                "intent": json.loads(encoded_intent), "result": None, "attempt": 1}

    def mark_effect_uncertain(self, job_id: str, effect_key: str,
                              detail: dict[str, Any] | None = None) -> dict[str, Any]:
        """Record timeout/connection loss; callers must reconcile remotely first."""
        encoded_result = self._effect_json(detail or {}, "effect result")
        return self._update_effect(job_id, effect_key, expected="dispatching", state="uncertain",
                                   result_json=encoded_result, reason="effect outcome uncertain; reconcile before retry")

    def begin_effect(self, job_id: str, effect_key: str) -> dict[str, Any]:
        """Claim the one permitted dispatch after intent persistence.

        A repeated call never grants a second dispatch. A process that finds
        `dispatching` after recovery must reconcile instead of calling upstream.
        """
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM update_effects WHERE job_id=? AND effect_key=?",
                             (job_id, effect_key)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError((job_id, effect_key))
            if row["state"] != "intent":
                result = self._decode_effect(row)
                result["dispatch_started"] = False
                db.commit()
                return result
            db.execute("UPDATE update_effects SET state='dispatching',updated_at=? WHERE job_id=? AND effect_key=?",
                       (now, job_id, effect_key))
            receipt = {"effect_key": effect_key, "kind": row["kind"], "state": "dispatching",
                       "intent": json.loads(row["intent_json"])}
            db.execute(
                "INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) "
                "SELECT ?,state,state,?,?,? FROM update_jobs WHERE job_id=?",
                (job_id, "external effect dispatch claimed", now,
                 json.dumps(receipt, sort_keys=True, ensure_ascii=False), job_id),
            )
            updated = db.execute("SELECT * FROM update_effects WHERE job_id=? AND effect_key=?",
                                 (job_id, effect_key)).fetchone()
            db.commit()
        result = self._decode_effect(updated)
        result["dispatch_started"] = True
        return result

    def reconcile_effect(self, job_id: str, effect_key: str, *, outcome: str,
                         evidence: dict[str, Any]) -> dict[str, Any]:
        """Persist a caller-verified remote snapshot, never perform the retry.

        The ledger hashes the credential-free snapshot itself so the receipt
        cannot claim a digest unrelated to the recorded observation.
        """
        if outcome not in {"applied", "not_applied"}:
            raise ValueError("reconciled outcome must be applied or not_applied")
        source, observed_at, snapshot = evidence.get("source"), evidence.get("observed_at"), evidence.get("snapshot")
        if (not isinstance(source, str) or not source.strip() or len(source) > 200
                or not isinstance(observed_at, str) or not observed_at.strip() or len(observed_at) > 80
                or not isinstance(snapshot, dict)):
            raise ValueError("reconciliation requires source, observed_at and a snapshot object")
        snapshot_json = self._effect_json(snapshot, "reconciliation snapshot")
        digest = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
        encoded = self._effect_json({"source": source, "observed_at": observed_at,
                                     "snapshot": json.loads(snapshot_json), "evidence_sha256": digest,
                                     "outcome": outcome}, "reconciliation evidence")
        current = self.effect(job_id, effect_key)
        if current is None:
            raise KeyError((job_id, effect_key))
        if current["state"] == outcome and current["result"] == json.loads(encoded):
            return current
        expected = current["state"]
        if expected not in {"dispatching", "uncertain"}:
            raise EffectConflictError(f"effect is {expected}; remote reconciliation is not applicable")
        return self._update_effect(job_id, effect_key, expected=expected, state=outcome,
                                   result_json=encoded, reason=f"remote effect reconciled: {outcome}")

    def _update_effect(self, job_id: str, effect_key: str, *, expected: str, state: str,
                       result_json: str, reason: str) -> dict[str, Any]:
        now = time.time()
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM update_effects WHERE job_id=? AND effect_key=?",
                             (job_id, effect_key)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError((job_id, effect_key))
            if row["state"] == state and row["result_json"] == result_json:
                result = self._decode_effect(row)
                db.commit()
                return result
            if row["state"] != expected:
                db.rollback()
                raise EffectConflictError(f"effect is {row['state']}; expected {expected}")
            db.execute("UPDATE update_effects SET state=?,result_json=?,updated_at=? WHERE job_id=? AND effect_key=?",
                       (state, result_json, now, job_id, effect_key))
            receipt = {"effect_key": effect_key, "kind": row["kind"], "state": state,
                       "intent": json.loads(row["intent_json"]), "result": json.loads(result_json)}
            db.execute(
                "INSERT INTO update_transitions(job_id,from_state,to_state,reason,at,receipt_json) "
                "SELECT ?,state,state,?,?,? FROM update_jobs WHERE job_id=?",
                (job_id, reason, now, json.dumps(receipt, sort_keys=True, ensure_ascii=False), job_id),
            )
            updated = db.execute("SELECT * FROM update_effects WHERE job_id=? AND effect_key=?",
                                 (job_id, effect_key)).fetchone()
            db.commit()
        return self._decode_effect(updated)

    def effect(self, job_id: str, effect_key: str) -> dict[str, Any] | None:
        with self._session() as db:
            row = db.execute("SELECT * FROM update_effects WHERE job_id=? AND effect_key=?",
                             (job_id, effect_key)).fetchone()
            return self._decode_effect(row) if row else None

    def effects(self, job_id: str) -> list[dict[str, Any]]:
        with self._session() as db:
            rows = db.execute("SELECT * FROM update_effects WHERE job_id=? ORDER BY created_at,effect_key",
                              (job_id,)).fetchall()
            return [self._decode_effect(row) for row in rows]

    @staticmethod
    def _decode_effect(row: sqlite3.Row) -> dict[str, Any]:
        return {"job_id": row["job_id"], "effect_key": row["effect_key"], "kind": row["kind"],
                "state": row["state"], "intent": json.loads(row["intent_json"]),
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "attempt": row["attempt"]}

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._session() as db:
            row = db.execute("SELECT * FROM update_jobs WHERE job_id=?", (job_id,)).fetchone()
            return self._decode(row) if row else None

    def list(self) -> list[dict[str, Any]]:
        with self._session() as db:
            return [self._decode(row) for row in db.execute("SELECT * FROM update_jobs ORDER BY created_at DESC")]

    def transitions(self, job_id: str) -> list[dict[str, Any]]:
        with self._session() as db:
            return [dict(row) for row in db.execute("SELECT * FROM update_transitions WHERE job_id=? ORDER BY sequence", (job_id,))]

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["receipt"] = json.loads(result.pop("receipt_json"))
        return result
