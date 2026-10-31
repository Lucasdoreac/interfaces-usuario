"""PARADIGMA: bounded owner-MCP to host-runner bridge with durable receipts.

The bridge is a local transport only. It accepts typed operations and
never accepts a project path, shell command, credential, or arbitrary payload.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import time
from typing import Any, Iterator
from uuid import UUID

from .capability import UpdateCaller, UpdateCapabilityService, UpdateOperation, UpdateRequest, UpdateResult

_ALLOWED = frozenset({
    UpdateOperation.INVENTORY,
    UpdateOperation.PLAN,
    UpdateOperation.VALIDATE,
    UpdateOperation.STATUS,
    UpdateOperation.CANCEL,
    UpdateOperation.RUN,
    UpdateOperation.TEST,
    UpdateOperation.DEPLOY,
    UpdateOperation.ROLLBACK,
    UpdateOperation.RECOVER,
})
_REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
_JOB_ID = re.compile(r"^[0-9a-f]{24}$")
_MAX_REQUEST_BYTES = 16 * 1024
_OWNER_ACTORS = frozenset({"owner:self-chat", "owner:admin-api", "owner:admin-ui"})
# Container root is unmapped in the host systemd user namespace and is
# therefore observed as the overflow UID on shared inbox files.
_CONTAINER_ROOT_OVERFLOW_UID = 65534
_MAX_RESPONSE_BYTES = 256 * 1024
_MAX_PENDING_REQUESTS = 64
_MAX_REQUEST_AGE_SECONDS = 3600
_MISSION_EVENT_OPERATION = "updates.mission_event"
_REVIEW_OPERATION = "updates.review"
_RESUMABLE_OPERATIONS = frozenset({UpdateOperation.RUN.value, _MISSION_EVENT_OPERATION})


class BridgeError(ValueError):
    """A bridge request is malformed, conflicting, or unsafe."""


def _trusted_request_owner(uid: int) -> bool:
    return uid in {0, os.getuid(), _CONTAINER_ROOT_OVERFLOW_UID}


class UpdateBridge:
    """Filesystem mailbox shared with the API container's project bind mount."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.state = self.root / ".sober" / "update-vanguard-bridge"
        self.inbox = self.state / "inbox"
        self.processing = self.state / "processing"
        self.outbox = self.state / "outbox"
        self.resumable = self.state / "resumable"
        self.lock_path = self.state / "worker.lock"
        self.serve_lock_path = self.state / "serve.lock"
        self.submit_lock_path = self.state / "submit.lock"

    def prepare(self) -> None:
        sober = self.root / ".sober"
        if sober.is_symlink() or self.state.is_symlink():
            raise BridgeError("bridge state must not traverse symlinks")
        for directory in (self.state, self.inbox, self.processing, self.outbox, self.resumable):
            if directory.is_symlink():
                raise BridgeError("bridge directory must not be a symlink")
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not directory.resolve().is_relative_to(self.root):
                raise BridgeError("bridge directory escapes project root")
            info = directory.stat(follow_symlinks=False)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise BridgeError("bridge directories must be private and owned by the host runner")
        if self.lock_path.is_symlink():
            raise BridgeError("bridge lock must not be a symlink")
        if self.submit_lock_path.is_symlink():
            raise BridgeError("bridge submit lock must not be a symlink")
        for lock_path in (self.lock_path, self.submit_lock_path):
            descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            os.close(descriptor)
            info = lock_path.stat(follow_symlinks=False)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise BridgeError("bridge locks must be private and owned by the host runner")

    def submit(self, *, request_id: str, operation: str, actor_id: str,
               job_id: str | None = None, resolve_python: bool = False,
               resolve_actions: bool = False) -> dict[str, Any]:
        """Atomically publish one allowlisted request; identical retries are reads."""
        self._validate_id(request_id)
        try:
            op = UpdateOperation(operation)
        except ValueError as exc:
            raise BridgeError("unsupported update operation") from exc
        if op not in _ALLOWED:
            raise BridgeError("operation has no host bridge adapter")
        if actor_id not in _OWNER_ACTORS:
            raise BridgeError("only an authenticated owner transport may submit")
        if job_id is not None and (not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id)):
            raise BridgeError("job_id must be a 24-character update job id")
        if type(resolve_python) is not bool:
            raise BridgeError("resolve_python must be boolean")
        if op is not UpdateOperation.PLAN and resolve_python:
            raise BridgeError("resolve_python is only valid for updates.plan")
        if type(resolve_actions) is not bool:
            raise BridgeError("resolve_actions must be boolean")
        if op is not UpdateOperation.PLAN and resolve_actions:
            raise BridgeError("resolve_actions is only valid for updates.plan")
        if op in {UpdateOperation.STATUS, UpdateOperation.CANCEL, UpdateOperation.TEST,
                  UpdateOperation.DEPLOY, UpdateOperation.ROLLBACK,
                  UpdateOperation.RECOVER, UpdateOperation.VALIDATE} and not job_id:
            raise BridgeError("status, cancel, test, deploy, rollback, validate and recover require job_id")
        if op in {UpdateOperation.INVENTORY, UpdateOperation.PLAN} and job_id is not None:
            raise BridgeError("inventory and plan do not accept job_id")
        self.prepare()
        request = {
            "schema_version": 1,
            "request_id": request_id,
            "operation": op.value,
            "actor_id": actor_id,
            "job_id": job_id,
            "resolve_python": resolve_python,
            "resolve_actions": resolve_actions,
            "submitted_at": time.time(),
        }
        encoded = _encode(request, _MAX_REQUEST_BYTES, "request")
        with self._submission_lock():
            return self._publish_request(request_id, request, encoded)

    def submit_supervision(self, *, request_id: str, actor_id: str, job_id: str,
                           receipt: dict[str, Any]) -> dict[str, Any]:
        """Submit a bounded review/repair receipt for host validation and ledger append."""
        self._validate_id(request_id)
        if actor_id not in _OWNER_ACTORS or not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
            raise BridgeError("supervision requires an authenticated owner and canonical job ID")
        if not isinstance(receipt, dict) or receipt.get("request_id") != request_id:
            raise BridgeError("supervision receipt must bind to its mailbox request ID")
        self.prepare()
        request = {
            "schema_version": 1, "request_id": request_id,
            "operation": "updates.supervision", "actor_id": actor_id,
            "job_id": job_id, "submitted_at": time.time(),
            "supervision_receipt": receipt,
        }
        encoded = _encode(request, _MAX_REQUEST_BYTES, "supervision request")
        with self._submission_lock():
            return self._publish_request(request_id, request, encoded)

    def submit_review(self, *, request_id: str, actor_id: str, job_id: str,
                      receipt: dict[str, Any]) -> dict[str, Any]:
        """Submit one independent LLM review receipt for an exact candidate SHA."""
        self._validate_id(request_id)
        if actor_id not in _OWNER_ACTORS or not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
            raise BridgeError("review requires an authenticated owner and canonical job ID")
        if not isinstance(receipt, dict) or receipt.get("request_id") != request_id:
            raise BridgeError("review receipt must bind to its mailbox request ID")
        self.prepare()
        request = {
            "schema_version": 1, "request_id": request_id,
            "operation": _REVIEW_OPERATION, "actor_id": actor_id,
            "job_id": job_id, "submitted_at": time.time(),
            "review_receipt": receipt,
        }
        encoded = _encode(request, _MAX_REQUEST_BYTES, "review request")
        with self._submission_lock():
            return self._publish_request(request_id, request, encoded)

    def submit_mission_event(
        self, *, request_id: str, actor_id: str, mission_id: int, job_id: str,
        source_sha: str, event_type: str, checkpoint: dict[str, Any],
    ) -> dict[str, Any]:
        """Publish one bounded owner mission checkpoint for the canonical ledger."""
        self._validate_id(request_id)
        if (actor_id not in _OWNER_ACTORS or type(mission_id) is not int or mission_id < 1
                or not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id)):
            raise BridgeError("mission event requires an authenticated owner, mission and canonical job")
        if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
            raise BridgeError("mission event requires a full source SHA")
        if not isinstance(event_type, str) or not isinstance(checkpoint, dict):
            raise BridgeError("mission event payload is invalid")
        request = {
            "schema_version": 1, "request_id": request_id,
            "operation": _MISSION_EVENT_OPERATION, "actor_id": actor_id,
            "mission_id": mission_id, "job_id": job_id,
            "source_sha": source_sha, "event_type": event_type,
            "checkpoint": checkpoint, "submitted_at": time.time(),
        }
        encoded = _encode(request, _MAX_REQUEST_BYTES, "mission event request")
        self.prepare()
        with self._submission_lock():
            return self._publish_request(request_id, request, encoded)

    def _publish_request(self, request_id: str, request: dict[str, Any], encoded: bytes) -> dict[str, Any]:
        target = self.inbox / f"{request_id}.json"
        processing = self.processing / f"{request_id}.json"
        response = self.outbox / f"{request_id}.json"
        for existing in (target, processing, response):
            if existing.is_symlink():
                raise BridgeError("request path must not be a symlink")
            if existing.is_file():
                if existing == response:
                    if existing.stat(follow_symlinks=False).st_uid != os.getuid():
                        raise BridgeError("response is not owned by the host runner")
                    existing_payload = _validate_response(
                        _decode(existing.read_bytes(), "response"), request_id
                    )
                    if not _same_request(existing_payload.get("request"), request):
                        raise BridgeError("request_id was already used for different input")
                    return {"request_id": request_id, "state": existing_payload["state"],
                            "result": existing_payload.get("result"),
                            "blocker": existing_payload.get("blocker"), "replayed": True}
                if not _same_request(_decode(existing.read_bytes(), "request"), request):
                    raise BridgeError("request_id was already used for different input")
                return {"request_id": request_id,
                        "state": "processing" if existing == processing else "queued",
                        "replayed": True}
        pending = sum(1 for path in self.inbox.glob("*.json") if path.is_file())
        pending += sum(1 for path in self.processing.glob("*.json") if path.is_file())
        if pending >= _MAX_PENDING_REQUESTS:
            raise BridgeError("host update mailbox is full; no request was queued")
        temporary = self.inbox / f".{request_id}.{os.getpid()}.tmp"
        # API container runs as root; mode 0644 lets the host runner read the
        # request while the parent mailbox directory remains host-owned 0700.
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        try:
            os.fchmod(descriptor, 0o644)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                if target.is_symlink() or not _same_request(_decode(target.read_bytes(), "request"), request):
                    raise BridgeError("request_id was concurrently used for different input")
        finally:
            temporary.unlink(missing_ok=True)
        return {"request_id": request_id, "state": "queued", "replayed": False}

    @contextmanager
    def _submission_lock(self) -> Iterator[None]:
        descriptor = os.open(self.submit_lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(descriptor, "a+b") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def result(self, request_id: str) -> dict[str, Any] | None:
        self.prepare()
        self._validate_id(request_id)
        response = self.outbox / f"{request_id}.json"
        if response.is_symlink():
            raise BridgeError("response path must not be a symlink")
        if response.is_file():
            if response.stat(follow_symlinks=False).st_uid != os.getuid():
                raise BridgeError("response is not owned by the host runner")
            return _validate_response(_decode(response.read_bytes(), "response"), request_id)
        if (self.processing / f"{request_id}.json").is_file():
            return {"schema_version": 1, "request_id": request_id, "state": "processing"}
        if (self.inbox / f"{request_id}.json").is_file():
            return {"schema_version": 1, "request_id": request_id, "state": "queued"}
        return None

    @contextmanager
    def _worker_lock(self) -> Iterator[None]:
        self.prepare()
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(descriptor, "a+b") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    @contextmanager
    def serving(self) -> Iterator[None]:
        """Own the mailbox for one server lifetime and reconcile stale claims once."""
        self.prepare()
        descriptor = os.open(self.serve_lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(descriptor, "a+b") as stream:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise BridgeError("an update bridge server already owns this mailbox") from exc
            with self._worker_lock():
                self._reconcile_interrupted()
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def run_once(self, service: UpdateCapabilityService | None = None, *,
                 reconcile: bool = True) -> dict[str, Any] | None:
        """Claim under a short lock, then dispatch so another worker can handle CANCEL."""
        service = service or UpdateCapabilityService(self.root, allow_upstream_resolution=True)
        with self._worker_lock():
            if reconcile:
                self._reconcile_interrupted()
            candidates = sorted(self.inbox.glob("*.json"))
            claimed = None
            request_id = None
            for candidate in candidates:
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                info = candidate.stat(follow_symlinks=False)
                if (not _trusted_request_owner(info.st_uid)
                        or stat.S_IMODE(info.st_mode) & 0o022):
                    continue
                request_id = candidate.stem
                if not _REQUEST_ID.fullmatch(request_id):
                    continue
                claimed = self.processing / candidate.name
                try:
                    os.replace(candidate, claimed)
                except FileNotFoundError:
                    continue
                break
            else:
                return None
        try:
            request = _decode(claimed.read_bytes(), "request")
            resumed = self._is_resumable(request_id, request)
            if resumed:
                request["submitted_at"] = time.time()
            result = self._dispatch(service, request, expected_request_id=request_id,
                                    allow_expired=resumed)
            if (request.get("operation") == UpdateOperation.RUN.value
                    and result.get("state") in {"blocked", "uncertain"}):
                _record_run_supervision(service, request_id, result)
        except (BridgeError, OSError, ValueError, TypeError) as exc:
            result = {"state": "rejected", "blocker": str(exc)[:240], "result": None}
            request = {"request_id": request_id}
        response = {"schema_version": 1, "request_id": request_id, "request": request,
                    **result, "completed_at": time.time()}
        self._write_response(request_id, response)
        claimed.unlink(missing_ok=True)
        (self.resumable / f"{request_id}.json").unlink(missing_ok=True)
        return response


    def _dispatch(self, service: UpdateCapabilityService, request: dict[str, Any],
                  *, expected_request_id: str, allow_expired: bool = False) -> dict[str, Any]:
        request = _trusted_request(request, expected_request_id, allow_expired=allow_expired)
        if request["operation"] == _MISSION_EVENT_OPERATION:
            recorded = service._ledger().record_mission_event(
                job_id=request["job_id"], mission_id=request["mission_id"],
                event_id=request["request_id"], source_sha=request["source_sha"],
                event_type=request["event_type"], checkpoint=request["checkpoint"],
            )
            return {"state": "completed", "result": {"event_recorded": recorded}, "blocker": None}
        if request["operation"] == _REVIEW_OPERATION:
            recorded = service._ledger().record_independent_review(
                request["job_id"], request["review_receipt"],
            )
            return {"state": "completed", "result": {"review_recorded": recorded}, "blocker": None}
        if request["operation"] == "updates.supervision":
            loaded = service._job_ledger(request["job_id"])
            if isinstance(loaded, UpdateResult):
                raise BridgeError("canonical job is unavailable for supervision receipt")
            ledger, _job = loaded
            appended = ledger.record_supervision(request["job_id"], request["supervision_receipt"])
            return {"state": "completed", "result": {"receipt_appended": appended}, "blocker": None}
        operation = UpdateOperation(request["operation"])
        if operation in {UpdateOperation.STATUS, UpdateOperation.CANCEL} and not request["job_id"]:
            raise BridgeError("status and cancel require job_id")
        caller = UpdateCaller(request["actor_id"], True, frozenset({operation}), trusted_host_runner=True)
        result = service.dispatch(UpdateRequest(operation, request["job_id"], request["resolve_python"],
                                                request["resolve_actions"]), caller)
        return {"state": "completed" if result.ok else "blocked",
                "result": _compact_result(result.data), "blocker": result.blocker}

    def _mark_resumable(self, request_id: str, request: dict[str, Any]) -> None:
        fingerprint = {key: value for key, value in request.items() if key != "submitted_at"}
        target = self.resumable / f"{request_id}.json"
        accepted_at = request["submitted_at"]
        if target.is_file() and not target.is_symlink():
            prior = _decode(target.read_bytes(), "continuation marker")
            if prior.get("request_id") == request_id:
                accepted_at = prior.get("accepted_at", accepted_at)
        marker = {"request_id": request_id,
                  "accepted_at": accepted_at,
                  "sha256": hashlib.sha256(_encode(fingerprint, _MAX_REQUEST_BYTES,
                                                    "continuation fingerprint")).hexdigest()}
        encoded = _encode(marker, 1024, "continuation marker")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{request_id}.", suffix=".tmp", dir=self.resumable,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _is_resumable(self, request_id: str, request: dict[str, Any]) -> bool:
        marker_path = self.resumable / f"{request_id}.json"
        if marker_path.is_symlink() or not marker_path.is_file():
            return False
        info = marker_path.stat(follow_symlinks=False)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise BridgeError("continuation marker is not private and host-owned")
        marker = _decode(marker_path.read_bytes(), "continuation marker")
        fingerprint = {key: value for key, value in request.items() if key != "submitted_at"}
        expected = hashlib.sha256(_encode(fingerprint, _MAX_REQUEST_BYTES,
                                          "continuation fingerprint")).hexdigest()
        return (marker.get("request_id") == request_id
                and marker.get("sha256") == expected
                and isinstance(marker.get("accepted_at"), (int, float))
                and not isinstance(marker.get("accepted_at"), bool))

    def _reconcile_interrupted(self) -> None:
        for claimed in sorted(self.processing.glob("*.json")):
            if claimed.is_symlink() or not claimed.is_file():
                continue
            request_id = claimed.stem
            if not _REQUEST_ID.fullmatch(request_id):
                continue
            existing = self.outbox / claimed.name
            if existing.exists():
                if (existing.is_symlink()
                        or existing.stat(follow_symlinks=False).st_uid != os.getuid()):
                    raise BridgeError("existing response is not owned by the host runner")
                _validate_response(_decode(existing.read_bytes(), "response"), request_id)
                claimed.unlink(missing_ok=True)
                (self.resumable / claimed.name).unlink(missing_ok=True)
                continue
            try:
                decoded = _decode(claimed.read_bytes(), "request")
                resuming_idempotent = decoded.get("operation") in _RESUMABLE_OPERATIONS
                request = _trusted_request(
                    decoded, request_id, allow_expired=resuming_idempotent,
                )
            except (BridgeError, OSError):
                request = {"request_id": request_id}
            # RUN reconciles its durable effect ledger before progressing.
            # MISSION_EVENT only appends an exact, digest-bound event; replay
            # acknowledges a prior append or validates a new one. Neither can
            # repeat a one-shot external effect. Other operations stay uncertain.
            if request.get("operation") in _RESUMABLE_OPERATIONS:
                # Refresh the admission timestamp only after proving this is
                # an already-claimed, trusted idempotent request. `_dispatch`
                # applies the ordinary one-hour age limit when it returns
                # to the inbox; retaining the original timestamp would reject
                # a valid continuation after a long host outage.
                self._mark_resumable(request_id, request)
                request["submitted_at"] = time.time()
                encoded = _encode(request, _MAX_REQUEST_BYTES, "request")
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{request_id}.", suffix=".resume.tmp", dir=self.processing,
                )
                temporary = Path(temporary_name)
                try:
                    with os.fdopen(descriptor, "wb") as stream:
                        os.fchmod(stream.fileno(), 0o644)
                        stream.write(encoded)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, claimed)
                finally:
                    temporary.unlink(missing_ok=True)
                target = self.inbox / claimed.name
                try:
                    os.link(claimed, target)
                except FileExistsError:
                    try:
                        if target.is_symlink() or not target.is_file():
                            raise BridgeError("queued continuation path is not a regular file")
                        duplicate_payload = _decode(target.read_bytes(), "request")
                        duplicate = _trusted_request(
                            duplicate_payload, request_id,
                            allow_expired=self._is_resumable(request_id, duplicate_payload),
                        )
                    except (BridgeError, OSError):
                        duplicate = None
                    if duplicate is not None and _same_request(duplicate, request):
                        claimed.unlink()
                        continue
                    # Reusing one request ID for different content is a hard
                    # rejection. Remove only the conflicting leaf inside the
                    # private inbox so run_once cannot dispatch it after this
                    # interrupted claim has been rejected.
                    self._write_response(request_id, {
                        "schema_version": 1,
                        "request_id": request_id,
                        "request": request,
                        "state": "rejected",
                        "result": None,
                        "blocker": "conflicting queued request reused the continuation ID; nothing was dispatched",
                        "completed_at": time.time(),
                    })
                    if target.is_file() or target.is_symlink():
                        target.unlink(missing_ok=True)
                    claimed.unlink(missing_ok=True)
                    continue
                else:
                    claimed.unlink()
                    continue
            self._write_response(request_id, {
                "schema_version": 1,
                "request_id": request_id,
                "request": request,
                "state": "uncertain",
                "result": None,
                "blocker": "runner stopped after claiming request; no automatic replay performed",
                "completed_at": time.time(),
            })
            claimed.unlink(missing_ok=True)

    def _write_response(self, request_id: str, response: dict[str, Any]) -> None:
        encoded = _encode(response, _MAX_RESPONSE_BYTES, "response")
        target = self.outbox / f"{request_id}.json"
        if target.is_symlink():
            raise BridgeError("response path must not be a symlink")
        temporary = self.outbox / f".{request_id}.{os.getpid()}.tmp"
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            if target.exists():
                raise BridgeError("response already exists; refusing overwrite")
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _validate_id(request_id: str) -> None:
        try:
            parsed = UUID(hex=request_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise BridgeError("request_id must be a lowercase 32-character UUID hex") from exc
        if parsed.hex != request_id or not _REQUEST_ID.fullmatch(request_id):
            raise BridgeError("request_id must be a lowercase 32-character UUID hex")


def _record_run_supervision(service: UpdateCapabilityService, request_id: str,
                            outcome: dict[str, Any]) -> None:
    """Persist a bounded failure checkpoint in the same canonical plan.

    This is a checkpoint, not permission to repair or retry. Until independent
    review and repair evidence exists, unknown failures advance only to
    diagnosis; uncertain effects advance only to reconciliation.
    """
    data = outcome.get("result")
    job_id = data.get("job_id") if isinstance(data, dict) else None
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        return
    loaded = service._job_ledger(job_id)
    if isinstance(loaded, UpdateResult):
        return
    ledger, job = loaded
    source_sha = job.get("head_sha")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[a-f0-9]{40,64}", source_sha):
        return
    receipt = job.get("receipt", {})
    plan = receipt.get("plan", {}) if isinstance(receipt, dict) else {}
    attempts = receipt.get("supervision", {}).get("attempts", []) if isinstance(receipt, dict) else []
    if isinstance(attempts, list) and any(
            isinstance(item, dict) and item.get("request_id") == request_id for item in attempts):
        return
    attempt = len(attempts) + 1 if isinstance(attempts, list) else 1
    blocker = outcome.get("blocker")
    diagnostic_text = blocker if isinstance(blocker, str) else "updates.run returned without a blocker"
    lowered = diagnostic_text.casefold()
    if outcome.get("state") == "uncertain" or "uncertain" in lowered:
        classification, next_step, stage = "uncertain_effect", "reconcile", "recovery"
    elif any(term in lowered for term in (
            "missing evidence", "external proof", "authorization required",
            "not authorized", "permission denied", "credential missing")):
        classification, next_step, stage = "external_proof", "await_external", "plan"
    elif any(term in lowered for term in (
            "temporarily unavailable", "service unavailable", "connection reset",
            "network is unreachable", "rate limit", "timed out", "timeout", "http 429", "http 503")):
        classification, next_step = "transient", "retry"
        stage = _supervision_stage(data, lowered)
    elif any(term in lowered for term in (
            "test failed", "tests failed", "isolated candidate gates did not pass",
            "canonical code gate failed")):
        classification, next_step = "auto_correctable", "review"
        stage = _supervision_stage(data, lowered)
    elif "health probe failed" in lowered or "health probes failed" in lowered:
        classification, next_step, stage = "unknown", "diagnose", "probe"
    else:
        classification, next_step = "unknown", "diagnose"
        stage = _supervision_stage(data, lowered)
    ledger.record_supervision(job_id, {
        "request_id": request_id, "source_sha": source_sha, "stage": stage,
        "classification": classification, "attempt": attempt,
        "diagnostic": {"gate": "updates.run", "output_sha256": hashlib.sha256(
            diagnostic_text.encode("utf-8")).hexdigest()},
        "review": {"status": "pending"}, "repair": {"status": "pending"},
        "next_step": next_step, "at": time.time(),
    })


def _supervision_stage(data: Any, diagnostic: str) -> str:
    """Infer a stage only from concrete result fields or an explicit diagnostic."""
    if "probe" in diagnostic or "health" in diagnostic:
        return "probe"
    if "test" in diagnostic or "validation" in diagnostic:
        return "validate"
    if isinstance(data, dict):
        if "validation" in data:
            return "post_deploy"
        if "deployment" in data:
            return "deploy"
        if "execution" in data or "tests" in data:
            return "validate"
    return "plan"


def _encode(value: dict[str, Any], limit: int, label: str) -> bytes:
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BridgeError(f"{label} is not valid JSON") from exc
    if len(encoded) > limit:
        raise BridgeError(f"{label} exceeds size limit")
    return encoded


def _decode(data: bytes, label: str) -> dict[str, Any]:
    if len(data) > (_MAX_RESPONSE_BYTES if label == "response" else _MAX_REQUEST_BYTES):
        raise BridgeError(f"{label} exceeds size limit")
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise BridgeError(f"{label} must be an object")
    return value


def _same_request(left: Any, right: dict[str, Any]) -> bool:
    if not isinstance(left, dict):
        return False
    return ({key: value for key, value in left.items() if key != "submitted_at"}
            == {key: value for key, value in right.items() if key != "submitted_at"})


def _compact_result(value: Any) -> Any:
    """Keep large candidate lock diffs in the canonical ledger, not mailbox copies."""
    if isinstance(value, list):
        return [_compact_result(item) for item in value]
    if not isinstance(value, dict):
        return value
    compacted: dict[str, Any] = {}
    for key, item in value.items():
        if key == "lock_diff" and isinstance(item, str):
            encoded = item.encode("utf-8")
            if len(encoded) > 16 * 1024:
                compacted["lock_diff_summary"] = {
                    "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest(),
                }
                continue
        compacted[key] = _compact_result(item)
    return compacted


def _trusted_request(request: dict[str, Any], request_id: str, *,
                     allow_expired: bool = False) -> dict[str, Any]:
    if isinstance(request, dict) and request.get("operation") == _MISSION_EVENT_OPERATION:
        required = {"schema_version", "request_id", "operation", "actor_id", "mission_id",
                    "job_id", "source_sha", "event_type", "checkpoint", "submitted_at"}
        if set(request) != required or request.get("schema_version") != 1:
            raise BridgeError("mission event request schema is invalid")
        UpdateBridge._validate_id(request_id)
        if (request.get("request_id") != request_id
                or request.get("actor_id") not in _OWNER_ACTORS
                or type(request.get("mission_id")) is not int or request["mission_id"] < 1
                or not isinstance(request.get("job_id"), str)
                or not _JOB_ID.fullmatch(request["job_id"])
                or not isinstance(request.get("source_sha"), str)
                or not re.fullmatch(r"[0-9a-f]{40}", request["source_sha"])
                or not isinstance(request.get("event_type"), str)
                or not isinstance(request.get("checkpoint"), dict)):
            raise BridgeError("mission event request identity is invalid")
        submitted_at = request.get("submitted_at")
        if (isinstance(submitted_at, bool) or not isinstance(submitted_at, (int, float))
                or not math.isfinite(submitted_at)
                or (not allow_expired and time.time() - submitted_at > _MAX_REQUEST_AGE_SECONDS)):
            raise BridgeError("mission event request timestamp is invalid")
        return request
    if isinstance(request, dict) and request.get("operation") == _REVIEW_OPERATION:
        required = {"schema_version", "request_id", "operation", "actor_id", "job_id",
                    "submitted_at", "review_receipt"}
        if set(request) != required or request.get("schema_version") != 1:
            raise BridgeError("review request schema is invalid")
        UpdateBridge._validate_id(request_id)
        if (request.get("request_id") != request_id
                or request.get("actor_id") not in _OWNER_ACTORS
                or not isinstance(request.get("job_id"), str)
                or not _JOB_ID.fullmatch(request["job_id"])
                or not isinstance(request.get("review_receipt"), dict)
                or request["review_receipt"].get("request_id") != request_id):
            raise BridgeError("review request identity is invalid")
        submitted_at = request.get("submitted_at")
        if (isinstance(submitted_at, bool) or not isinstance(submitted_at, (int, float))
                or not math.isfinite(submitted_at)
                or (not allow_expired and time.time() - submitted_at > _MAX_REQUEST_AGE_SECONDS)):
            raise BridgeError("review request timestamp is invalid")
        return request
    if isinstance(request, dict) and request.get("operation") == "updates.supervision":
        required = {"schema_version", "request_id", "operation", "actor_id", "job_id",
                    "submitted_at", "supervision_receipt"}
        if set(request) != required or request.get("schema_version") != 1:
            raise BridgeError("supervision request schema is invalid")
        UpdateBridge._validate_id(request_id)
        if (request.get("request_id") != request_id
                or request.get("actor_id") not in _OWNER_ACTORS
                or not isinstance(request.get("job_id"), str)
                or not _JOB_ID.fullmatch(request["job_id"])
                or not isinstance(request.get("supervision_receipt"), dict)):
            raise BridgeError("supervision request identity is invalid")
        submitted_at = request.get("submitted_at")
        if (isinstance(submitted_at, bool) or not isinstance(submitted_at, (int, float))
                or not math.isfinite(submitted_at)
                or (not allow_expired and time.time() - submitted_at > _MAX_REQUEST_AGE_SECONDS)):
            raise BridgeError("supervision request timestamp is invalid")
        if request["supervision_receipt"].get("request_id") != request_id:
            raise BridgeError("supervision receipt identity does not match mailbox request")
        return request
    required = {"schema_version", "request_id", "operation", "actor_id", "job_id",
                "resolve_python", "resolve_actions", "submitted_at"}
    if set(request) != required or request.get("schema_version") != 1:
        raise BridgeError("interrupted request schema is invalid")
    UpdateBridge._validate_id(request_id)
    if request.get("request_id") != request_id or request.get("actor_id") not in _OWNER_ACTORS:
        raise BridgeError("interrupted request identity is invalid")
    operation = UpdateOperation(request.get("operation"))
    if operation not in _ALLOWED:
        raise BridgeError("interrupted request operation is unsupported")
    job_id = request.get("job_id")
    if job_id is not None and (not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id)):
        raise BridgeError("interrupted request job id is invalid")
    if operation in {UpdateOperation.STATUS, UpdateOperation.CANCEL, UpdateOperation.TEST,
                     UpdateOperation.DEPLOY,
                     UpdateOperation.ROLLBACK, UpdateOperation.RECOVER,
                     UpdateOperation.VALIDATE} and job_id is None:
        raise BridgeError("interrupted request job id is missing")
    if operation in {UpdateOperation.INVENTORY, UpdateOperation.PLAN} and job_id is not None:
        raise BridgeError("interrupted request contains an unexpected job id")
    if type(request.get("resolve_python")) is not bool:
        raise BridgeError("interrupted request option is invalid")
    if request["resolve_python"] and operation is not UpdateOperation.PLAN:
        raise BridgeError("interrupted request option is invalid")
    if type(request.get("resolve_actions")) is not bool:
        raise BridgeError("interrupted request option is invalid")
    if request["resolve_actions"] and operation is not UpdateOperation.PLAN:
        raise BridgeError("interrupted request option is invalid")
    submitted_at = request.get("submitted_at")
    if (isinstance(submitted_at, bool) or not isinstance(submitted_at, (int, float))
            or not math.isfinite(submitted_at)):
        raise BridgeError("interrupted request timestamp is invalid")
    if not allow_expired and time.time() - submitted_at > _MAX_REQUEST_AGE_SECONDS:
        raise BridgeError("request expired before the host runner claimed it")
    return request


def _validate_response(response: dict[str, Any], request_id: str) -> dict[str, Any]:
    allowed = {"schema_version", "request_id", "request", "state", "result", "blocker", "completed_at"}
    states = {"completed", "blocked", "rejected", "uncertain"}
    if (set(response) != allowed or response.get("schema_version") != 1
            or response.get("request_id") != request_id or response.get("state") not in states):
        raise BridgeError("host response envelope is invalid")
    original = response.get("request")
    if not isinstance(original, dict) or original.get("request_id") != request_id:
        raise BridgeError("host response request identity is invalid")
    if response.get("result") is not None and not isinstance(response["result"], dict):
        raise BridgeError("host response result must be an object")
    blocker = response.get("blocker")
    if blocker is not None and (not isinstance(blocker, str) or len(blocker) > 240):
        raise BridgeError("host response blocker is invalid")
    completed_at = response.get("completed_at")
    if (isinstance(completed_at, bool) or not isinstance(completed_at, (int, float))
            or not math.isfinite(completed_at)):
        raise BridgeError("host response timestamp is invalid")
    return response
