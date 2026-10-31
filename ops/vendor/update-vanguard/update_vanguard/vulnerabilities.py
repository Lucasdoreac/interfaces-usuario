"""PARADIGMA: per-project vulnerability track record from lockfiles and OSV, kept as history.

`scan` reads a project's lockfiles (PyPI from `uv.lock`, npm from `package-lock.json`),
asks OSV (https://osv.dev, `POST /v1/querybatch`) which known advisories affect the exact
locked versions, and merges the answer into a durable history per project:

    {"<ecosystem>:<package>:<advisory>": {"first_seen", "last_seen", "version",
                                           "resolved_at", "resolved_version"}}

An advisory that stops matching is marked resolved, never deleted, so the record shows
when each problem appeared, at which version, and when and by which version it went away.
Only package names, ecosystems and versions leave the machine. A failed or partial OSV
answer leaves the history untouched (NOT MEASURED), never "no vulnerabilities".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import re
import time
import tomllib
import urllib.request
from pathlib import Path
from typing import Callable

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
BATCH_SIZE = 500

Post = Callable[[str, dict], dict]


class NotMeasured(RuntimeError):
    """OSV could not be queried completely; the history must not change."""


def _post(url: str, body: dict) -> dict:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def locked_packages(repo: Path) -> list[tuple[str, str, str]]:
    """(ecosystem, name, version) for every registry package locked in the project."""
    packages: set[tuple[str, str, str]] = set()
    uv_lock = repo / "uv.lock"
    if uv_lock.is_file():
        for entry in tomllib.loads(uv_lock.read_text(encoding="utf-8")).get("package", []):
            if entry.get("version") and (entry.get("source") or {}).get("registry"):
                packages.add(("PyPI", entry["name"], entry["version"]))
    npm_lock = repo / "package-lock.json"
    if npm_lock.is_file():
        data = json.loads(npm_lock.read_text(encoding="utf-8"))
        for path, entry in (data.get("packages") or {}).items():
            name = entry.get("name") or path.rsplit("node_modules/", 1)[-1]
            if path and entry.get("version") and not entry.get("link"):
                packages.add(("npm", name, entry["version"]))
    return sorted(packages)


def query(packages: list[tuple[str, str, str]], *, post: Post = _post) -> dict[tuple[str, str, str], list[str]]:
    """Advisory IDs per package; raises NotMeasured on any incomplete answer."""
    found: dict[tuple[str, str, str], list[str]] = {}
    for start in range(0, len(packages), BATCH_SIZE):
        chunk = packages[start:start + BATCH_SIZE]
        try:
            answer = post(OSV_BATCH_URL, {"queries": [
                {"package": {"ecosystem": eco, "name": name}, "version": version}
                for eco, name, version in chunk]})
        except (OSError, ValueError) as exc:
            raise NotMeasured(f"OSV query failed: {type(exc).__name__}") from exc
        results = answer.get("results") if isinstance(answer, dict) else None
        if not isinstance(results, list) or len(results) != len(chunk):
            raise NotMeasured("OSV returned an incomplete batch")
        for package, result in zip(chunk, results):
            if (result or {}).get("next_page_token"):
                raise NotMeasured(f"OSV paginated results for {package[1]}; not followed")
            ids = sorted(v["id"] for v in (result or {}).get("vulns", []) if v.get("id"))
            if ids:
                found[package] = ids
    return found


def state_dir() -> Path:
    return Path(os.environ.get("HARNESS_VULN_STATE") or Path.home() / ".local" / "state" / "harness" / "vulnerabilities")


def _slug(identity: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", identity).strip("_") or "project"


def merge(history: dict, found: dict[tuple[str, str, str], list[str]], *, now: float) -> dict:
    """New advisories open, matching ones refresh, missing ones resolve; nothing is deleted."""
    current: dict[str, str] = {}
    for (eco, name, version), ids in found.items():
        for advisory in ids:
            current[f"{eco}:{name}:{advisory}"] = version
    merged = {key: dict(value) for key, value in history.items()}
    for key, version in current.items():
        entry = merged.get(key)
        if entry is None or entry.get("resolved_at") is not None:
            merged[key] = {"first_seen": now, "last_seen": now, "version": version,
                           "resolved_at": None, "resolved_version": None}
        else:
            entry.update(last_seen=now, version=version)
    for key, entry in merged.items():
        if key not in current and entry.get("resolved_at") is None:
            entry.update(resolved_at=now)
    return merged


def scan(repo: Path, identity: str, *, post: Post = _post, now: float | None = None) -> dict:
    """Scan one project and persist its history; returns a summary."""
    packages = locked_packages(repo)
    found = query(packages, post=post)
    path = state_dir() / f"{_slug(identity)}.json"
    history = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    resolved_versions = {(eco, name): version for eco, name, version in packages}
    stamp = time.time() if now is None else now
    merged = merge(history.get("advisories", {}), found, now=stamp)
    for key, entry in merged.items():
        if entry.get("resolved_at") == stamp:
            eco, name, _advisory = key.split(":", 2)
            entry["resolved_version"] = resolved_versions.get((eco, name))
    record = {"identity": identity, "repo": str(repo), "scanned_at": stamp,
              "packages": len(packages), "advisories": merged}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    open_ = {k: v for k, v in merged.items() if v.get("resolved_at") is None}
    return {"identity": identity, "packages": len(packages),
            "open": len(open_), "open_packages": len({k.rsplit(":", 1)[0] for k in open_}),
            "resolved_total": len(merged) - len(open_), "history": str(path)}


def registered_projects(registry: Path) -> list[tuple[str, Path]]:
    """Projects bound in the harness ledger registry: identity and repository root."""
    if not registry.is_file():
        return []
    bindings = json.loads(registry.read_text(encoding="utf-8"))
    return [(identity, Path(ledger).parent.parent) for identity, ledger in sorted(bindings.items())
            if isinstance(ledger, str)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness-vuln-scan", description=__doc__)
    parser.add_argument("--registry", type=Path,
                        default=Path(os.environ.get("HARNESS_LEDGER_REGISTRY")
                                     or Path.home() / ".local/state/harness/ledgers.json"),
                        help="projects to scan (default: the harness ledger registry)")
    parser.add_argument("--repo", type=Path, action="append",
                        help="scan only this repository (repeatable); identity is its path")
    args = parser.parse_args(argv)
    targets = ([(str(repo.resolve()), repo.resolve()) for repo in args.repo] if args.repo
               else registered_projects(args.registry))
    status = 0
    for identity, repo in targets:
        try:
            print(json.dumps(scan(repo, identity), sort_keys=True))
        except NotMeasured as exc:
            print(json.dumps({"identity": identity, "not_measured": str(exc)}), file=sys.stderr)
            status = 2
    return status
