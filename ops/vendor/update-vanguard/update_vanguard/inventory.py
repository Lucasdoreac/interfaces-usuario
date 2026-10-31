"""Conservative source discovery. Unsupported parsers remain visible as gaps."""

from __future__ import annotations

import hashlib
import fnmatch
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from .manifest import MANIFEST_PATH, load_manifest
from .source_pin import snapshot_digest


# `.sober` is harness-owned state (ledger, scratch, and generated candidates),
# not the project's source inventory. In particular, generated workflow
# candidates must not be rediscovered as additional project workflows.
IGNORE_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".tox", ".sober"}
_UPDATE_STATE_EXCLUSIONS = (
    ":(exclude).sober/update-vanguard.sqlite3",
    ":(exclude).sober/update-vanguard.sqlite3-shm",
    ":(exclude).sober/update-vanguard.sqlite3-wal",
    ":(exclude).sober/update-vanguard-bridge/**",
    ":(exclude).sober/update-vanguard-candidates/**",
    ":(exclude).sober/update-vanguard-scratch/**",
    ":(exclude).sober/current",
    ":(exclude).sober/update-vanguard-releases/**",
)


def _normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _git(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def git_worktree_status(root: Path) -> str | None:
    """Return porcelain status excluding only the update core's managed state."""
    try:
        return subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all",
             "--", ".", *_UPDATE_STATE_EXCLUSIONS],
            cwd=root, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _files(root: Path, pattern: str) -> list[Path]:
    """Find matching files without descending into ignored runtime trees.

    Filtering a recursive glob's results is too late: update-vanguard releases
    contain full virtual environments under `.sober`, so a single inventory
    could walk gigabytes of generated packages before dropping those paths.
    Prune directory names before `os.walk` opens them.
    """
    matches: list[Path] = []
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name for name in directories
            if name not in IGNORE_PARTS and not (current_path / name).is_symlink()
        )
        for name in files:
            if fnmatch.fnmatchcase(name, pattern):
                path = current_path / name
                if not path.is_symlink():
                    matches.append(path)
    return sorted(matches)


def _parse_jsonc(source: str) -> Any:
    """Parse Dev Container JSONC without treating comment markers in strings as syntax."""
    clean: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(source):
        char = source[index]
        if in_string:
            clean.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            clean.append(char)
            index += 1
            continue
        if source.startswith("//", index):
            newline = source.find("\n", index + 2)
            if newline < 0:
                break
            clean.append("\n")
            index = newline + 1
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                raise ValueError("unterminated JSONC block comment")
            clean.extend("\n" for item in source[index:end + 2] if item == "\n")
            index = end + 2
            continue
        clean.append(char)
        index += 1
    if in_string:
        raise ValueError("unterminated JSONC string")

    uncommented = "".join(clean)
    clean.clear()
    index = 0
    in_string = False
    escaped = False
    while index < len(uncommented):
        char = uncommented[index]
        if in_string:
            clean.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            clean.append(char)
            index += 1
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < len(uncommented) and uncommented[lookahead].isspace():
                lookahead += 1
            if lookahead < len(uncommented) and uncommented[lookahead] in "}]":
                index += 1
                continue
        clean.append(char)
        index += 1
    return json.loads("".join(clean))


