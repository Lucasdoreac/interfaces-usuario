"""Load the project's explicit update-vanguard policy without side effects."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_PATH = Path(".sober/updates.toml")
RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}
_CANONICAL_HARNESS_REPOSITORY = "Lucasdoreac/personal-dev-harness"
_UPDATE_VANGUARD_PACKAGE = "personal-dev-harness-update-vanguard"
_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    pass


def load_manifest(root: Path) -> dict[str, Any] | None:
    path = root / MANIFEST_PATH
    if path.parent.is_symlink() or path.is_symlink():
        raise ManifestError(f"update manifest path must not follow symlinks: {path}")
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ManifestError(f"invalid update manifest {path}: {exc}") from exc
    policy = data.get("policy")
    project = data.get("project")
    schema_version = data.get("schema_version")
    if (isinstance(schema_version, bool) or schema_version != 1
            or not isinstance(policy, dict) or not isinstance(project, dict)):
        raise ManifestError(f"unsupported update manifest contract: {path}")
    harness = data.get("harness")
    if harness is not None:
        if not isinstance(harness, dict):
            raise ManifestError("harness pin must be a TOML table")
        revision = harness.get("revision")
        digest = harness.get("source_sha256")
        package = harness.get("package")
        source = harness.get("repository")
        vendor_path = harness.get("path")
        if source != _CANONICAL_HARNESS_REPOSITORY:
            raise ManifestError("harness.repository must name the canonical harness")
        if not isinstance(revision, str) or not _COMMIT_SHA.fullmatch(revision):
            raise ManifestError("harness.revision must be a full immutable commit SHA")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ManifestError("harness.source_sha256 must be a lowercase SHA-256 digest")
        if package != _UPDATE_VANGUARD_PACKAGE:
            raise ManifestError("harness.package must name the canonical update-vanguard distribution")
        if (not isinstance(vendor_path, str) or not vendor_path
                or Path(vendor_path).is_absolute() or ".." in Path(vendor_path).parts
                or "\\" in vendor_path):
            raise ManifestError("harness.path must stay inside the project root")
    name = project.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ManifestError("project.name must be a non-empty string of at most 100 characters")
    if project.get("authority") != "owner":
        raise ManifestError("project.authority must be explicitly owner-authorized")
    if not re.fullmatch(r"[A-Za-z0-9._ -]+", name):
        raise ManifestError("project.name contains unsupported characters")
    version = policy.get("version")
    if (policy.get("capability") != "updates" or isinstance(version, bool)
            or not isinstance(version, int) or version < 1):
        raise ManifestError("policy must declare its own updates capability and integer policy version")
    if policy.get("channel") != "stable":
        raise ManifestError("only the stable release channel is supported")
    if not isinstance(policy.get("enabled"), bool):
        raise ManifestError("policy.enabled must be an explicit boolean")
    impact = data.get("impact", {})
    if not isinstance(impact, dict):
        raise ManifestError("impact must be a TOML table")
    persistent_paths = impact.get("persistent_data_paths", [])
    if (not isinstance(persistent_paths, list)
            or any(not isinstance(path, str) or not path for path in persistent_paths)):
        raise ManifestError("impact.persistent_data_paths must be a list of exact repository paths")
    normalized_persistent_paths = []
    for path in persistent_paths:
        parsed = PurePosixPath(path)
        if ("\\" in path or not parsed.parts or parsed.is_absolute()
                or any(ord(character) < 32 for character in path)
                or any(part in {".", ".."} for part in parsed.parts)
                or "*" in path or "?" in path or "[" in path or "]" in path
                or parsed.as_posix() != path):
            raise ManifestError("impact.persistent_data_paths must contain normalized exact repository paths")
        normalized_persistent_paths.append(path)
    if len(set(normalized_persistent_paths)) != len(normalized_persistent_paths):
        raise ManifestError("impact.persistent_data_paths must not contain duplicates")
    for key in ("auto_merge_risks", "auto_deploy_risks"):
        risks = policy.get(key)
        if not isinstance(risks, list) or any(not isinstance(risk, str) or risk not in RISK_LEVELS for risk in risks):
            raise ManifestError(f"policy.{key} must contain only explicit LOW/MEDIUM/HIGH values")
    limits = policy.get("limits", {})
    max_concurrent = limits.get("max_concurrent_jobs") if isinstance(limits, dict) else None
    if isinstance(max_concurrent, bool) or not isinstance(max_concurrent, int) or not 1 <= max_concurrent <= 32:
        raise ManifestError("policy.limits.max_concurrent_jobs must be between 1 and 32")
    for key, maximum in (("max_changed_packages", 1000), ("max_daily_jobs", 1000)):
        value = limits.get(key) if isinstance(limits, dict) else None
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ManifestError(f"policy.limits.{key} must be between 1 and {maximum}")
    adapters = data.get("adapters", {})
    if not isinstance(adapters, dict) or any(not isinstance(name, str) for name in adapters):
        raise ManifestError("adapters must be a TOML table")
    toolchains = data.get("toolchains", {})
    if not isinstance(toolchains, dict):
        raise ManifestError("toolchains must be a TOML table")
    gates = data.get("gates", {})
    if not isinstance(gates, dict) or not isinstance(gates.get("commands", []), list) or any(
            not isinstance(command, str) or not command.strip() for command in gates.get("commands", [])):
        raise ManifestError("gates.commands must be a list of non-empty strings")
    if not isinstance(gates.get("publish_ci_status", False), bool):
        raise ManifestError("gates.publish_ci_status must be an explicit boolean when configured")
    pr_gate = gates.get("pr")
    if pr_gate is not None:
        if not isinstance(pr_gate, dict):
            raise ManifestError("gates.pr must be a table")
        if not isinstance(pr_gate.get("python"), str) or not pr_gate["python"].strip():
            raise ManifestError("gates.pr.python must name the project interpreter")
        for key in ("merge", "recover"):
            value = pr_gate.get(key, [] if key == "recover" else None)
            if (not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value)):
                raise ManifestError(f"gates.pr.{key} must be a list of command arguments")
        if not pr_gate.get("merge"):
            raise ManifestError("gates.pr.merge must not be empty")
        if not isinstance(pr_gate.get("env", {}), dict) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in pr_gate.get("env", {}).items()):
            raise ManifestError("gates.pr.env must map environment variable names to strings")
        for key in ("uncertain_output", "job_output"):
            if key in pr_gate:
                if not isinstance(pr_gate[key], str):
                    raise ManifestError(f"gates.pr.{key} must be a regular expression string")
                try:
                    re.compile(pr_gate[key])
                except re.error as exc:
                    raise ManifestError(f"gates.pr.{key} is invalid: {exc}") from exc
        codes = pr_gate.get("uncertain_exit_codes", [])
        if not isinstance(codes, list) or any(type(code) is not int or not 1 <= code <= 255 for code in codes):
            raise ManifestError("gates.pr.uncertain_exit_codes must contain exit codes from 1 to 255")
        timeout = pr_gate.get("timeout_seconds", 7200)
        if type(timeout) is not int or not 1 <= timeout <= 86400:
            raise ManifestError("gates.pr.timeout_seconds must be between 1 and 86400")
        if ((pr_gate.get("uncertain_output") or codes)
                and (not pr_gate.get("recover") or not pr_gate.get("job_output"))):
            raise ManifestError(
                "gates.pr uncertain deploy detection requires recover and job_output")
    execution = data.get("execution", {})
    if not isinstance(execution, dict):
        raise ManifestError("execution must be a TOML table")
    adapter = execution.get("adapter", "pending")
    if (not isinstance(adapter, str)
            or adapter not in {"pending", "docker-uv"}
            and not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", adapter)):
        raise ManifestError("execution.adapter must be pending or a valid adapter identifier")
    if adapter == "docker-uv":
        image_id = execution.get("image_id")
        if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise ManifestError("docker-uv requires an immutable execution.image_id")
        project_dir = execution.get("project", ".")
        if (not isinstance(project_dir, str) or not project_dir
                or Path(project_dir).is_absolute() or ".." in Path(project_dir).parts):
            raise ManifestError("execution.project must stay inside the project root")
        for key in ("uv_groups", "uv_extras"):
            values = execution.get(key, [])
            if (not isinstance(values, list) or any(
                    not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value)
                    for value in values)):
                raise ManifestError(f"execution.{key} must contain safe names")
        timeout = execution.get("timeout_seconds", 1800)
        memory = execution.get("memory_mb", 2048)
        venv_mb = execution.get("venv_mb", 1024)
        cpus = execution.get("cpus", 2)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 30 <= timeout <= 7200:
            raise ManifestError("execution.timeout_seconds must be between 30 and 7200")
        if isinstance(memory, bool) or not isinstance(memory, int) or not 256 <= memory <= 8192:
            raise ManifestError("execution.memory_mb must be between 256 and 8192")
        if isinstance(venv_mb, bool) or not isinstance(venv_mb, int) or not 128 <= venv_mb <= 2048:
            raise ManifestError("execution.venv_mb must be between 128 and 2048")
        if venv_mb > memory:
            raise ManifestError("execution.venv_mb cannot exceed the container memory limit")
        if isinstance(cpus, bool) or not isinstance(cpus, (int, float)) or not 0.25 <= cpus <= 8:
            raise ManifestError("execution.cpus must be between 0.25 and 8")
    deployment = data.get("deployment", {})
    if not isinstance(deployment, dict):
        raise ManifestError("deployment must be a TOML table")
    if deployment.get("artifact_kind", "docker-image") not in {"docker-image", "provider-build"}:
        raise ManifestError("deployment.artifact_kind must be docker-image or provider-build")
    probes = deployment.get("probes", [])
    rollback = deployment.get("rollback", "")
    production_enabled = deployment.get("production_enabled", False)
    if (not isinstance(probes, list) or any(not isinstance(probe, str) or not probe.strip() for probe in probes)
            or not isinstance(rollback, str) or not isinstance(production_enabled, bool)):
        raise ManifestError("deployment probes, rollback, or production_enabled have an invalid format")
    return data
