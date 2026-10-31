"""Conservative, exact-SHA source impact evidence for canonical plans."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from .manifest import load_manifest

_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_PERSISTENCE_PATH = re.compile(
    r"(^|/)(?:migrations?|alembic|schema|initdb)(?:/|$)|(?:ledger|database|repository)\.py$|\.(?:sql|sqlite|db)$",
    re.IGNORECASE,
)
_RUNTIME_PATH = re.compile(
    r"(^|/)(?:Dockerfile(?:\.[^/]*)?|docker-compose(?:\.[^/]*)?\.(?:yml|yaml)|"
    r"compose(?:\.[^/]*)?\.(?:yml|yaml)|Makefile|ops/[^/]+\.(?:sh|bash)|"
    r"(?:app|src|scripts|update_vanguard)/.+\.(?:py|js|jsx|ts|tsx|mjs|cjs|go|rs|java|kt|rb|php|c|cc|cpp|h|hpp|swift))$",
    re.IGNORECASE,
)
_KNOWN_NON_RUNTIME = re.compile(
    r"(^|/)(?:README(?:\.[^/]*)?|CHANGELOG(?:\.[^/]*)?|LICENSE(?:\.[^/]*)?|"
    r"[^/]+\.(?:md|rst|txt|adoc|png|jpe?g|svg|gif|pdf))$",
    re.IGNORECASE,
)
_DEPENDENCY_MANIFEST = {
    "pyproject.toml", "uv.lock", "requirements.txt", "package.json", "package-lock.json",
    "pnpm-lock.yaml", "yarn.lock", "cargo.toml", "cargo.lock", "go.mod", "go.sum",
    "gemfile", "gemfile.lock", "composer.json", "composer.lock", "pom.xml", "build.gradle",
    "build.gradle.kts",
}
_PINNED_REQUIREMENT = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([0-9]+\.[0-9]+\.[0-9]+)$"
)


def _normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _semver_delta(before_value: object, after_value: object) -> str | None:
    before_match = _SEMVER.fullmatch(str(before_value))
    after_match = _SEMVER.fullmatch(str(after_value))
    if not before_match or not after_match:
        return None
    before = tuple(map(int, before_match.groups()))
    after = tuple(map(int, after_match.groups()))
    if after == before:
        return "none"
    if after < before:
        return None
    if after[0] > before[0]:
        return "major"
    if after[1] > before[1]:
        return "minor"
    if after[2] > before[2]:
        return "patch"
    return None


def _single_local_package_delta(root: Path, base: str, head: str,
                                old: dict[str, Any], new: dict[str, Any]) -> str | None:
    """Classify one exact local-package pin bump when both manifests and locks prove it."""
    try:
        old_project, new_project = old.get("project", {}), new.get("project", {})
        if (old_project.get("name") != new_project.get("name")
                or old_project.get("version") != new_project.get("version")
                or old_project.get("optional-dependencies", {}) != new_project.get("optional-dependencies", {})
                or old.get("build-system", {}) != new.get("build-system", {})
                or old.get("dependency-groups", {}) != new.get("dependency-groups", {})):
            return None
        old_dependencies = old_project.get("dependencies", [])
        new_dependencies = new_project.get("dependencies", [])
        if not isinstance(old_dependencies, list) or not isinstance(new_dependencies, list):
            return None

        from collections import Counter

        old_counts, new_counts = Counter(old_dependencies), Counter(new_dependencies)
        removed = list((old_counts - new_counts).elements())
        added = list((new_counts - old_counts).elements())
        if len(removed) != 1 or len(added) != 1:
            return None
        old_requirement = _PINNED_REQUIREMENT.fullmatch(removed[0])
        new_requirement = _PINNED_REQUIREMENT.fullmatch(added[0])
        if (old_requirement is None or new_requirement is None
                or _normalized_name(old_requirement.group(1))
                != _normalized_name(new_requirement.group(1))):
            return None
        package = _normalized_name(old_requirement.group(1))
        old_sources = old.get("tool", {}).get("uv", {}).get("sources", {})
        new_sources = new.get("tool", {}).get("uv", {}).get("sources", {})
        if old_sources != new_sources:
            return None
        source = next((value for key, value in new_sources.items()
                       if _normalized_name(key) == package), None)
        if (not isinstance(source, dict) or not isinstance(source.get("path"), str)
                or source.get("editable", False) is not False
                or source.get("git") or source.get("url")):
            return None
        relative = Path(source["path"])
        if relative.is_absolute() or ".." in relative.parts:
            return None
        package_pyproject = (relative / "pyproject.toml").as_posix()
        old_local = tomllib.loads(_git(root, "show", f"{base}:{package_pyproject}"))
        new_local = tomllib.loads(_git(root, "show", f"{head}:{package_pyproject}"))
        old_local_project = old_local.get("project", {})
        new_local_project = new_local.get("project", {})
        old_version, new_version = old_local_project.get("version"), new_local_project.get("version")
        if (_normalized_name(str(old_local_project.get("name", ""))) != package
                or _normalized_name(str(new_local_project.get("name", ""))) != package
                or old_version != old_requirement.group(2)
                or new_version != new_requirement.group(2)):
            return None

        old_lock = tomllib.loads(_git(root, "show", f"{base}:uv.lock"))
        new_lock = tomllib.loads(_git(root, "show", f"{head}:uv.lock"))
        if ({key: value for key, value in old_lock.items() if key != "package"}
                != {key: value for key, value in new_lock.items() if key != "package"}):
            return None
        old_packages, new_packages = old_lock.get("package"), new_lock.get("package")
        if not isinstance(old_packages, list) or not isinstance(new_packages, list):
            return None
        root_name = _normalized_name(str(old_project.get("name", "")))

        def unchanged_lock_packages(packages: list[object]) -> list[object] | None:
            if any(not isinstance(item, dict) for item in packages):
                return None
            return [item for item in packages
                    if _normalized_name(str(item.get("name", ""))) not in {root_name, package}]

        old_other, new_other = unchanged_lock_packages(old_packages), unchanged_lock_packages(new_packages)
        if old_other is None or new_other is None or old_other != new_other:
            return None

        def root_lock_record(packages: list[object]) -> dict[str, Any] | None:
            matches = [item for item in packages if isinstance(item, dict)
                       and _normalized_name(str(item.get("name", ""))) == root_name]
            if len(matches) != 1:
                return None
            record = dict(matches[0])
            dependencies = record.pop("dependencies", [])
            record.pop("metadata", None)
            if not isinstance(dependencies, list):
                return None
            record["dependencies"] = sorted(
                _normalized_name(str(item.get("name", "")))
                for item in dependencies if isinstance(item, dict)
            )
            if len(record["dependencies"]) != len(dependencies):
                return None
            return record

        if root_lock_record(old_packages) != root_lock_record(new_packages):
            return None

        def pinned_local_version(packages: list[object]) -> str | None:
            matches = [item for item in packages if isinstance(item, dict)
                       and _normalized_name(str(item.get("name", ""))) == package
                       and item.get("source", {}).get("directory") == source["path"]]
            return matches[0].get("version") if len(matches) == 1 else None

        if (pinned_local_version(old_packages) != old_version
                or pinned_local_version(new_packages) != new_version):
            return None
        return _semver_delta(old_version, new_version)
    except (KeyError, OSError, subprocess.SubprocessError, tomllib.TOMLDecodeError, ValueError):
        return None


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=False, capture_output=True, text=True,
    )
    if result.returncode:
        raise ValueError("source impact could not verify the requested Git evidence")
    return result.stdout.strip()


def _public_api(root: Path, revision: str, path: str) -> dict[str, tuple[str, str]]:
    if not path.endswith(".py"):
        return {}
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"], cwd=root, check=False, capture_output=True,
    )
    if result.returncode:
        return {}
    try:
        tree = ast.parse(result.stdout, filename=path)
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise ValueError("changed Python source has no parseable public API") from exc
    exported: set[str] | None = None
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
                try:
                    value = ast.literal_eval(node.value) if node.value is not None else None
                except (ValueError, TypeError):
                    raise ValueError("public API export list is not a literal")
                if not isinstance(value, (list, tuple)) or any(not isinstance(name, str) for name in value):
                    raise ValueError("public API export list is malformed")
                exported = set(value)
                break
    # Modules without an explicit export contract do not advertise their
    # implementation symbols as stable public API.
    if exported is None:
        return {}
    symbols: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in exported):
            signature = ast.dump(node.args, include_attributes=False)
            returns = ast.dump(node.returns, include_attributes=False) if node.returns else ""
            symbols[node.name] = ("callable", f"{signature}->{returns}")
        elif isinstance(node, ast.ClassDef) and node.name in exported:
            members = []
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and not member.name.startswith("_"):
                    members.append((member.name, ast.dump(member.args, include_attributes=False)))
            symbols[node.name] = ("class", repr(sorted(members)))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in exported and target.id != "__all__":
                    value = node.value
                    # Public policy text changes are versioned content, not API removal.
                    category = "policy-text" if target.id in {"SYSTEM_PROMPT", "PROJECT_INSTRUCTIONS"} else "constant"
                    shape = type(value).__name__ if value is not None else "annotation-only"
                    symbols[target.id] = (category, shape)
    return symbols


def _has_blob(root: Path, revision: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}:{path}"], cwd=root,
        check=False, capture_output=True,
    )
    return result.returncode == 0


def _uv_lock_delta(root: Path, base: str, head: str) -> str | None:
    """Compare exact uv package records; opaque graph or source changes stay UNKNOWN."""
    try:
        base_has_lock = _has_blob(root, base, "uv.lock")
        head_has_lock = _has_blob(root, head, "uv.lock")
        if not base_has_lock and head_has_lock:
            # Introducing the first lock freezes a graph but gives no prior
            # resolved graph to compare; treat it as a structural package change.
            return "major"
        if base_has_lock and not head_has_lock:
            return None
        if not base_has_lock and not head_has_lock:
            return "none"
        old_lock = tomllib.loads(_git(root, "show", f"{base}:uv.lock"))
        new_lock = tomllib.loads(_git(root, "show", f"{head}:uv.lock"))
        if ({key: value for key, value in old_lock.items() if key != "package"}
                != {key: value for key, value in new_lock.items() if key != "package"}):
            return None
        old_packages, new_packages = old_lock.get("package"), new_lock.get("package")
        if (not isinstance(old_packages, list) or not isinstance(new_packages, list)
                or any(not isinstance(item, dict) for item in [*old_packages, *new_packages])):
            return None

        def grouped(packages: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
            output: dict[str, list[dict[str, Any]]] = {}
            for package in packages:
                name, version = package.get("name"), package.get("version")
                if not isinstance(name, str) or not isinstance(version, str):
                    raise TypeError("uv lock package identity is incomplete")
                output.setdefault(_normalized_name(name), []).append(package)
            return output

        old_by_name, new_by_name = grouped(old_packages), grouped(new_packages)
        if set(old_by_name) != set(new_by_name):
            return "major"
        changes: list[dict[str, Any]] = []
        for name in sorted(old_by_name):
            before, after = old_by_name[name], new_by_name[name]
            source_before = sorted(json.dumps(item.get("source"), sort_keys=True) for item in before)
            source_after = sorted(json.dumps(item.get("source"), sort_keys=True) for item in after)
            if source_before != source_after:
                return None

            def shape(package: dict[str, Any]) -> str:
                return json.dumps({key: value for key, value in package.items() if key != "version"},
                                  sort_keys=True, separators=(",", ":"))

            old_shapes = sorted(shape(item) for item in before)
            new_shapes = sorted(shape(item) for item in after)
            if old_shapes != new_shapes:
                # Dependency/source metadata changed alongside package data;
                # HIGH is conservative for recognized graph structure changes.
                return "major"
            old_versions = sorted(str(item["version"]) for item in before)
            new_versions = sorted(str(item["version"]) for item in after)
            if old_versions != new_versions:
                changes.append({"name": name, "from": old_versions, "to": new_versions})
        from .versioning import package_delta

        return package_delta(changes)[0]
    except (KeyError, OSError, subprocess.SubprocessError, tomllib.TOMLDecodeError, TypeError, ValueError):
        return None


def assess_source_impact(root: Path, head_sha: str | None = None) -> dict[str, Any]:
    """Derive impact dimensions from a clean diff; unknown evidence stays null.

    This is a detector, not a risk waiver. Persistent paths are conservatively
    marked affected, and unsupported dependency or API changes remain unknown.
    """
    root = root.resolve(strict=True)
    try:
        head = head_sha or _git(root, "rev-parse", "HEAD")
        if re.fullmatch(r"[0-9a-f]{40}", head) is None or _git(root, "rev-parse", "HEAD") != head:
            raise ValueError("source impact SHA is not the current HEAD")
        if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
            raise ValueError("source impact requires a clean worktree")
        base = _git(root, "merge-base", "origin/main", head)
        if re.fullmatch(r"[0-9a-f]{40}", base) is None:
            raise ValueError("source impact base is unavailable")
        paths = [item for item in _git(root, "diff", "--name-only", "--no-renames", f"{base}...{head}").splitlines()
                 if item]
        if not paths:
            # A release on main compares its latest commit with its first parent.
            parents = _git(root, "rev-list", "--parents", "-n", "1", head).split()
            if len(parents) < 2:
                raise ValueError("source impact baseline is unavailable")
            base = parents[1]
            paths = [item for item in _git(root, "diff", "--name-only", "--no-renames", f"{base}...{head}").splitlines()
                     if item]
        if not paths:
            raise ValueError("source impact diff is empty")

        python_paths = [path for path in paths if path.endswith(".py")]
        runtime_paths = [path for path in paths if path.endswith(".py") or _RUNTIME_PATH.search(path)
                         or Path(path).name.lower() in _DEPENDENCY_MANIFEST]
        unknown_paths = [path for path in paths
                         if not path.endswith(".py") and not _RUNTIME_PATH.search(path)
                         and Path(path).name.lower() not in _DEPENDENCY_MANIFEST
                         and not _KNOWN_NON_RUNTIME.search(path)]
        runtime_delta = "patch" if runtime_paths else ("none" if not unknown_paths else None)
        manifest = load_manifest(root)
        configured_persistent_paths = set(
            manifest.get("impact", {}).get("persistent_data_paths", [])
            if isinstance(manifest, dict) else []
        )
        persistent = any(
            _PERSISTENCE_PATH.search(path) or path in configured_persistent_paths
            for path in paths
        )
        if any("docker-compose" in Path(path).name.lower()
               or Path(path).name.lower().startswith("compose")
               or "dockerfile" in Path(path).name.lower()
               or ("backup" in Path(path).name.lower() and path.startswith("ops/"))
               for path in paths):
            # Container topology and backup/restore scripts can affect persisted
            # data even when the filename does not use a database convention.
            persistent = True
        project_imports = True if runtime_paths else (False if not unknown_paths else None)
        package_delta: str | None = "none"
        dependency_changed = any(Path(path).name.lower() in _DEPENDENCY_MANIFEST for path in paths)
        if dependency_changed:
            # Only Python manifests have a complete parser and semantic
            # comparator here. Other ecosystems remain UNKNOWN until their
            # resolver is implemented; treating their changes as "none" is unsafe.
            if any(Path(path).name.lower() not in {"pyproject.toml", "uv.lock", "requirements.txt"}
                   for path in paths if Path(path).name.lower() in _DEPENDENCY_MANIFEST):
                package_delta = None
            unsupported_manifests = any(
                Path(path).name.lower() not in {"pyproject.toml", "uv.lock", "requirements.txt"}
                for path in paths if Path(path).name.lower() in _DEPENDENCY_MANIFEST
            )
            uv_lock_changed = any(Path(path).name == "uv.lock" for path in paths)
            pyproject_paths = [path for path in paths if Path(path).name == "pyproject.toml"]
            if unsupported_manifests:
                package_delta = None
            elif uv_lock_changed:
                package_delta = _uv_lock_delta(root, base, head)
            if pyproject_paths and not unsupported_manifests:
                old = tomllib.loads(_git(root, "show", f"{base}:pyproject.toml"))
                new = tomllib.loads(_git(root, "show", f"{head}:pyproject.toml"))
                old_project, new_project = old.get("project", {}), new.get("project", {})
                dependency_fields = ("dependencies", "optional-dependencies")
                old_dependencies = {key: old_project.get(key) for key in dependency_fields}
                new_dependencies = {key: new_project.get(key) for key in dependency_fields}
                old_build = old.get("build-system", {}).get("requires")
                new_build = new.get("build-system", {}).get("requires")
                declared_dependencies_changed = (
                    old_dependencies != new_dependencies or old_build != new_build
                )
                if declared_dependencies_changed and not uv_lock_changed:
                    local_delta = _single_local_package_delta(root, base, head, old, new)
                    if local_delta is not None:
                        package_delta = local_delta
                    else:
                        package_delta = None
                if not uv_lock_changed and not declared_dependencies_changed:
                    old_version, new_version = old_project.get("version"), new_project.get("version")
                    old_match = _SEMVER.fullmatch(str(old_version))
                    new_match = _SEMVER.fullmatch(str(new_version))
                    if not old_match or not new_match:
                        package_delta = None
                    else:
                        before = tuple(map(int, old_match.groups()))
                        after = tuple(map(int, new_match.groups()))
                        if after == before:
                            package_delta = "none"
                        elif after < before:
                            package_delta = None
                        elif after[0] > before[0]:
                            package_delta = "major"
                        elif after[1] > before[1]:
                            package_delta = "minor"
                        elif after[2] > before[2]:
                            package_delta = "patch"
                        else:
                            package_delta = None

        api_delta: str | None = "none"
        for path in python_paths:
            old_exists = _has_blob(root, base, path)
            new_exists = _has_blob(root, head, path)
            if old_exists and not new_exists:
                api_delta = "breaking"
                break
            old_api = _public_api(root, base, path)
            new_api = _public_api(root, head, path)
            if set(old_api) - set(new_api):
                api_delta = "breaking"
                break
            if any(old_api[name][1] != new_api[name][1]
                   for name in set(old_api) & set(new_api)
                   if old_api[name][0] in {"callable", "class"}):
                api_delta = "breaking"
                break
            if old_api != new_api:
                api_delta = "compatible"

        evidence = {
            "package_delta": package_delta,
            "project_imports_affected": project_imports,
            "runtime_delta": runtime_delta,
            "api_delta": api_delta,
            "persistent_data_affected": persistent,
        }
        digest_material = "\0".join([base, head, *sorted(paths)]).encode("utf-8")
        return {
            "schema_version": 1, "base_sha": base, "source_sha": head,
            "changed_paths": sorted(paths),
            "changed_paths_sha256": hashlib.sha256(digest_material).hexdigest(),
            "risk_evidence": evidence,
        }
    except (OSError, subprocess.SubprocessError, UnicodeError, tomllib.TOMLDecodeError, ValueError):
        return {
            "schema_version": 1, "source_sha": head_sha, "status": "unknown",
            "reason": "source impact evidence is incomplete; risk dimensions remain unknown",
            "risk_evidence": {
                "package_delta": None, "project_imports_affected": None,
                "runtime_delta": None, "api_delta": None, "persistent_data_affected": None,
            },
        }