def _python_projects(root: Path, excluded_roots: tuple[Path, ...] = ()) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for pyproject in _files(root, "pyproject.toml"):
        if any(excluded == pyproject or excluded in pyproject.parents for excluded in excluded_roots):
            continue
        lock = pyproject.with_name("uv.lock")
        record: dict[str, Any] = {
            "manifest": pyproject.relative_to(root).as_posix(),
            "lock": lock.relative_to(root).as_posix() if lock.is_file() else None,
            "resolver": "uv" if lock.is_file() else None,
            "state": "covered" if lock.is_file() else "pending",
            "packages": [],
        }
        try:
            config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            project = config.get("project", {})
            declared: list[str] = []
            optional = project.get("optional-dependencies", {})
            groups = config.get("dependency-groups", {})
            if not isinstance(optional, dict) or not isinstance(groups, dict):
                raise ValueError("dependency groups must be TOML tables")
            dependency_lists = [project.get("dependencies", []), *optional.values(), *groups.values()]
            build_system = config.get("build-system", {})
            if not isinstance(build_system, dict):
                raise ValueError("build-system must be a TOML table")
            for dependencies in dependency_lists:
                if not isinstance(dependencies, list) or any(not isinstance(dep, str) for dep in dependencies):
                    raise ValueError("unsupported dependency declaration format")
                declared.extend(dependencies)
            if any(not dep.strip() for dep in declared):
                raise ValueError("empty dependency declaration")
            direct_names = {_normalize_package_name(re.split(r"[ <>=!~;\[]", dep, maxsplit=1)[0]) for dep in declared}
            build_requirements = build_system.get("requires", [])
            if not isinstance(build_requirements, list) or any(not isinstance(dep, str) or not dep.strip() for dep in build_requirements):
                raise ValueError("unsupported build-system requirements format")
            build_names = {_normalize_package_name(re.split(r"[ <>=!~;\[]", dep, maxsplit=1)[0]) for dep in build_requirements}
            record["declared_direct"] = sorted(direct_names)
            record["declared_build_requirements"] = sorted(build_names)
            if lock.is_file():
                lock_data = tomllib.loads(lock.read_text(encoding="utf-8"))
                packages = lock_data.get("package")
                if not isinstance(packages, list) or not lock_data.get("version"):
                    raise ValueError("uv.lock has no supported package graph")
                lock_names = {_normalize_package_name(str(item.get("name", ""))) for item in packages if item.get("name")}
                missing_direct = sorted(direct_names - lock_names)
                missing_transitive: set[str] = set()
                for package in packages:
                    for dependency in package.get("dependencies", []):
                        if isinstance(dependency, str):
                            dependency_name = dependency
                        elif isinstance(dependency, dict) and isinstance(dependency.get("name"), str):
                            dependency_name = dependency["name"]
                        else:
                            raise ValueError("unsupported dependency edge in uv.lock")
                        normalized_dependency = _normalize_package_name(dependency_name)
                        if normalized_dependency not in lock_names:
                            missing_transitive.add(normalized_dependency)
                record["packages"] = sorted(
                    {f"{item.get('name')}=={item.get('version')}" for item in packages if item.get("name") and item.get("version")}
                )
                record["lock_sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest()
                record["missing_direct"] = missing_direct
                record["missing_transitive"] = sorted(missing_transitive)
                record["runtime_graph_state"] = (
                    "covered" if record["packages"] and not missing_direct and not missing_transitive else "pending"
                )
                if not build_names:
                    record["build_resolution"] = "not_declared"
                else:
                    # PEP 517 requirements are not implicitly part of uv's project graph.
                    # The project must mirror them in a dedicated PEP 735 group so the
                    # normal universal uv.lock resolver can pin their full transitive graph.
                    build_group = groups.get("build-system")
                    missing_build = sorted(build_names - lock_names)
                    group_matches = build_group == build_requirements
                    record["build_group"] = "build-system"
                    record["missing_build"] = missing_build
                    record["build_resolution"] = (
                        "covered" if group_matches and not missing_build else "pending"
                    )
                record["state"] = "covered" if (
                    record["runtime_graph_state"] == "covered"
                    and record["build_resolution"] in {"covered", "not_declared"}
                ) else "pending"
                if build_names and record["build_resolution"] != "covered":
                    record["reason"] = (
                        "build-system.requires must match dependency-groups.build-system and every "
                        "build requirement must appear in uv.lock"
                    )
        except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValueError, AttributeError, TypeError) as exc:
            record["state"] = "pending"
            record["runtime_graph_state"] = "pending"
            record["reason"] = f"cannot parse complete uv graph: {exc}"
        projects.append(record)
    return projects


