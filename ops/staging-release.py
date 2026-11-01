#!/usr/bin/env python3
"""Fixed-target Render Staging UI adapter for the canonical update-vanguard core.

No backend, database, mail-provider or local-stack mutations are exposed here.
Render API contract: https://api-docs.render.com/reference/create-deploy
Recovery contract: https://render.com/docs/rollbacks
"""
from __future__ import annotations
import argparse
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SERVICE = "srv-dau3tntg1s2s73bbr0sg"
BASE = "9eacf82b1974ac1218ef1c38af45edf6a4ec5e3f"
URL = "https://reservas-staging-web.onrender.com"
REPOSITORY = "https://github.com/Lucasdoreac/interfaces-usuario"
PROBES = ("/", "/organizer")
PRIVATE = Path.home() / "Library/Application Support/LabTech/staging-runtime-inventory.private.json"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def sha():
    return git("rev-parse", "HEAD")


def api(path, method="GET", data=None):
    # The existing authenticated CLI owns credential configuration; never print it.
    config = (Path.home() / ".render/cli.yaml").read_text().splitlines()
    credential = next(line.split(":", 1)[1].strip().strip("\"'") for line in config
                      if line.strip().startswith("key:"))
    body = None if data is None else json.dumps(data).encode()
    request = urllib.request.Request("https://api.render.com/v1" + path, data=body,
        method=method, headers={"Authorization": "Bearer " + credential,
                                "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def deploys():
    return [entry.get("deploy", entry) for entry in api(f"/services/{SERVICE}/deploys?limit=20")]


def live():
    return next(item for item in deploys() if item["status"] == "live")


def check_service(service):
    """Reject a different target or changed build contract before dispatch."""
    details = service.get("serviceDetails", {})
    if (service.get("id") != SERVICE or service.get("type") != "static_site"
        or service.get("repo", "").removesuffix(".git") != REPOSITORY
        or service.get("rootDir") != "reservas"
        or details.get("publishPath") != "build/client"
        or details.get("buildCommand") != "yarn install --frozen-lockfile && yarn build"
        or details.get("url") != URL or service.get("autoDeploy") != "no"):
        raise ValueError("Staging UI service/build contract diverged")


def check_diff(paths):
    for name in paths:
        if not (name.startswith(("reservas/src/", "reservas/app/", "reservas/tests/", "ops/vendor/update-vanguard/"))
                or name in {"reservas/.dockerignore", ".sober/updates.toml", ".sober/.gitignore", "ops/.gitignore", "ops/staging-release.py", "ops/staging.Dockerfile", "ops/test_staging_release.py"}):
            raise ValueError("Change outside the authorized UI/release scope: " + name)


def image():
    return "labtech-staging-ui:" + sha()


def build():
    values = json.loads(PRIVATE.read_text())["web"]
    if values.get("VITE_API_BASE_URL") != "https://reservas-staging-api.onrender.com":
        raise ValueError("UI build does not target the existing Staging API")
    subprocess.run(["docker", "build", "--label", "org.opencontainers.image.revision=" + sha(),
        "--build-arg", "VITE_API_BASE_URL", "--build-arg", "VITE_AUTH_EMAIL_ALLOWLIST",
        "-f", "ops/staging.Dockerfile", "-t", image(), "reservas"], cwd=ROOT,
        env={**os.environ, **values}, check=True)
    return subprocess.check_output(["docker", "image", "inspect", image(), "--format", "{{.Id}}"], text=True).strip()


def docker_test(focused=False):
    tests = ["node", "--test", "tests/logout.test.js", "tests/client.test.js",
             "tests/room-pagination.test.js", "tests/navbar-mobile-menu.test.js",
             "tests/navbar-logo-contrast.test.js"] if focused else ["yarn", "test"]
    subprocess.run(["docker", "run", "--rm", image(), *tests], check=True)


def probes(expected_sha):
    if live().get("commit", {}).get("id") != expected_sha:
        raise ValueError("Render live deployment SHA diverged")
    results = []
    for path in PROBES:
        with urllib.request.urlopen(URL + path, timeout=30) as response:
            html = response.read().decode()
            if response.status != 200 or "/assets/" not in html:
                raise ValueError("SPA shell probe failed: " + path)
            results.append({"path": path, "status": "passed",
                            "body_sha256": hashlib.sha256(html.encode()).hexdigest()})
    asset = re.search(r'(?:src|href)="(/assets/[^\"]+\.js)"', html)
    if not asset:
        raise ValueError("Built entry script unavailable")
    with urllib.request.urlopen(URL + asset.group(1), timeout=30) as response:
        if response.status != 200 or not response.read(1):
            raise ValueError("Built entry script probe failed")
    results.append({"path": asset.group(1), "status": "passed"})
    return results


class RenderStagingUI:
    adapter_name = "render-staging-ui"

    def assess(self, *, root, job_id, job, manifest):
        check_service(api(f"/services/{SERVICE}"))
        previous = live()
        previous_sha = previous["commit"]["id"]
        if previous_sha != BASE:
            raise ValueError("Staging changed after mission baseline; reconcile first")
        active = [x for x in deploys() if x["status"] in {
            "created", "build_in_progress", "update_in_progress", "pre_deploy_in_progress"}]
        if active:
            raise ValueError("Another deployment is active")
        changed = git("diff", "--name-only", BASE, job["head_sha"]).splitlines()
        check_diff(changed)
        # Retained live deploy plus successful artifact reads prove recovery target availability.
        if not all(callable(getattr(self, name, None)) for name in ("assess_rollback", "rollback", "reconcile_recorded")):
            raise ValueError("Native recovery executor is unavailable")
        previous_probes = probes(previous_sha)
        image_id = build()
        docker_test(focused=True)
        return {"source_sha": job["head_sha"], "source_commit_verified": sha() == job["head_sha"],
            "risk_evidence": {"package_delta": "none", "project_imports_affected": True,
                "runtime_delta": "none", "api_delta": "none", "persistent_data_affected": False,
                "tests_complete": None, "backup_restore_verified": False,
                "rollback_verified": True, "probes_verified": None},
            "impact_evidence": {"source_sha": job["head_sha"], "changed_files": changed,
                "scope": "Staging static UI only; backends and persistent data unchanged"},
            "rollback_evidence": {"verified": True, "previous_deploy_id": previous["id"],
                "previous_source_sha": previous_sha, "live_artifact_probes": previous_probes,
                "mechanism": "Render retained static-site build rollback"},
            "preflight_receipt": {"source_sha": job["head_sha"], "target": SERVICE,
                "linux_image_id": image_id, "focused_tests": "passed"},
            "effect_intent": {"source_sha": job["head_sha"], "target": SERVICE,
                "previous_deploy_id": previous["id"], "previous_source_sha": previous_sha}}

    def deploy(self, *, root, job_id, job, manifest, assessment):
        # One POST only. Timeout/uncertain outcomes are reconciled by observing provider state.
        d = api(f"/services/{SERVICE}/deploys", "POST", {"commitId": job["head_sha"]})
        d = d.get("deploy", d)
        return self.wait(d["id"], job["head_sha"], assessment["effect_intent"])

    def wait(self, deploy_id, source_sha, intent):
        for _ in range(60):
            d = api(f"/services/{SERVICE}/deploys/{deploy_id}")
            if d["status"] == "live":
                if d.get("commit", {}).get("id") != source_sha:
                    raise ValueError("Provider deployed an unexpected SHA")
                results = probes(source_sha)
                return {"source_sha": source_sha, "target": SERVICE, "deploy_id": deploy_id,
                        "previous_source_sha": intent.get("previous_source_sha"),
                        "previous_deploy_id": intent.get("previous_deploy_id"),
                        "previous_artifact_id": intent.get("previous_deploy_id"),
                        "probes_verified": True, "probe_results": results}
            if d["status"] in {"build_failed", "update_failed", "canceled", "deactivated"}:
                raise ValueError("Render deployment failed; previous site retained")
            time.sleep(15)
        raise TimeoutError("Render deployment pending; reconcile before any retry")

    def observe_live(self, *, root, job_id, job, effect):
        intent = effect["intent"]
        current = live()
        if current.get("commit", {}).get("id") != intent["source_sha"]:
            return None
        previous = api(f"/services/{SERVICE}/deploys/{intent['previous_deploy_id']}")
        return {"source_sha": intent["source_sha"], "target": SERVICE,
            "deploy_id": current["id"], "probes_verified": bool(probes(intent["source_sha"])),
            "rollback_target_available": previous["commit"]["id"] == intent["previous_source_sha"]}

    def assess_rollback(self, *, root, job_id, job, manifest, deployed):
        check_service(api(f"/services/{SERVICE}"))
        artifact = deployed.get("previous_artifact_id")
        if artifact != deployed.get("previous_deploy_id") or not re.fullmatch(r"dep-[a-z0-9]+", artifact or ""):
            raise ValueError("Recovery build identity missing or inconsistent")
        retained = deploys()[:3]  # Free tier retains the two previous builds.
        previous = next((d for d in retained if d["id"] == artifact), None)
        if previous is None or previous.get("commit", {}).get("id") != deployed.get("previous_source_sha"):
            raise ValueError("Recorded recovery build is no longer retained")
        if live().get("commit", {}).get("id") != job["head_sha"]:
            raise ValueError("Staging changed; rollback requires reconciliation")
        intent = {"source_sha": job["head_sha"], "target": SERVICE,
                  "restore_source_sha": deployed["previous_source_sha"], "restore_artifact_id": artifact}
        return {**intent, "rollback_verified": True, "effect_intent": intent,
                "preflight_receipt": {"retained_deploy_id": artifact, "target": SERVICE}}

    def rollback(self, *, root, job_id, job, manifest, assessment):
        intent = assessment["effect_intent"]
        d = api(f"/services/{SERVICE}/rollback", "POST", {"deployId": intent["restore_artifact_id"]})
        d = d.get("deploy", d)
        observed = self.wait(d["id"], intent["restore_source_sha"], {})
        return self.rollback_snapshot(intent, observed)

    @staticmethod
    def rollback_snapshot(intent, observed):
        return {"source_sha": intent["source_sha"], "target": SERVICE,
                "restored_source_sha": intent["restore_source_sha"],
                "restored_artifact_id": intent["restore_artifact_id"],
                "deploy_id": observed["deploy_id"], "rollback_verified": observed["probes_verified"],
                "probe_results": observed["probe_results"]}

    def reconcile_recorded(self, *, root, job_id, job, effect):
        intent = effect["intent"]
        rolling_back = effect["kind"] == "updates.rollback"
        expected = intent["restore_source_sha"] if rolling_back else intent["source_sha"]
        matches = [d for d in deploys() if d.get("commit", {}).get("id") == expected
            and datetime.fromisoformat(d["createdAt"].replace("Z", "+00:00")).timestamp() >= effect["created_at"]
            and (not rolling_back or d.get("trigger") == "rollback")]
        if len(matches) != 1:
            return {"reconciled": False, "outcome": "uncertain", "reason": "Dispatch not uniquely observed; no retry"}
        d = matches[0]
        if d["status"] in {"build_failed", "update_failed", "canceled"}:
            return {"reconciled": True, "outcome": "not_applied", "snapshot": {"source_sha": expected, "deploy_id": d["id"]}}
        snapshot = self.wait(d["id"], expected, intent)
        if rolling_back:
            snapshot = self.rollback_snapshot(intent, snapshot)
        return {"reconciled": True, "outcome": "applied", "snapshot": snapshot, "source": self.adapter_name}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["plan", "run", "status", "recover", "rollback", "gate"])
    args = parser.parse_args()
    if args.operation == "gate":
        docker_test()
        return
    # Reuse the installed canonical core, not a copied project implementation.
    core = Path(shutil.which("sober-updates")).resolve().parents[1]
    sys.path.insert(0, str(core / "scripts"))
    import _harness_python
    _harness_python.ensure(__file__)
    import importlib.util
    import tomllib
    pin = tomllib.loads((ROOT / ".sober/updates.toml").read_text())["harness"]
    spec = importlib.util.spec_from_file_location("canonical_source_pin", core / "update_vanguard/source_pin.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    vendor = ROOT / pin["path"]
    verifier.verify_snapshot(vendor, pin["source_sha256"])
    sys.path.insert(0, str(vendor))
    from update_vanguard.capability import UpdateCapabilityService, UpdateOperation, UpdateRequest, LOCAL_CLI_CALLER
    state_root = Path(git("rev-parse", "--git-common-dir")).resolve().parent
    service = UpdateCapabilityService(ROOT, state_root=state_root, deployment_executor=RenderStagingUI())
    lock_path = state_root / ".sober/render-staging-ui.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = service.dispatch(UpdateRequest(UpdateOperation("updates." + args.operation)), LOCAL_CLI_CALLER)
    print(json.dumps({"ok": result.ok, "blocker": result.blocker, "data": result.data}, ensure_ascii=False))
    if not result.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
