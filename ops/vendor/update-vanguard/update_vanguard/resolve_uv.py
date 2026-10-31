"""Resolve a complete uv lock in an isolated archive without installing packages."""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import shutil
import signal
import subprocess
import tarfile
import tomllib
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from .manifest import ManifestError, load_manifest
from .scratch import managed_scratch
from .source_pin import snapshot_digest, verify_snapshot
from .versioning import is_stable_release


class ResolutionError(RuntimeError):
    pass


def _pinned_harness_source(repository: Path) -> dict[str, str] | None:
    """Validate the one supported local source: the immutable harness vendor."""
    try:
        manifest = load_manifest(repository)
    except ManifestError as exc:
        raise ResolutionError(f"invalid project manifest: {exc}") from exc
    pin = manifest.get("harness") if manifest else None
    if pin is None:
        return None
    relative = PurePosixPath(pin["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ResolutionError("pinned harness path escapes the project")
    cursor = repository
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ResolutionError("pinned harness path cannot traverse symlinks")
    vendor = cursor.resolve(strict=True)
    if not vendor.is_relative_to(repository):
        raise ResolutionError("pinned harness path escapes the project")
    try:
        verify_snapshot(vendor, pin["source_sha256"])
        package_config = tomllib.loads((vendor / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValueError) as exc:
        raise ResolutionError(f"pinned harness source is invalid: {exc}") from exc
    project = package_config.get("project", {})
    if project.get("name") != pin["package"] or not isinstance(project.get("version"), str):
        raise ResolutionError("pinned harness distribution metadata does not match its manifest")
    return {
        "name": pin["package"],
        "path": relative.as_posix(),
        "version": project["version"],
        "source_sha256": pin["source_sha256"],
    }


def _validate_harness_lock(lock_data: dict[str, Any], pin: dict[str, str] | None) -> None:
    if pin is None:
        return
    matches = [
        package for package in lock_data.get("package", [])
        if re.sub(r"[-_.]+", "-", str(package.get("name", ""))).lower() == pin["name"]
    ]
    if (len(matches) != 1 or matches[0].get("version") != pin["version"]
            or matches[0].get("source") != {"directory": pin["path"]}):
        raise ResolutionError("uv.lock does not pin the canonical harness vendor path and version")


def _command(command: list[str], cwd: Path, env: dict[str, str], timeout: float) -> tuple[int, str, str]:
    if os.name != "posix":
        raise ResolutionError("isolated resolver process-group cancellation is not supported on this host")
    process = subprocess.Popen(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        raise TimeoutError(f"resolver timed out after {timeout:g}s; process group collected") from exc
    return process.returncode, stdout, stderr


def _extract_archive(archive: bytes, destination: Path) -> None:
    with tarfile.open(fileobj=BytesIO(archive), mode="r:") as bundle:
        for member in bundle.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not name.parts:
                raise ResolutionError("git archive contains an unsafe path")
            target = destination.joinpath(*name.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ResolutionError("git archive contains a link or special file; resolver refuses it")
            target.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise ResolutionError("git archive entry could not be read")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)


def resolve_uv_project(
    repository: Path,
    project_manifest: str,
    head_sha: str,
    *,
    timeout_seconds: float = 300,
    uv_executable: str | None = None,
    runner: Callable[[list[str], Path, dict[str, str], float], tuple[int, str, str]] = _command,
) -> dict[str, object]:
    """Return a complete lock candidate; never edits the source worktree or installs deps."""
    repository = repository.resolve()
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repository,
                            capture_output=True, text=True, check=True).stdout
    current_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    if current_sha != head_sha:
        raise ResolutionError("project HEAD changed since inventory")
    if status:
        raise ResolutionError("dirty worktree blocks dependency resolution")
    if (repository / ".gitmodules").exists():
        raise ResolutionError("git submodules are not supported by the isolated archive resolver")
    manifest_relative = PurePosixPath(project_manifest)
    if manifest_relative.is_absolute() or ".." in manifest_relative.parts:
        raise ResolutionError("project manifest path escapes repository")
    project_relative = manifest_relative.parent
    source_project = repository.joinpath(*project_relative.parts)
    if source_project.resolve() != repository.joinpath(*project_relative.parts) or not source_project.resolve().is_relative_to(repository):
        raise ResolutionError("project manifest traverses a symlink or escapes the repository")
    source_pyproject = source_project / "pyproject.toml"
    source_lock = source_project / "uv.lock"
    if not source_pyproject.is_file() or not source_lock.is_file():
        raise ResolutionError("uv project requires both tracked pyproject.toml and uv.lock")
    if source_pyproject.is_symlink() or source_lock.is_symlink():
        raise ResolutionError("symlinked manifests are not supported")
    try:
        pyproject = tomllib.loads(source_pyproject.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ResolutionError(f"invalid pyproject.toml: {exc}") from exc
    project = pyproject.get("project", {})
    if not isinstance(project, dict) or project.get("dynamic"):
        raise ResolutionError("dynamic project metadata may execute the project build backend")
    project_name = project.get("name")
    if not isinstance(project_name, str) or not project_name.strip():
        raise ResolutionError("a static project.name is required to identify the root editable lock entry")
    normalized_project_name = re.sub(r"[-_.]+", "-", project_name).lower()
    tool_config = pyproject.get("tool", {})
    uv_config = tool_config.get("uv", {}) if isinstance(tool_config, dict) else None
    if (not isinstance(uv_config, dict) or any(key in uv_config for key in
            ("index", "index-url", "extra-index-url", "find-links", "no-index"))):
        raise ResolutionError("custom indexes or source overrides need a reviewed project adapter")
    uv_sources = uv_config.get("sources", {})
    if not isinstance(uv_sources, dict):
        raise ResolutionError("uv.sources must be a table")
    pinned_source = None
    if uv_sources:
        pinned_source = _pinned_harness_source(repository)
        expected_source = (
            {pinned_source["name"]: {"path": pinned_source["path"], "editable": False}}
            if pinned_source else None
        )
        if uv_sources != expected_source:
            raise ResolutionError("only the digest-verified canonical harness path is supported in uv.sources")
    declared = project.get("dependencies", [])
    optional = project.get("optional-dependencies", {})
    groups = pyproject.get("dependency-groups", {})
    build = pyproject.get("build-system", {})
    if (not isinstance(declared, list) or not isinstance(optional, dict) or not isinstance(groups, dict)
            or not isinstance(build, dict) or any(not isinstance(values, list) for values in [*optional.values(), *groups.values()])):
        raise ResolutionError("unsupported dependency declaration structure")
    declarations = [*declared, *(dep for values in optional.values() for dep in values),
                    *(dep for values in groups.values() for dep in values), *build.get("requires", [])]
    if any(not isinstance(dep, str) for dep in declarations):
        raise ResolutionError("unsupported dependency declaration format")
    if any(" @ " in dep for dep in declarations):
        raise ResolutionError("direct URL or unsupported dependency declarations need a reviewed source adapter")
    direct_names_declared = {
        re.sub(r"[-_.]+", "-", re.split(r"[ <>=!~;\[]", dep, maxsplit=1)[0]).lower()
        for dep in declarations
    }
    if pinned_source and pinned_source["name"] not in direct_names_declared:
        raise ResolutionError("pinned harness source is not a declared project dependency")
    uv_executable = uv_executable or shutil.which("uv")
    if not uv_executable:
        raise ResolutionError("uv executable is unavailable")

    old_lock = source_lock.read_text(encoding="utf-8")
    old_hash = hashlib.sha256(old_lock.encode()).hexdigest()
    try:
        old_lock_data = tomllib.loads(old_lock)
    except tomllib.TOMLDecodeError as exc:
        raise ResolutionError(f"invalid uv.lock: {exc}") from exc
    _validate_harness_lock(old_lock_data, pinned_source)
    for package in old_lock_data.get("package", []):
        source = package.get("source", {})
        if not isinstance(source, dict):
            raise ResolutionError("unsupported uv.lock source record")
        package_name = re.sub(r"[-_.]+", "-", str(package.get("name", ""))).lower()
        if source.get("editable") == "." and package_name == normalized_project_name and set(source) == {"editable"}:
            continue
        if pinned_source and package_name == pinned_source["name"]:
            if (package.get("version") != pinned_source["version"]
                    or source != {"directory": pinned_source["path"]}):
                raise ResolutionError("uv.lock harness source differs from its verified project pin")
            continue
        registry = source.get("registry")
        if registry and registry not in {"https://pypi.org/simple", "https://pypi.org/pypi"}:
            raise ResolutionError("non-public package registry needs an explicit project adapter")
        if any(key in source for key in ("git", "url", "directory", "editable", "archive")):
            raise ResolutionError("VCS, URL, and local-path dependencies need an explicit project adapter")
    with managed_scratch("provider-run") as scratch:
        home = scratch / "home"
        cache = scratch / "cache"
        project_root = scratch / "repo"
        home.mkdir()
        project_root.mkdir()
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
               "TMPDIR": str(scratch), "UV_CACHE_DIR": str(cache), "UV_NO_CONFIG": "1",
               "UV_NO_BUILD": "1", "UV_PYTHON_DOWNLOADS": "never", "UV_PRERELEASE": "if-necessary"}
        archive_process = subprocess.run(["git", "archive", "--format=tar", head_sha], cwd=repository,
                                         capture_output=True, timeout=30, check=False)
        if archive_process.returncode != 0:
            raise ResolutionError("could not snapshot the requested Git SHA")
        _extract_archive(archive_process.stdout, project_root)
        if pinned_source:
            archived_source = _pinned_harness_source(project_root)
            if archived_source != pinned_source:
                raise ResolutionError("archived harness pin differs from the inspected project snapshot")
        lock_to_update = project_root.joinpath(*manifest_relative.parent.parts, "uv.lock")
        if not lock_to_update.is_file():
            raise ResolutionError("tracked uv.lock is absent from the requested Git snapshot")
        command = [uv_executable, "--directory", str(lock_to_update.parent), "lock", "--upgrade",
                   "--prerelease", "if-necessary", "--no-build"]
        try:
            return_code, stdout, stderr = runner(command, project_root, env, timeout_seconds)
        except TimeoutError:
            raise
        if return_code != 0:
            detail = (stderr or stdout).strip()[-2000:]
            raise ResolutionError(f"uv could not resolve a complete stable lock: {detail}")
        new_lock = lock_to_update.read_text(encoding="utf-8")
        new_hash = hashlib.sha256(new_lock.encode()).hexdigest()
        old_data = old_lock_data
        new_data = tomllib.loads(new_lock)
        _validate_harness_lock(new_data, pinned_source)
        def package_versions(lock_data: dict[str, Any]) -> dict[str, list[str]]:
            versions: dict[str, set[str]] = {}
            for item in lock_data.get("package", []):
                name = re.sub(r"[-_.]+", "-", item["name"]).lower()
                versions.setdefault(name, set()).add(item["version"])
            return {name: sorted(values) for name, values in versions.items()}

        old_packages = package_versions(old_data)
        new_packages = package_versions(new_data)
        direct_names = {
            re.sub(r"[-_.]+", "-", re.split(r"[ <>=!~;\[]", dep, maxsplit=1)[0]).lower()
            for dep in declarations
        }
        missing_direct = sorted(direct_names - set(new_packages))
        if missing_direct:
            raise ResolutionError(f"resolved lock omits direct project requirements: {', '.join(missing_direct)}")
        prerelease_direct = sorted(
            f"{name}=={version}"
            for name, versions in new_packages.items() if name in direct_names
            for version in versions if not is_stable_release(version)
        )
        if prerelease_direct:
            raise ResolutionError(
                "stable channel refuses pre-release or unsupported direct requirements: "
                + ", ".join(prerelease_direct)
            )
        if set(old_packages) != set(new_packages):
            added = sorted(set(new_packages) - set(old_packages))
            removed = sorted(set(old_packages) - set(new_packages))
        else:
            added, removed = [], []
        changes = [{"name": name, "from": old_packages.get(name), "to": new_packages.get(name)}
                   for name in sorted(set(old_packages) | set(new_packages))
                   if old_packages.get(name) != new_packages.get(name)]
        return {
            "project_manifest": project_manifest,
            "base_sha": head_sha,
            "files": [lock_to_update.relative_to(project_root).as_posix()] if new_hash != old_hash else [],
            "old_lock_sha256": old_hash,
            "new_lock_sha256": new_hash,
            "package_changes": changes,
            "added_packages": added,
            "removed_packages": removed,
            "changed_package_count": len(changes),
            "lock_diff": "".join(difflib.unified_diff(old_lock.splitlines(keepends=True), new_lock.splitlines(keepends=True),
                                                        fromfile="uv.lock (base)", tofile="uv.lock (candidate)")),
            "candidate_lock": new_lock,
            "resolver": "uv",
            "prerelease_policy": "stable-direct; if-necessary transitive",
            "execution": "metadata-and-lock-resolution-only; no package installation",
        }
