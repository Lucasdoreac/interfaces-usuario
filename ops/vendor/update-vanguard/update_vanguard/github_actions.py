"""Resolve GitHub Actions to the newest stable patch in their current major.

The resolver reads only GitHub tag refs, pins a complete commit SHA, and never
edits the caller's workflow files. Unknown/untagged refs remain blockers.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .scratch import managed_scratch


class GitHubActionsResolutionError(RuntimeError):
    """A workflow reference or upstream tag set cannot be resolved safely."""


_USES = re.compile(
    r"^(?P<prefix>\s*(?:-\s*)?uses:\s*)(?P<target>[^\s#]+)(?P<tail>\s*(?:#.*)?)$"
)
_STABLE_TAG = re.compile(r"^v(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)$")
_MAJOR_TAG = re.compile(r"^v(?P<major>0|[1-9][0-9]*)$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class ActionUse:
    line_number: int
    repository: str
    subpath: str
    ref: str
    stable_hint: str | None
    prefix: str
    tail: str


def parse_action_use(line: str, line_number: int = 1) -> ActionUse | None:
    """Parse one remote `uses:` line; local and Docker actions return None."""
    match = _USES.fullmatch(line.rstrip("\r\n"))
    if not match:
        return None
    target = match.group("target")
    if target.startswith("./") or target.startswith("docker://") or "@" not in target:
        return None
    path, ref = target.rsplit("@", 1)
    parts = path.split("/")
    if (len(parts) < 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts)
            or not ref):
        return None
    tail = match.group("tail")
    comment = tail.partition("#")[2].strip()
    hint = comment.split()[0] if comment else None
    return ActionUse(
        line_number=line_number, repository="/".join(parts[:2]),
        subpath="/".join(parts[2:]), ref=ref, stable_hint=hint,
        prefix=match.group("prefix"), tail=tail,
    )


def _run_git(command: list[str], *, timeout_seconds: float) -> tuple[int, str, str]:
    """Run upstream git metadata lookup with an empty home and no credential helpers."""
    with managed_scratch("provider-run") as scratch_path:
        scratch = str(scratch_path)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": scratch,
            "TMPDIR": scratch,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }
        try:
            result = subprocess.run(command, cwd=scratch, env=env, capture_output=True,
                                    text=True, timeout=timeout_seconds, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitHubActionsResolutionError("GitHub tag lookup failed or timed out") from exc
    return result.returncode, result.stdout, result.stderr


def _release_tags(output: str, major: int) -> tuple[dict[str, str], str | None]:
    tag_objects: dict[str, str] = {}
    peeled: dict[str, str] = {}
    major_alias: str | None = None
    peeled_major_alias: str | None = None
    for raw in output.splitlines():
        fields = raw.split("\t", 1)
        if len(fields) != 2:
            continue
        sha, ref = fields
        if not _SHA.fullmatch(sha):
            continue
        if ref == f"refs/tags/v{major}":
            major_alias = sha
            continue
        if ref == f"refs/tags/v{major}^{{}}":
            peeled_major_alias = sha
            continue
        peeled_match = re.fullmatch(r"refs/tags/(v[^/]+)\^\{\}", ref)
        if peeled_match:
            peeled[peeled_match.group(1)] = sha
            continue
        tag_match = re.fullmatch(r"refs/tags/(v[^/]+)", ref)
        if tag_match:
            tag_objects[tag_match.group(1)] = sha

    stable: dict[str, tuple[tuple[int, int, int], str]] = {}
    for tag, tag_sha in tag_objects.items():
        match = _STABLE_TAG.fullmatch(tag)
        if not match or int(match.group("major")) != major:
            continue
        version = tuple(int(match.group(part)) for part in ("major", "minor", "patch"))
        stable[tag] = (version, peeled.get(tag, tag_sha))
    if not stable:
        raise GitHubActionsResolutionError(f"no stable v{major}.x.y tags found")
    if major_alias is None:
        raise GitHubActionsResolutionError(f"GitHub major alias v{major} is missing")
    return {tag: value[1] for tag, value in stable.items()}, peeled_major_alias or major_alias


def _major_and_current(use: ActionUse, tags: dict[str, str], alias_sha: str) -> tuple[int, str, str]:
    """Return major, current stable version, and the SHA currently selected."""
    if _SHA.fullmatch(use.ref):
        hint = use.stable_hint
        if hint is None or not _STABLE_TAG.fullmatch(hint):
            raise GitHubActionsResolutionError(
                f"pinned action {use.repository}@{use.ref} needs a stable vX.Y.Z annotation"
            )
        if hint not in tags or tags[hint] != use.ref:
            raise GitHubActionsResolutionError(
                f"pinned SHA for {use.repository} does not match its stable tag annotation"
            )
        major = int(_STABLE_TAG.fullmatch(hint).group("major"))
        return major, hint, use.ref
    major_match = _MAJOR_TAG.fullmatch(use.ref)
    stable_match = _STABLE_TAG.fullmatch(use.ref)
    if stable_match:
        major = int(stable_match.group("major"))
        if use.ref not in tags:
            raise GitHubActionsResolutionError(f"stable tag {use.ref} is absent upstream")
        return major, use.ref, tags[use.ref]
    if major_match:
        major = int(major_match.group("major"))
        current = [(tag, sha) for tag, sha in tags.items() if sha == alias_sha]
        if not current:
            raise GitHubActionsResolutionError(
                f"floating {use.repository}@{use.ref} does not resolve to a stable release tag"
            )
        current_tag = max(current, key=lambda item: tuple(
            int(part) for part in _STABLE_TAG.fullmatch(item[0]).groups()
        ))
        return major, current_tag[0], alias_sha
    raise GitHubActionsResolutionError(
        f"unsupported mutable or non-stable action ref {use.repository}@{use.ref}"
    )


def resolve_action_use(
    use: ActionUse,
    *,
    git_runner: Callable[..., tuple[int, str, str]] = _run_git,
    timeout_seconds: float = 30,
) -> dict[str, str | bool]:
    """Resolve one action within its declared major to a stable release SHA."""
    if use.ref.startswith("refs/") or "://" in use.ref:
        raise GitHubActionsResolutionError("action ref is not a valid tag or immutable SHA")
    # Find the currently selected major, then query only that exact repository.
    hint = use.stable_hint
    major_match = _MAJOR_TAG.fullmatch(use.ref)
    stable_match = _STABLE_TAG.fullmatch(use.ref)
    if _SHA.fullmatch(use.ref):
        if hint is None or not _STABLE_TAG.fullmatch(hint):
            raise GitHubActionsResolutionError("immutable action SHA requires a vX.Y.Z comment")
        major = int(_STABLE_TAG.fullmatch(hint).group("major"))
    elif major_match:
        major = int(major_match.group("major"))
    elif stable_match:
        major = int(stable_match.group("major"))
    else:
        raise GitHubActionsResolutionError(f"unsupported action ref: {use.ref}")

    url = f"https://github.com/{use.repository}.git"
    command = ["git", "ls-remote", "--tags", url]
    result = git_runner(command, timeout_seconds=timeout_seconds)
    if result[0] != 0:
        raise GitHubActionsResolutionError(f"could not read stable tags for {use.repository}")
    tags, alias_sha = _release_tags(result[1], major)
    current_major, current_version, current_sha = _major_and_current(use, tags, alias_sha)
    if current_major != major:
        raise GitHubActionsResolutionError("action major changed while resolving its release tags")
    latest = max(tags, key=lambda tag: tuple(
        int(part) for part in _STABLE_TAG.fullmatch(tag).groups()
    ))
    latest_sha = tags[latest]
    changed = current_sha != latest_sha or use.ref != latest_sha or use.stable_hint != latest
    return {
        "repository": use.repository,
        "subpath": use.subpath,
        "from_version": current_version.removeprefix("v"),
        "to_version": latest.removeprefix("v"),
        "from_sha": current_sha,
        "to_sha": latest_sha,
        "changed": changed,
        "replacement": f"{use.repository}{'/' + use.subpath if use.subpath else ''}@{latest_sha} # {latest}",
    }


def resolve_workflow_file(
    path: Path,
    *,
    git_runner: Callable[..., tuple[int, str, str]] = _run_git,
) -> dict[str, object]:
    """Build an in-memory candidate workflow; never write to the project checkout."""
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise GitHubActionsResolutionError("workflow file is unreadable") from exc
    lines = original.splitlines(keepends=True)
    changes: list[dict[str, object]] = []
    for index, line in enumerate(lines):
        use = parse_action_use(line, index + 1)
        if use is None:
            if re.match(r"^\s*(?:-\s*)?uses:\s*", line):
                raise GitHubActionsResolutionError(f"unsupported uses syntax at line {index + 1}")
            continue
        resolved = resolve_action_use(use, git_runner=git_runner)
        if resolved["changed"]:
            newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            lines[index] = f"{use.prefix}{resolved['replacement']}{newline}"
            changes.append({"line": index + 1, **resolved})
    return {
        "path": path.as_posix(),
        "changed": bool(changes),
        "content": "".join(lines),
        "changes": changes,
    }