def inventory(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = load_manifest(root)
    artifacts: list[dict[str, Any]] = []
    excluded_roots: tuple[Path, ...] = ()
    harness = manifest.get("harness") if manifest else None
    if harness is not None:
        vendor = root / harness["path"]
        pin_state = "pending"
        observed_digest = None
        reason = "vendored source does not match its immutable digest"
        try:
            if vendor.is_symlink() or not vendor.is_dir():
                raise ValueError("vendored source is missing or a symlink")
            resolved_vendor = vendor.resolve(strict=True)
            if root not in resolved_vendor.parents:
                raise ValueError("vendored source escapes the project root")
            observed_digest = snapshot_digest(resolved_vendor)
            if observed_digest == harness["source_sha256"]:
                pin_state = "covered"
                reason = "vendored source matches the canonical digest"
                excluded_roots = (resolved_vendor,)
        except (OSError, ValueError) as exc:
            reason = str(exc)
        artifacts.append({
            "kind": "harness-package", "path": harness["path"], "revision": harness["revision"],
            "source_sha256": harness["source_sha256"], "observed_sha256": observed_digest,
            "state": pin_state, "reason": reason,
        })
    for path in _files(root, "Dockerfile*") + _files(root, "Containerfile*"):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        images = [match.group(1) for line in lines
                  if (match := re.match(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)", line, re.IGNORECASE))]
        packages = [line.strip() for line in lines if re.search(r"\b(?:apt-get|apt)\s+install\b", line)]
        artifacts.append({"kind": "dockerfile", "path": path.relative_to(root).as_posix(), "images": images,
                          "os_package_declarations": packages, "state": "pending",
                          "reason": "image tags and OS packages lack a verified stable resolver"})
    for pattern, kind in (("docker-compose*.yml", "compose"), ("docker-compose*.yaml", "compose"),
                          ("compose*.yml", "compose"), ("compose*.yaml", "compose"),
                          ("devcontainer.json", "devcontainer")):
        for path in _files(root, pattern):
            references: dict[str, Any] = {}
            if kind == "compose":
                references["images"] = re.findall(
                    r"(?m)^\s*image:\s*([^\s#]+)", path.read_text(encoding="utf-8", errors="replace")
                )
            else:
                try:
                    data = _parse_jsonc(path.read_text(encoding="utf-8"))
                    references = {key: data.get(key) for key in ("image", "dockerFile", "dockerComposeFile", "features") if key in data}
                    references["referenced_files"] = sorted({
                        item for key in ("dockerFile", "dockerComposeFile")
                        for item in ([data[key]] if isinstance(data.get(key), str) else data.get(key, []))
                        if isinstance(item, str)
                    })
                except (OSError, UnicodeError, json.JSONDecodeError):
                    references["parse_error"] = "invalid devcontainer JSON"
            artifacts.append({"kind": kind, "path": path.relative_to(root).as_posix(), **references,
                              "state": "pending", "reason": "format-specific stable resolver is not installed"})
    for path in _files(root, "*.yml") + _files(root, "*.yaml"):
        if ".github/workflows" not in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        action_lines = re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)(?:\s*(#.*))?$", text)
        uses = [target for target, _comment in action_lines]
        remote = [reference for reference in uses if not reference.startswith(("./", "docker://"))]
        stable_pin = re.compile(
            r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*@[0-9a-f]{40}"
        )
        stable_tag = re.compile(r"#\s*v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\s*$")
        immutable = all(
            stable_pin.fullmatch(target) and stable_tag.search(comment or "")
            for target, comment in action_lines if not target.startswith(("./", "docker://"))
        )
        artifacts.append({"kind": "github-actions", "path": path.relative_to(root).as_posix(), "references": uses,
                          "state": "covered" if immutable else "partial" if uses else "pending",
                          "reason": "immutable SHA with stable release annotation" if immutable else
                                   "references found; stable release and immutable SHA pinning is pending"})
    for pattern in ("requirements*.txt", "requirements*.in", "Pipfile", "Pipfile.lock", "poetry.lock", "pdm.lock",
                    "setup.py", "setup.cfg", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
                    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum", "Gemfile", "Gemfile.lock", "composer.json",
                    "pom.xml", "build.gradle", "build.gradle.kts", "environment.yml", "conda-lock.yml",
                    "Package.swift", "Package.resolved", "mix.exs", "mix.lock", "rebar.config", "rebar.lock",
                    "*.csproj", "*.fsproj", "*.vbproj", "*.sln", "Directory.Packages.props",
                    "packages.lock.json", "NuGet.config", "*.cabal", "cabal.project", "cabal.project.freeze",
                    "stack.yaml", "stack.yaml.lock", "build.sbt", "cpanfile"):
        for path in _files(root, pattern):
            artifacts.append({"kind": "unresolved-package-source", "path": path.relative_to(root).as_posix(),
                              "state": "pending", "reason": "no verified ecosystem adapter is configured"})
    for pattern in (".python-version", ".tool-versions", "mise.toml", "rust-toolchain.toml", ".nvmrc",
                    ".node-version", "global.json", "project/build.properties"):
        for path in _files(root, pattern):
            artifacts.append({"kind": "toolchain", "path": path.relative_to(root).as_posix(),
                              "declaration": path.read_text(encoding="utf-8", errors="replace").strip(),
                              "state": "pending", "reason": "toolchain version resolver is not configured"})
    python_projects = _python_projects(root, excluded_roots)
    # GitHub Actions discovery is informational. The local canonical release
    # gate does not depend on remote Actions checks or a workflow pin resolver.
    # Keep the parsed references visible in `artifacts`, but do not turn them
    # into a release coverage blocker.
    pending = [item["path"] for item in artifacts
               if item["state"] != "covered" and item["kind"] != "github-actions"]
    pending.extend(item["manifest"] for item in python_projects if item["state"] != "covered")
    if manifest is None:
        pending.append(str(MANIFEST_PATH))
    status = git_worktree_status(root)
    worktree_clean = status == "" if status is not None else None
    if worktree_clean is None:
        pending.append("git state unavailable")
    elif not worktree_clean:
        pending.append("dirty git worktree")
    toolchains = manifest.get("toolchains", {}) if manifest else {}
    adapters = manifest.get("adapters", {}) if manifest else {}
    supported_adapters = {"python": {"uv"}, "build_system": {"uv-dependency-group"}}
    discovered_adapter_kinds = {"python"} if python_projects else set()
    if any(project.get("declared_build_requirements") for project in python_projects):
        discovered_adapter_kinds.add("build_system")
    for artifact in artifacts:
        if artifact["kind"] in {"dockerfile", "compose", "devcontainer"}:
            discovered_adapter_kinds.add("containers")
            if artifact.get("os_package_declarations"):
                discovered_adapter_kinds.add("system_packages")
        elif artifact["kind"] == "unresolved-package-source":
            discovered_adapter_kinds.add("package_ecosystems")
        elif artifact["kind"] == "toolchain":
            discovered_adapter_kinds.add("toolchains")
    if manifest:
        for name in sorted(discovered_adapter_kinds):
            adapter = adapters.get(name)
            if not isinstance(adapter, str) or adapter not in supported_adapters.get(name, set()):
                pending.append(f"adapter:{name}")
    return {
        "schema_version": 1,
        "project_root": str(root),
        "project_name": manifest.get("project", {}).get("name") if manifest else root.name,
        "head_sha": _git(root, "rev-parse", "HEAD"),
        "worktree_clean": worktree_clean,
        "manifest": str(MANIFEST_PATH) if manifest else None,
        "policy_enabled": bool(manifest and manifest["policy"]["enabled"]),
        "toolchains": toolchains,
        "python_projects": python_projects,
        "artifacts": artifacts,
        "coverage": "complete" if manifest and not pending else "pending",
        "pending": sorted(set(pending)),
    }


def json_text(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
