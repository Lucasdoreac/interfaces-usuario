"""Two-phase, bounded Docker adapter for a uv project and workflow candidates."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import select
import shlex
import shutil
import subprocess
import tarfile
import time
from typing import Any, Callable

from .ledger import Ledger


class ExecutorError(RuntimeError):
    pass


class ExecutorUncertain(ExecutorError):
    pass


DockerRun = Callable[..., subprocess.CompletedProcess[str]]


def _safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ExecutorError("project path escapes the candidate snapshot")
    return path


def _assert_no_symlink_path(root: Path, relative: PurePosixPath) -> Path:
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ExecutorError("candidate path must not traverse symlinks")
    if not cursor.resolve().is_relative_to(root.resolve()):
        raise ExecutorError("candidate path escapes its root")
    return cursor


class DockerUvExecutor:
    """Install locked wheels without secrets, then run gates offline and read-only.

    The project code is never run during the network-enabled install phase: source
    builds are disabled. Gate containers have no network, credentials, host home,
    or Docker socket. Each phase has a durable deterministic container name so a
    caller can cancel or reconcile it after interruption.
    """

    LABEL = "org.sober.update-vanguard.job"
    SCRATCH_DIR = "update-vanguard-scratch"
    OUTPUT_LIMIT = 16000

    def __init__(self, *, docker: str = "docker", run: DockerRun | None = None,
                 poll_seconds: float = 1.0):
        self.docker = docker
        self.run = run or subprocess.run
        self.poll_seconds = poll_seconds

    def _call(self, args: list[str], timeout: float = 30) -> subprocess.CompletedProcess[str]:
        try:
            return self.run([self.docker, *args], text=True, capture_output=True,
                            timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ExecutorUncertain(f"Docker command outcome is uncertain: {args[0]}") from exc

    def _git(self, args: list[str], timeout: float = 30) -> subprocess.CompletedProcess[str]:
        try:
            return self.run(["git", *args], text=True, capture_output=True,
                            timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ExecutorUncertain(f"Git snapshot command outcome is uncertain: {args[0]}") from exc

    def _inspect(self, name: str) -> dict[str, Any] | None:
        result = self._call(["container", "inspect", name])
        if result.returncode != 0:
            listing = self._call(["container", "ls", "--all", "--format", "{{.Names}}",
                                  "--filter", f"name=^{name}$"])
            if listing.returncode != 0:
                raise ExecutorUncertain("container inspection failed and absence could not be reconciled")
            if listing.stdout.strip():
                raise ExecutorUncertain("container exists but Docker inspection failed")
            return None
        try:
            records = json.loads(result.stdout)
            record = records[0]
            return {
                "id": record["Id"],
                "running": bool(record["State"]["Running"]),
                "status": str(record["State"].get("Status", "unknown")),
                "exit_code": int(record["State"].get("ExitCode", -1)),
                "pid": int(record["State"].get("Pid", 0)),
                "error": str(record["State"].get("Error", "")),
                "networks": set((record.get("NetworkSettings", {}).get("Networks") or {}).keys()),
                "job_id": (record["Config"].get("Labels") or {}).get(self.LABEL),
            }
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ExecutorUncertain("Docker returned an unrecognizable container receipt") from exc

    def _verify_container(self, name: str, job_id: str) -> dict[str, Any] | None:
        record = self._inspect(name)
        if record is not None and record["job_id"] != job_id:
            raise ExecutorError("deterministic container name belongs to another job")
        return record

    def _disconnect_network(self, name: str, job_id: str) -> None:
        record = self._verify_container(name, job_id)
        if record is None or not record["running"]:
            raise ExecutorUncertain("setup container is not running while fencing network access")
        if "bridge" in record["networks"]:
            disconnected = self._call(["network", "disconnect", "bridge", name], timeout=30)
            record = self._verify_container(name, job_id)
            if disconnected.returncode != 0 and record is not None and "bridge" in record["networks"]:
                raise ExecutorUncertain("setup network disconnection is ambiguous")
        if record is None or "bridge" in record["networks"]:
            raise ExecutorUncertain("setup container still has network access")

    def _logs(self, name: str) -> str:
        result = self._call(["container", "logs", name], timeout=60)
        return (result.stdout + result.stderr)[-self.OUTPUT_LIMIT:]

    def _scratch(self, root: Path, job_id: str) -> Path:
        sober = root / ".sober"
        parent = sober / self.SCRATCH_DIR
        if sober.is_symlink() or parent.is_symlink():
            raise ExecutorError("managed scratch path must not follow symlinks")
        parent.mkdir(parents=True, exist_ok=True)
        target = parent / job_id
        if target.is_symlink() or not target.resolve().is_relative_to(parent.resolve()):
            raise ExecutorError("managed scratch path escapes its root")
        marker = target / ".update-vanguard-owner.json"
        if target.exists():
            if marker.is_symlink() or not marker.is_file():
                raise ExecutorError("existing scratch has no valid ownership marker; preserving it")
            try:
                info = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ExecutorError("existing scratch ownership marker is invalid; preserving it") from exc
            if info != {"job_id": job_id, "project_root": str(root)}:
                raise ExecutorError("existing scratch marker belongs to another job")
            os.chmod(target, 0o755)
            return target
        target.mkdir(mode=0o700)
        descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"job_id": job_id, "project_root": str(root)}, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(target, 0o755)
        return target

    def _snapshot(self, root: Path, job_id: str, head_sha: str,
                  candidates: list[dict[str, Any]],
                  primary_candidate: dict[str, Any]) -> tuple[Path, Path, str]:
        scratch = self._scratch(root, job_id)
        repo = scratch / "repo"
        if repo.is_symlink():
            raise ExecutorError("snapshot path must not be a symlink")
        created_snapshot = not repo.exists()
        if created_snapshot:
            clone = self._git(["-c", "protocol.file.allow=always", "clone", "--no-local", "--quiet",
                               "--no-checkout", str(root), str(repo)], timeout=300)
            if clone.returncode != 0:
                raise ExecutorError(f"could not snapshot candidate source: {clone.stderr[-1000:]}")
            checkout = self._git(["-C", str(repo), "checkout", "--quiet", "--detach", head_sha], timeout=120)
            if checkout.returncode != 0:
                raise ExecutorError("requested source SHA is unavailable in snapshot clone")
        else:
            observed = self._git(["-C", str(repo), "rev-parse", "HEAD"])
            if observed.returncode != 0 or observed.stdout.strip() != head_sha:
                raise ExecutorError("existing scratch snapshot does not match the job SHA")
        manifest_path = _safe_relative(str(primary_candidate["project_manifest"]))
        project_rel = PurePosixPath(*manifest_path.parts[:-1])
        if not project_rel.parts:
            project_rel = PurePosixPath(".")
        project_dir = _assert_no_symlink_path(repo, project_rel) if str(project_rel) != "." else repo
        overlays: dict[str, tuple[Path, bytes, str, bool]] = {}
        primary_project = str(project_rel)
        for item in candidates:
            if "project_manifest" in item:
                files = item.get("files")
                if not isinstance(files, list):
                    raise ExecutorError("uv candidate file list is invalid")
                if not files:
                    continue
                if len(files) != 1:
                    raise ExecutorError("one uv candidate must change exactly one lock file")
                manifest_rel = _safe_relative(str(item["project_manifest"]))
                item_project = PurePosixPath(*manifest_rel.parts[:-1])
                if not item_project.parts:
                    item_project = PurePosixPath(".")
                if str(item_project) != primary_project:
                    raise ExecutorError("changed uv locks outside the configured test project are unsupported")
                lock_rel = _safe_relative(str(files[0]))
                if len(lock_rel.parts) != 1 or lock_rel.name != "uv.lock":
                    raise ExecutorError("uv candidates may update only their project's uv.lock")
                target_rel = lock_rel if primary_project == "." else item_project / lock_rel
                source_rel = _safe_relative(str(item["candidate_path"]))
                expected_sha = item.get("new_lock_sha256")
            elif "path" in item:
                if item.get("changed") is not True:
                    continue
                target_rel = _safe_relative(str(item["path"]))
                if (len(target_rel.parts) < 3 or target_rel.parts[:2] != (".github", "workflows")
                        or target_rel.suffix not in {".yml", ".yaml"}):
                    raise ExecutorError("non-uv candidates may update only GitHub workflow files")
                source_rel = _safe_relative(str(item.get("candidate_path", "")))
                expected_sha = item.get("candidate_sha256")
            else:
                raise ExecutorError("candidate type is unsupported by docker-uv")
            source_path = _assert_no_symlink_path(root, source_rel)
            target_path = _assert_no_symlink_path(repo, target_rel)
            if not source_path.is_file() or not target_path.is_file():
                raise ExecutorError("candidate source or tracked snapshot target is missing")
            contents = source_path.read_bytes()
            actual_sha = hashlib.sha256(contents).hexdigest()
            if not isinstance(expected_sha, str) or actual_sha != expected_sha:
                raise ExecutorError("candidate file digest does not match the plan receipt")
            key = target_rel.as_posix()
            if key in overlays:
                raise ExecutorError("multiple candidates target the same snapshot file")
            base = self._git(["-C", str(repo), "show", f"{head_sha}:{key}"], timeout=30)
            if base.returncode != 0:
                raise ExecutorError("candidate target is not a tracked file at the planned source SHA")
            overlays[key] = (target_path, contents, actual_sha, base.stdout.encode() != contents)

        if created_snapshot:
            for target_path, contents, _digest, changed_from_base in overlays.values():
                if changed_from_base:
                    target_path.write_bytes(contents)
        else:
            status = self._git(["-C", str(repo), "status", "--porcelain=v1", "-z",
                                "--untracked-files=all"], timeout=30)
            if status.returncode != 0:
                raise ExecutorUncertain("existing candidate snapshot status could not be read")
            changed_paths = {entry[3:] for entry in status.stdout.split("\0") if len(entry) >= 4}
            expected_changes = {key for key, entry in overlays.items() if entry[3]}
            if changed_paths != expected_changes:
                raise ExecutorError("existing scratch contains unexpected changes; preserving it")
            for key, (target_path, _contents, expected_sha, _changed_from_base) in overlays.items():
                if hashlib.sha256(target_path.read_bytes()).hexdigest() != expected_sha:
                    raise ExecutorError(f"existing scratch candidate differs at {key}; preserving it")
        os.chmod(repo, 0o755)
        os.chmod(project_dir, 0o755)
        venv = repo.parent / "venv"
        if venv.is_symlink() or (venv.exists() and not venv.is_dir()):
            raise ExecutorError("managed venv path is not a regular directory")
        return repo, venv, str(project_rel)

    def _export_venv(self, *, container: str, venv: Path, job_id: str,
                     image_id: str, lock_sha: str, execution: dict[str, Any]) -> None:
        marker = venv / ".update-vanguard-venv.json"
        expected = {"job_id": job_id, "image_id": image_id, "lock_sha256": lock_sha}
        if venv.exists():
            if marker.is_symlink() or not marker.is_file():
                raise ExecutorUncertain("existing exported venv lacks its ownership receipt; preserving it")
            try:
                if json.loads(marker.read_text(encoding="utf-8")) != expected:
                    raise ExecutorError("exported venv receipt does not match this job")
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ExecutorUncertain("exported venv receipt is unreadable") from exc
            return
        self._copy_container_venv(container=container, venv=venv, execution=execution)
        if venv.is_symlink() or not venv.is_dir():
            raise ExecutorUncertain("bounded venv export did not complete; reconcile before retry")
        python = venv / "bin" / "python3"
        config = venv / "pyvenv.cfg"
        python_link = venv / "bin" / "python"
        if not (python.is_symlink() or python.is_file()) or not (python_link.is_symlink() or python_link.is_file()) or not config.is_file():
            try:
                entries = sorted(item.name for item in (venv / "bin").iterdir())
            except OSError:
                entries = []
            raise ExecutorError(
                "exported venv is incomplete "
                f"(python3_link={python.is_symlink()}, python3_file={python.is_file()}, "
                f"python_link={python_link.is_symlink()}, python_file={python_link.is_file()}, "
                f"config_file={config.is_file()}, bin_entries={entries[:20]})"
            )
        size = 0
        for directory, subdirs, files in os.walk(venv, followlinks=False):
            for name in (*subdirs, *files):
                size += (Path(directory) / name).lstat().st_size
        if size > execution.get("venv_mb", 1024) * 1024 * 1024:
            raise ExecutorError("exported venv exceeds its configured storage cap")
        descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(expected, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())

    def _copy_container_venv(self, *, container: str, venv: Path,
                             execution: dict[str, Any]) -> None:
        """Stream a bounded tar from the live container; Docker cp omits tmpfs mounts."""
        archive_path = venv.parent / "venv-export.tar"
        if archive_path.exists() or archive_path.is_symlink():
            raise ExecutorUncertain("existing venv export artifact is ambiguous; preserving it")
        script = ("import sys,tarfile; "
                  "tarfile.open(fileobj=sys.stdout.buffer, mode='w|').add('/venv', arcname='.')")
        command = [self.docker, "exec", container, "python3", "-c", script]
        process = None
        byte_count = 0
        max_bytes = execution.get("venv_mb", 1024) * 1024 * 1024 + 64 * 1024 * 1024
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
            assert process.stdout is not None
            with archive_path.open("xb") as archive:
                deadline = time.monotonic() + 120
                fd = process.stdout.fileno()
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ExecutorUncertain("container venv export timed out; reconcile before retry")
                    readable, _, _ = select.select([fd], [], [], min(remaining, 1.0))
                    if not readable:
                        if process.poll() is not None:
                            continue
                        continue
                    chunk = os.read(fd, 64 * 1024)
                    if not chunk:
                        break
                    byte_count += len(chunk)
                    if byte_count > max_bytes:
                        raise ExecutorError("streamed venv archive exceeded its bounded export size")
                    archive.write(chunk)
                archive.flush()
                os.fsync(archive.fileno())
            return_code = process.wait(timeout=10)
            stderr = process.stderr.read(4000).decode("utf-8", errors="replace") if process.stderr else ""
            if return_code != 0:
                raise ExecutorUncertain(f"container venv export failed: {stderr[-1000:]}")
            venv.mkdir(mode=0o700)
            total_size = 0
            count = 0
            with tarfile.open(archive_path, mode="r:") as bundle:
                for member in bundle:
                    count += 1
                    if count > 100_000:
                        raise ExecutorError("venv archive contains too many filesystem entries")
                    relative = PurePosixPath(member.name)
                    if relative.is_absolute() or ".." in relative.parts:
                        raise ExecutorError("venv archive contains a path escape")
                    parts = tuple(part for part in relative.parts if part not in {"", "."})
                    if not parts:
                        continue
                    total_size += member.size if member.isfile() else 0
                    if total_size > execution.get("venv_mb", 1024) * 1024 * 1024:
                        raise ExecutorError("exported venv exceeds its configured storage cap")
                    target = venv.joinpath(*parts)
                    cursor = venv
                    for part in parts[:-1]:
                        cursor /= part
                        if cursor.is_symlink() or (cursor.exists() and not cursor.is_dir()):
                            raise ExecutorError("venv archive traverses a non-directory or symlink")
                        cursor.mkdir(exist_ok=True)
                    if member.isdir():
                        target.mkdir(exist_ok=True)
                    elif member.issym():
                        link = member.linkname
                        escapes = False
                        if not link or "\x00" in link:
                            escapes = True
                        elif link.startswith("/"):
                            link_path = PurePosixPath(link)
                            name = link_path.name
                            allowed_python = (name in {"python", "python3"}
                                              or (name.startswith("python3.") and name[8:].isdigit()))
                            escapes = not (link_path.parent == PurePosixPath("/usr/local/bin")
                                           and allowed_python)
                        else:
                            depth = len(parts[:-1])
                            for component in PurePosixPath(link).parts:
                                if component == "..":
                                    depth -= 1
                                    if depth < 1:
                                        escapes = True
                                        break
                                elif component not in {"", "."}:
                                    depth += 1
                        if escapes:
                            raise ExecutorError("venv archive contains an unsafe symbolic link")
                        os.symlink(link, target)
                    elif member.isfile():
                        source = bundle.extractfile(member)
                        if source is None:
                            raise ExecutorError("venv archive regular file has no content")
                        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
                        with os.fdopen(descriptor, "wb") as output:
                            shutil.copyfileobj(source, output, length=64 * 1024)
                        os.chmod(target, 0o755 if member.mode & 0o111 else 0o644)
                    else:
                        raise ExecutorError("venv archive contains a hardlink or special file")
        except (OSError, tarfile.TarError, subprocess.TimeoutExpired) as exc:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            raise ExecutorUncertain("bounded container venv stream could not be reconciled") from exc
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            if process is not None:
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
            if archive_path.exists() and not archive_path.is_symlink():
                archive_path.unlink()

    @staticmethod
    def _resource_flags(execution: dict[str, Any]) -> list[str]:
        return ["--memory", f"{execution.get('memory_mb', 2048)}m",
                "--cpus", str(execution.get("cpus", 2)), "--pids-limit", "128",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "1000:1000"]

    def _container_args(self, *, name: str, job_id: str, phase: str, image_id: str,
                        execution: dict[str, Any], repo: Path, venv: Path,
                        project_dir: str, command: list[str]) -> list[str]:
        network = "bridge" if phase == "install" else "none"
        cwd = "/repo" if project_dir == "." else f"/repo/{project_dir}"
        if "," in str(repo):
            raise ExecutorError("Docker bind paths containing commas are not supported")
        env = {
            "HOME": "/tmp/home", "UV_PROJECT_ENVIRONMENT": "/venv",
            "UV_CACHE_DIR": "/tmp/uvcache", "UV_NO_CONFIG": "1",
            "UV_NO_BUILD": "1", "UV_PYTHON_DOWNLOADS": "never",
            "UV_PRERELEASE": "if-necessary", "VIRTUAL_ENV": "/venv",
            "PATH": "/venv/bin:/usr/local/bin:/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": cwd,
        }
        args = ["container", "create", "--name", name, "--label", f"{self.LABEL}={job_id}",
                "--network", network, *self._resource_flags(execution), "--read-only",
                "--tmpfs", "/tmp:rw,exec,size=1g", "--tmpfs", "/home/ci:rw,size=256m",
                "--mount", f"type=bind,src={repo},dst=/repo,readonly",
                "--workdir", cwd]
        if phase == "install":
            args += ["--tmpfs", f"/venv:rw,exec,size={execution.get('venv_mb', 1024)}m"]
        else:
            if "," in str(venv):
                raise ExecutorError("Docker venv paths containing commas are not supported")
            args += ["--mount", f"type=bind,src={venv},dst=/venv,readonly"]
        for key, value in env.items():
            args += ["--env", f"{key}={value}"]
        args.append(image_id)
        if phase == "install":
            sync = ["uv", "sync", "--frozen", "--no-install-project", "--no-build"]
            for group in execution.get("uv_groups", []):
                sync += ["--group", group]
            for extra in execution.get("uv_extras", []):
                sync += ["--extra", extra]
            script = (f"{' '.join(shlex.quote(part) for part in sync)}; result=$?; "
                      "printf '%s\\n' \"$result\" > /tmp/update-vanguard-install.exit; "
                      "exec sleep infinity")
            args += ["sh", "-lc", script]
        else:
            args += command
        return args

    def _run_phase(self, *, job_id: str, phase: str, command_index: int | None,
                   image_id: str, execution: dict[str, Any], repo: Path,
                   venv: Path, project_dir: str, ledger: Ledger, receipt: dict[str, Any],
                   command: list[str] | None = None) -> tuple[int, str]:
        suffix = "install" if phase == "install" else f"gate-{command_index}"
        name = f"uvg-{job_id[:18]}-{suffix}"
        current = {"name": name, "phase": phase, "command_index": command_index,
                   "command": list(command or []) if phase == "gate" else [
                       "uv", "sync", "--frozen", "--no-install-project", "--no-build"
                   ], "started_at": time.time(), "status": "creating"}
        execution_receipt = receipt.setdefault("execution", {})
        if execution_receipt.get("current"):
            raise ExecutorUncertain("another execution phase is already recorded; recover it first")
        execution_receipt.update({"status": "running", "adapter": "docker-uv", "current": current})
        ledger.record(job_id, f"isolated {phase} phase prepared", receipt)
        created = self._call(self._container_args(
            name=name, job_id=job_id, phase=phase, image_id=image_id, execution=execution,
            repo=repo, venv=venv, project_dir=project_dir,
            command=[] if phase == "install" else list(command or [])
        ), timeout=60)
        observed = self._verify_container(name, job_id)
        if created.returncode != 0:
            if observed is not None:
                raise ExecutorUncertain("container creation returned an error but the named container exists")
            current["status"] = "create_failed"
            current["detail"] = created.stderr[-1000:]
            execution_receipt.update({"status": "failed", "current": None})
            ledger.record(job_id, f"isolated {phase} container creation failed", receipt)
            raise ExecutorError(f"could not create isolated {phase} container")
        if observed is None:
            raise ExecutorUncertain("container creation was reported but container cannot be inspected")
        current.update({"status": "running", "container_id": observed["id"]})
        ledger.record(job_id, f"isolated {phase} container created", receipt)
        started = self._call(["container", "start", name], timeout=60)
        if started.returncode != 0:
            observed = self._verify_container(name, job_id)
            if observed is None or observed["running"] or observed["status"] != "exited":
                raise ExecutorUncertain("container start result is ambiguous; recover before retry")
        deadline = time.monotonic() + execution.get("timeout_seconds", 1800)
        install_result: int | None = None
        while True:
            latest = ledger.get(job_id)
            latest_execution = (latest or {}).get("receipt", {}).get("execution", {})
            if latest_execution.get("status") == "cancelled":
                return 130, "cancelled by operator"
            observed = self._verify_container(name, job_id)
            if observed is None:
                raise ExecutorUncertain("active phase container disappeared; no retry was attempted")
            if phase == "install" and observed["running"]:
                marker = self._call(["container", "exec", name, "sh", "-c",
                                     "cat /tmp/update-vanguard-install.exit"], timeout=15)
                if marker.returncode == 0 and marker.stdout.strip().isdigit():
                    install_result = int(marker.stdout.strip())
                    break
            if not observed["running"]:
                if observed["status"] != "exited":
                    raise ExecutorUncertain("container is not running but has no verified exit state")
                break
            if time.monotonic() >= deadline:
                stop = self._call(["container", "stop", "--time", "5", name], timeout=15)
                after = self._verify_container(name, job_id)
                if stop.returncode != 0 and (after is None or after["running"]):
                    raise ExecutorUncertain("execution timed out; container cancellation is unverified")
                if after is None or after["running"] or after["status"] != "exited":
                    raise ExecutorUncertain("timed-out container exit could not be verified")
                break
            time.sleep(self.poll_seconds)
        if phase == "install" and install_result == 0:
            self._disconnect_network(name, job_id)
            self._export_venv(container=name, venv=venv, job_id=job_id, image_id=image_id,
                              lock_sha=str(receipt["execution"]["candidate_lock_sha256"]),
                              execution=execution)
            current["install_exit_code"] = 0
            current["network_fenced"] = True
            ledger.record(job_id, "locked environment exported after setup network fencing", receipt)
            stop = self._call(["container", "stop", "--time", "5", name], timeout=15)
            stopped = self._verify_container(name, job_id)
            if stop.returncode != 0 and (stopped is None or stopped["running"]):
                raise ExecutorUncertain("installed venv was exported but setup container shutdown is unverified")
            if stopped is None or stopped["running"] or stopped["status"] != "exited":
                raise ExecutorUncertain("setup container shutdown is unverified")
        elif phase == "install" and install_result is not None:
            self._call(["container", "stop", "--time", "5", name], timeout=15)
        output = self._logs(name)
        observed = self._verify_container(name, job_id)
        if observed is None or observed["running"]:
            raise ExecutorUncertain("phase result is not terminal")
        exit_code = install_result if phase == "install" and install_result is not None else observed["exit_code"]
        execution_receipt = receipt.setdefault("execution", {})
        current = execution_receipt.get("current") or current
        current.update({"status": "completed" if exit_code == 0 else "failed",
                        "exit_code": exit_code, "output": output})
        execution_receipt.setdefault("phases", []).append(dict(current))
        execution_receipt["current"] = None
        execution_receipt["status"] = "running" if exit_code == 0 else "failed"
        ledger.record(job_id, f"isolated {phase} phase {'passed' if exit_code == 0 else 'failed'}", receipt)
        removed = self._call(["container", "rm", name], timeout=60)
        if removed.returncode != 0:
            raise ExecutorUncertain("terminal container result was recorded but cleanup is unverified")
        return exit_code, output

    def run_candidate(self, *, root: Path, job_id: str, job: dict[str, Any],
                      manifest: dict[str, Any], ledger: Ledger) -> dict[str, Any]:
        policy = manifest["policy"]
        if not policy["enabled"]:
            raise ExecutorError("updates capability is disabled by the project manifest")
        execution = manifest.get("execution", {})
        if execution.get("adapter") != "docker-uv":
            raise ExecutorError("docker-uv execution adapter is not configured")
        image_id = execution["image_id"]
        image = self._call(["image", "inspect", "--format", "{{.Id}}", image_id], timeout=30)
        if image.returncode != 0 or image.stdout.strip() != image_id:
            raise ExecutorError("pinned executor image is not present locally; implicit pulls are forbidden")
        current_head = self._git(["-C", str(root), "rev-parse", "HEAD"], timeout=30)
        status = self._git(["-C", str(root), "status", "--porcelain", "--untracked-files=all"], timeout=30)
        if current_head.returncode != 0 or current_head.stdout.strip() != job["head_sha"] or status.stdout.strip():
            raise ExecutorError("source HEAD must still match the plan and the worktree must be clean")
        candidates = job["receipt"]["plan"].get("candidates", [])
        if (not isinstance(candidates, list) or not candidates
                or any(not isinstance(item, dict) for item in candidates)):
            raise ExecutorError("docker-uv requires at least one resolved project candidate")
        uv_candidates = [item for item in candidates if "project_manifest" in item]
        if not uv_candidates:
            raise ExecutorError("docker-uv requires a configured Python project candidate")
        project_config = str(execution.get("project", "."))
        project_rel = PurePosixPath(project_config)
        if project_rel.is_absolute() or ".." in project_rel.parts:
            raise ExecutorError("execution project escapes the source snapshot")
        matching = []
        for item in uv_candidates:
            manifest_rel = _safe_relative(str(item.get("project_manifest", "")))
            candidate_project = PurePosixPath(*manifest_rel.parts[:-1]) or PurePosixPath(".")
            if str(candidate_project) == str(project_rel):
                matching.append(item)
        if len(matching) != 1:
            raise ExecutorError("execution.project must select exactly one uv project candidate")
        primary_candidate = matching[0]
        for item in uv_candidates:
            files = item.get("files")
            if not isinstance(files, list):
                raise ExecutorError("uv candidate file list is invalid")
            manifest_rel = _safe_relative(str(item.get("project_manifest", "")))
            candidate_project = PurePosixPath(*manifest_rel.parts[:-1]) or PurePosixPath(".")
            if files and candidate_project != project_rel:
                raise ExecutorError("docker-uv cannot claim tests for changed locks outside execution.project")
        repo, venv, project_dir = self._snapshot(
            root, job_id, job["head_sha"], candidates, primary_candidate
        )
        commands = manifest.get("gates", {}).get("commands", [])
        parsed_commands = [shlex.split(command, posix=True) for command in commands]
        if not parsed_commands or any(not command for command in parsed_commands):
            raise ExecutorError("at least one non-empty gate command is required")
        execution_receipt = job["receipt"].setdefault("execution", {})
        execution_receipt.setdefault("adapter_config", {
            "image_id": image_id, "uv_groups": execution.get("uv_groups", []),
            "uv_extras": execution.get("uv_extras", []),
            "timeout_seconds": execution.get("timeout_seconds", 1800),
            "memory_mb": execution.get("memory_mb", 2048),
            "venv_mb": execution.get("venv_mb", 1024),
            "cpus": execution.get("cpus", 2),
        })
        candidate_lock_sha = str(primary_candidate.get("new_lock_sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", candidate_lock_sha):
            raise ExecutorError("selected uv project candidate lacks a valid lock digest")
        previous_candidate_sha = execution_receipt.get("candidate_lock_sha256")
        if previous_candidate_sha is not None and previous_candidate_sha != candidate_lock_sha:
            raise ExecutorError("existing execution receipt belongs to a different lock candidate")
        execution_receipt["candidate_lock_sha256"] = candidate_lock_sha
        candidate_files = []
        for item in candidates:
            if item.get("project_manifest") and item.get("files"):
                manifest_rel = _safe_relative(str(item["project_manifest"]))
                project = PurePosixPath(*manifest_rel.parts[:-1])
                target = str(project / item["files"][0]) if project.parts else str(item["files"][0])
                candidate_files.append({"path": target, "sha256": item.get("new_lock_sha256")})
            elif item.get("path") and item.get("changed") is True:
                candidate_files.append({"path": item["path"], "sha256": item.get("candidate_sha256")})
        candidate_set_sha = hashlib.sha256(json.dumps(
            sorted(candidate_files, key=lambda item: item["path"]),
            sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        previous_set_sha = execution_receipt.get("candidate_set_sha256")
        if previous_set_sha is not None and previous_set_sha != candidate_set_sha:
            raise ExecutorError("existing execution receipt belongs to a different candidate set")
        execution_receipt["candidate_set_sha256"] = candidate_set_sha
        execution_receipt["candidate_files"] = sorted(candidate_files, key=lambda item: item["path"])
        execution_receipt.setdefault("declared_gate_commands", parsed_commands)
        if execution_receipt.get("current"):
            raise ExecutorUncertain("job already has an active or unreconciled phase")
        if execution_receipt.get("status") in {"failed", "cancelled"}:
            raise ExecutorError("previous isolated test failed or was cancelled; create a fresh plan before retry")
        phases = execution_receipt.setdefault("phases", [])
        if not any(phase.get("phase") == "install" for phase in phases):
            code, _ = self._run_phase(job_id=job_id, phase="install", command_index=None,
                                      image_id=image_id, execution=execution, repo=repo,
                                      venv=venv, project_dir=project_dir,
                                      ledger=ledger, receipt=job["receipt"])
            if code != 0:
                latest = ledger.get(job_id)
                if (latest or {}).get("receipt", {}).get("execution", {}).get("status") == "cancelled":
                    return (latest or {})["receipt"]["execution"]
                execution_receipt["status"] = "failed"
                execution_receipt["scratch_cleanup"] = self._cleanup_scratch(root, job_id)
                ledger.record(job_id, "uv locked wheel install failed", job["receipt"])
                return job["receipt"]["execution"]
        completed = {phase["command_index"] for phase in execution_receipt.get("phases", [])
                     if phase.get("phase") == "gate" and phase.get("exit_code") == 0}
        for index, command in enumerate(parsed_commands):
            if index in completed:
                continue
            code, _ = self._run_phase(job_id=job_id, phase="gate", command_index=index,
                                      image_id=image_id, execution=execution, repo=repo,
                                      venv=venv, project_dir=project_dir,
                                      ledger=ledger, receipt=job["receipt"],
                                      command=command)
            if code != 0:
                latest = ledger.get(job_id)
                if (latest or {}).get("receipt", {}).get("execution", {}).get("status") == "cancelled":
                    return (latest or {})["receipt"]["execution"]
                execution_receipt["status"] = "failed"
                execution_receipt["scratch_cleanup"] = self._cleanup_scratch(root, job_id)
                ledger.record(job_id, f"gate {index + 1} failed", job["receipt"])
                return job["receipt"]["execution"]
        execution_receipt["status"] = "passed"
        execution_receipt["completed_at"] = time.time()
        execution_receipt["source_sha"] = job["head_sha"]
        execution_receipt["candidate_lock_sha256"] = candidate_lock_sha
        execution_receipt["scratch_cleanup"] = self._cleanup_scratch(root, job_id)
        ledger.record(job_id, "all declared isolated gates passed", job["receipt"])
        return execution_receipt

    def _cleanup_scratch(self, root: Path, job_id: str) -> str:
        result = self._call(["container", "ls", "--all", "--quiet", "--filter", f"label={self.LABEL}={job_id}"], timeout=30)
        if result.returncode != 0 or result.stdout.strip():
            return "retained: one or more job containers remain"
        parent = root / ".sober" / self.SCRATCH_DIR
        target = parent / job_id
        marker = target / ".update-vanguard-owner.json"
        if ((root / ".sober").is_symlink() or parent.is_symlink() or target.is_symlink() or marker.is_symlink()
                or not marker.is_file() or not target.resolve().is_relative_to(parent.resolve())):
            return "retained: scratch ownership or path could not be verified"
        try:
            info = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return "retained: scratch ownership marker is invalid"
        if info != {"job_id": job_id, "project_root": str(root)}:
            return "retained: scratch ownership marker does not match this job"
        shutil.rmtree(target)
        return "removed: owned job scratch after all phases passed"

    def cancel_recorded(self, *, job_id: str, job: dict[str, Any], ledger: Ledger) -> dict[str, Any]:
        execution = job["receipt"].get("execution", {})
        current = execution.get("current")
        if not isinstance(current, dict) or not isinstance(current.get("name"), str):
            raise ExecutorError("no active isolated update test is recorded")
        record = self._verify_container(current["name"], job_id)
        if record is None:
            raise ExecutorUncertain("recorded container is missing; cancellation cannot be proven")
        if record["running"]:
            stopped = self._call(["container", "stop", "--time", "5", current["name"]], timeout=15)
            record = self._verify_container(current["name"], job_id)
            if (stopped.returncode != 0 and record is not None and record["running"]):
                raise ExecutorUncertain("container stop failed; process may still be active")
        elif record["status"] != "exited":
            raise ExecutorUncertain("container is not running or cleanly exited; cancellation is unverified")
        else:
            raise ExecutorError("container already exited; reconcile its result instead of marking it cancelled")
        if record is None or record["running"]:
            raise ExecutorUncertain("container termination is not verified")
        current.update({"status": "cancelled", "exit_code": record["exit_code"],
                        "output": self._logs(current["name"])})
        execution.setdefault("phases", []).append(dict(current))
        execution["current"] = None
        execution["status"] = "cancelled"
        execution["cancelled_at"] = time.time()
        ledger.record(job_id, "isolated update test cancelled and process fenced", job["receipt"])
        removed = self._call(["container", "rm", current["name"]], timeout=60)
        execution["scratch_cleanup"] = "retained: container removal unverified" if removed.returncode else "retained: cancelled job evidence"
        ledger.record(job_id, "cancelled test resource cleanup reconciled", job["receipt"])
        return execution

    def reconcile_recorded(self, *, root: Path, job_id: str, job: dict[str, Any], ledger: Ledger) -> dict[str, Any]:
        execution = job["receipt"].get("execution", {})
        current = execution.get("current")
        if not isinstance(current, dict) or not isinstance(current.get("name"), str):
            phases = execution.get("phases", [])
            if not phases:
                if execution.get("status") == "preparing":
                    listed = self._call(["container", "ls", "--all", "--quiet", "--filter",
                                         f"label={self.LABEL}={job_id}"], timeout=30)
                    if listed.returncode != 0 or listed.stdout.strip():
                        return {"reconciled": False, "reason": "preflight container state is not proven",
                                "retry_performed": False}
                    execution["status"] = "interrupted"
                    ledger.record(job_id, "Docker proved test preflight left no containers", job["receipt"])
                    return {"reconciled": True, "preflight_only": True, "retry_performed": False}
                return {"reconciled": False, "reason": "no active or completed container phase is recorded"}
            cleaned = 0
            for phase in phases:
                name = phase.get("name") if isinstance(phase, dict) else None
                if not isinstance(name, str):
                    continue
                record = self._verify_container(name, job_id)
                if record is None:
                    continue
                if record["running"]:
                    return {"reconciled": False, "running": True, "container": name,
                            "retry_performed": False, "cleaned_containers": cleaned}
                expected = phase.get("exit_code")
                valid_terminal = record["status"] == "exited" and (
                    record["exit_code"] == expected
                    or (phase.get("phase") == "install" and phase.get("network_fenced") is True
                        and record["exit_code"] == 137)
                )
                if not valid_terminal:
                    return {"reconciled": False, "reason": "completed phase container has an unverified terminal state",
                            "container": name, "retry_performed": False, "cleaned_containers": cleaned}
                removed = self._call(["container", "rm", name], timeout=60)
                if removed.returncode != 0 and self._verify_container(name, job_id) is not None:
                    return {"reconciled": False, "reason": "completed phase container cleanup is unverified",
                            "container": name, "retry_performed": False, "cleaned_containers": cleaned}
                cleaned += 1
            if cleaned:
                ledger.record(job_id, "terminal recorded phase containers removed after inspection", job["receipt"])
            return {"reconciled": bool(cleaned), "cleaned_containers": cleaned,
                    "retry_performed": False}
        record = self._verify_container(current["name"], job_id)
        if record is None:
            return {"reconciled": False, "reason": "recorded container is missing; no retry performed"}
        if record["running"] and current.get("phase") == "install":
            marker = self._call(["container", "exec", current["name"], "sh", "-c",
                                 "cat /tmp/update-vanguard-install.exit"], timeout=15)
            if marker.returncode != 0 or not marker.stdout.strip().isdigit():
                return {"reconciled": False, "running": True, "container": current["name"], "retry_performed": False}
            code = int(marker.stdout.strip())
            if code == 0:
                self._disconnect_network(current["name"], job_id)
                candidate = job["receipt"].get("plan", {}).get("candidates", [{}])[0]
                config = execution.get("adapter_config", {})
                self._export_venv(container=current["name"],
                                  venv=root / ".sober" / self.SCRATCH_DIR / job_id / "venv",
                                  job_id=job_id, image_id=str(config.get("image_id", "")),
                                  lock_sha=str(candidate.get("new_lock_sha256", "")), execution=config)
            self._call(["container", "stop", "--time", "5", current["name"]], timeout=15)
            record = self._verify_container(current["name"], job_id)
            if record is None or record["running"] or record["status"] != "exited":
                return {"reconciled": False, "reason": "recorded install marker found but shutdown is unverified",
                        "retry_performed": False}
            current.update({"reconciled_install_exit_code": code})
        elif record["running"]:
            return {"reconciled": False, "running": True, "container": current["name"], "retry_performed": False}
        if record["status"] == "created" and record["pid"] == 0 and record["error"]:
            current.update({"status": "failed_to_start", "detail": record["error"], "exit_code": 127})
            execution.setdefault("phases", []).append(dict(current))
            execution["current"] = None
            execution["status"] = "failed"
            ledger.record(job_id, "Docker proved isolated container never started", job["receipt"])
            removed = self._call(["container", "rm", current["name"]], timeout=60)
            execution["scratch_cleanup"] = self._cleanup_scratch(root, job_id) if removed.returncode == 0 else "retained: container removal unverified"
            ledger.record(job_id, "failed-to-start container reconciliation recorded", job["receipt"])
            return {"reconciled": True, "running": False, "exit_code": 127, "retry_performed": False,
                    "reason": "Docker state proves the process never started"}
        if record["status"] != "exited":
            return {"reconciled": False, "reason": "container has no verified exit state; no retry performed"}
        if current.get("phase") == "install" and record["exit_code"] == 0:
            candidate = job["receipt"].get("plan", {}).get("candidates", [{}])[0]
            config = execution.get("adapter_config", {})
            scratch = root / ".sober" / self.SCRATCH_DIR / job_id
            venv = scratch / "venv"
            self._export_venv(container=current["name"], venv=venv, job_id=job_id,
                              image_id=str(config.get("image_id", "")),
                              lock_sha=str(candidate.get("new_lock_sha256", "")),
                              execution=config)
        reconciled_exit = current.pop("reconciled_install_exit_code",
                                      current.pop("install_exit_code", record["exit_code"]))
        current.update({"status": "completed" if reconciled_exit == 0 else "failed",
                        "exit_code": reconciled_exit, "output": self._logs(current["name"])})
        execution.setdefault("phases", []).append(dict(current))
        execution["current"] = None
        execution["status"] = "running" if reconciled_exit == 0 else "failed"
        ledger.record(job_id, "interrupted isolated phase reconciled from Docker state", job["receipt"])
        removed = self._call(["container", "rm", current["name"]], timeout=60)
        if reconciled_exit != 0:
            execution["scratch_cleanup"] = self._cleanup_scratch(root, job_id) if removed.returncode == 0 else "retained: container removal unverified"
            ledger.record(job_id, "failed test resource cleanup reconciled", job["receipt"])
        return {"reconciled": True, "running": False, "exit_code": reconciled_exit, "retry_performed": False}
