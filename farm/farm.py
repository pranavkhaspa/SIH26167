#!/usr/bin/env python3
"""SatQuery AI — Daytona worker farm orchestrator (stdlib only)."""

import argparse
import concurrent.futures
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path("/home/pro/Documents/sih/SIH26167")
ENV_PATH = REPO_ROOT / ".env"
RESULTS_DIR = REPO_ROOT / "farm" / "results"
CONTROL_PLANE = "https://app.daytona.io/api"

_lock = threading.Lock()


# ── HTTP helper ───────────────────────────────────────────────────────────────

def http(method, url, key, body=None, headers=None, timeout=90):
    hdrs = {"Authorization": f"Bearer {key}"}
    if headers:
        hdrs.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        err_body = exc.read() if exc.fp else b""
        return exc.code, err_body


def http_multipart(method, url, key, field_name, file_bytes, filename,
                   content_type="application/gzip", timeout=90):
    boundary = "----SatQueryFarmBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
    hdrs = {
        "Authorization": f"Bearer {key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        err_body = exc.read() if exc.fp else b""
        return exc.code, err_body


# ── Config load ───────────────────────────────────────────────────────────────

def load_env(path):
    env = {}
    pending_key = None
    pending_parts = []
    pending_delta = 0
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if pending_key is not None:
                pending_parts.append(line)
                pending_delta += line.count("{") - line.count("}")
                if pending_delta <= 0:
                    v = "\n".join(pending_parts).strip().strip("'\"")
                    env[pending_key] = v
                    pending_key = None
                continue
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            delta = v.count("{") - v.count("}")
            if delta > 0:
                pending_key = k
                pending_parts = [v]
                pending_delta = delta
            else:
                env[k] = v.strip("'\"")
    return env


def build_machines(env):
    raw = env.get("DAYTONA_MACHINES", "")
    if not raw:
        return {}
    machines = json.loads(raw)
    for name in list(machines.keys()):
        per_key = f"DAYTONA_MACHINE_{name.upper()}"
        if per_key in env and env[per_key]:
            machines[name] = env[per_key]
    seen = set()
    deduped = {}
    for name, key in machines.items():
        if name not in seen:
            seen.add(name)
            deduped[name] = key
    return deduped


# ── Probe / dry-run ───────────────────────────────────────────────────────────

def probe_machine(name, key):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    body = {"name": f"sih-probe-{ts}-{name}", "class": "small", "autoDeleteInterval": 1}
    sandbox_id = None
    try:
        status, resp = http("POST", f"{CONTROL_PLANE}/sandbox", key, body=body, timeout=30)
        if status == 200:
            data = json.loads(resp)
            sandbox_id = data.get("id")
            return "USABLE", sandbox_id
        resp_text = resp.decode(errors="replace").lower()
        if status == 403 and ("suspended" in resp_text or "depleted credits" in resp_text or "credits" in resp_text):
            return "SUSPENDED", None
        for _ in range(2):
            time.sleep(1)
            status, resp = http("POST", f"{CONTROL_PLANE}/sandbox", key, body=body, timeout=30)
            if status == 200:
                data = json.loads(resp)
                sandbox_id = data.get("id")
                return "USABLE", sandbox_id
            resp_text = resp.decode(errors="replace").lower()
            if status == 403 and ("suspended" in resp_text or "depleted credits" in resp_text or "credits" in resp_text):
                return "SUSPENDED", None
        return "UNREACHABLE", None
    except Exception:
        return "UNREACHABLE", None
    finally:
        if sandbox_id:
            for retry in range(3):
                try:
                    status = http("DELETE", f"{CONTROL_PLANE}/sandbox/{sandbox_id}", key, timeout=15)[0]
                    if status in (200, 404):
                        break
                    if status == 409:
                        time.sleep(2)
                        continue
                    break
                except Exception:
                    break


def do_probe(machines):
    results = {}
    for name, key in machines.items():
        status, _ = probe_machine(name, key)
        results[name] = status
        print(f"  {name:<12} {status}")
    return results


# ── Tarball builder ───────────────────────────────────────────────────────────

def build_tarball(include_frontend, failpoint, tmpdir):
    archive_path = os.path.join(tmpdir, "sih-src.tar.gz")
    subprocess.run(
        ["git", "archive", "--format=tar.gz", "--prefix=sih/", "-o", archive_path, "HEAD"],
        cwd=str(REPO_ROOT), check=True,
    )
    if failpoint:
        tmp_extract = os.path.join(tmpdir, "extract")
        os.makedirs(tmp_extract, exist_ok=True)
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(tmp_extract)
        fail_dir = os.path.join(tmp_extract, "sih", "backend", "tests")
        os.makedirs(fail_dir, exist_ok=True)
        with open(os.path.join(fail_dir, "test_farm_failpoint.py"), "w") as f:
            f.write("def test_farm_failpoint():\n    assert False, 'injected farm failpoint'\n")
        new_archive = os.path.join(tmpdir, "sih-src-fp.tar.gz")
        with tarfile.open(new_archive, "w:gz") as tf:
            for entry in os.listdir(tmp_extract):
                tf.add(os.path.join(tmp_extract, entry), arcname=entry)
        archive_path = new_archive
        shutil.rmtree(tmp_extract)
    with open(archive_path, "rb") as f:
        return f.read()


# ── Single job runner ─────────────────────────────────────────────────────────

def get_git_rev():
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT),
                       capture_output=True, text=True)
    return r.stdout.strip()


def run_job(machine_name, machine_key, task, sandbox_class, snapshot,
            tarball_bytes, job_cap, include_frontend, rev):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    rec = {"machine": machine_name, "ok": False, "exit": None, "artifact": None}
    sandbox_id = None
    toolbox_url = None
    try:
        # 5a — create sandbox (try snapshot, fall back to stock image on error)
        for candidate in ([snapshot, None] if snapshot else [None]):
            if candidate is None and sandbox_id:
                break
            body = {
                "name": f"sih-{task}-{machine_name}-{ts}",
                "class": sandbox_class,
                "autoDeleteInterval": 90,
            }
            if candidate:
                body["snapshot"] = candidate
            status, resp = http("POST", f"{CONTROL_PLANE}/sandbox", machine_key, body=body, timeout=60)
            if status == 200:
                data = json.loads(resp)
                sandbox_id = data.get("id")
                toolbox_url = data.get("toolboxProxyUrl", "")
                break
            if status == 403:
                resp_text = resp.decode(errors="replace").lower()
                if "suspended" in resp_text or "depleted credits" in resp_text or "credits" in resp_text:
                    rec["exit"] = "SUSPENDED"
                    print(f"  {machine_name:<12} SUSPENDED (sandbox create 403)")
                    return rec

        if not sandbox_id:
            rec["exit"] = "FAIL"
            print(f"  {machine_name:<12} FAIL (sandbox create)")
            return rec

        # 5b — poll until started
        start = time.time()
        while time.time() - start < 120:
            status, resp = http("GET", f"{CONTROL_PLANE}/sandbox/{sandbox_id}", machine_key, timeout=15)
            if status == 200:
                data = json.loads(resp)
                if data.get("state") == "started":
                    toolbox_url = data.get("toolboxProxyUrl", toolbox_url)
                    break
            time.sleep(3)
        else:
            rec["exit"] = "FAIL"
            print(f"  {machine_name:<12} FAIL (sandbox timeout)")
            return rec

        # 5c — upload tarball
        upload_url = f"{toolbox_url}/{sandbox_id}/files/upload?path=/home/daytona/sih-src.tar.gz"
        status, resp = http_multipart("POST", upload_url, machine_key,
                                      "file", tarball_bytes, "sih-src.tar.gz", timeout=120)
        if status != 200:
            rec["exit"] = "FAIL"
            err_preview = resp.decode(errors="replace")[:220]
            print(f"  {machine_name:<12} FAIL (upload {status}: {err_preview}) "
                  f"[sid={sandbox_id} url={upload_url}]")
            return rec

        # 5d — build script
        script_lines = [
            "set -eo pipefail",
            "cd /home/daytona && rm -rf w && mkdir w && tar xzf sih-src.tar.gz -C w",
            "cd w/sih/backend && pip3 install -q --no-input -r requirements.txt",
            "python3 -m pytest -q --disable-warnings 2>&1 | tee /home/daytona/results.txt",
        ]
        if include_frontend:
            script_lines.append(
                "cd /home/daytona/w/sih/frontend && (npm ci --silent && npm run lint && npm run build) "
                "> >(tee -a /home/daytona/results.txt) 2>&1"
            )
            script_lines.append("wait")
        script = "\n".join(script_lines)
        cap = min(job_cap, 86400)
        exec_url = f"{toolbox_url}/{sandbox_id}/process/execute"
        status, resp = http("POST", exec_url, machine_key,
                            body={"command": script, "timeout": cap}, timeout=cap + 30)
        if status == 200:
            data = json.loads(resp)
            rec["exit"] = data.get("exitCode", 1)
        else:
            rec["exit"] = 1

        # 5e — download results
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        artifact_name = f"{task}-{rev}-{machine_name}.txt"
        artifact_path = RESULTS_DIR / artifact_name
        dl_url = f"{toolbox_url}/{sandbox_id}/files/download?path=/home/daytona/results.txt"
        try:
            ds, dr = http("GET", dl_url, machine_key, timeout=30)
            if ds == 200:
                artifact_path.write_bytes(dr)
                rec["artifact"] = str(artifact_path)
        except Exception:
            pass

        rec["ok"] = rec["exit"] == 0
        verdict = "PASS" if rec["ok"] else f"FAIL (exit {rec['exit']})"
        print(f"  {machine_name:<12} {verdict}")

    except Exception as exc:
        rec["exit"] = "EXCEPTION"
        print(f"  {machine_name:<12} FAIL (exception: {exc})")
    finally:
        # 5f — best-effort delete
        if sandbox_id:
            for retry in range(3):
                try:
                    ds, _ = http("DELETE", f"{CONTROL_PLANE}/sandbox/{sandbox_id}",
                                 machine_key, timeout=15)
                    if ds in (200, 404):
                        break
                    if ds == 409:
                        time.sleep(3)
                        continue
                    break
                except Exception:
                    break
    return rec


# ── CLI / main ────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(description="SatQuery AI — Daytona worker farm orchestrator")
    p.add_argument("--task", default="gate", help="Task name (default: gate)")
    p.add_argument("--class", dest="sandbox_class", default="small",
                   choices=["small", "medium", "large"], help="Sandbox class")
    p.add_argument("--parallel", type=int, default=0,
                   help="Parallel workers (default: #usable machines)")
    p.add_argument("--include-frontend", action="store_true",
                   help="Also run npm ci/lint/build in sandboxes")
    p.add_argument("--snapshot", default="sih-farm-base",
                   help="Snapshot name for warm boot")
    p.add_argument("--dry-run", action="store_true",
                   help="Probe machines only, no jobs")
    p.add_argument("--timeout", type=int, default=900,
                   help="Per-job timeout in seconds")
    p.add_argument("--machines", default="",
                   help="Comma-separated machine filter (default: all usable)")
    p.add_argument("--failpoint", action="store_true",
                   help="Inject a failing pytest assertion into the tarball")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not ENV_PATH.exists():
        print(f"ERROR: {ENV_PATH} not found", file=sys.stderr)
        sys.exit(2)

    env = load_env(str(ENV_PATH))
    machines = build_machines(env)
    if not machines:
        print("ERROR: no machines in DAYTONA_MACHINES", file=sys.stderr)
        sys.exit(2)

    print(f"=== SatQuery Farm — task={args.task} class={args.sandbox_class} "
          f"parallel={args.parallel} snapshot={args.snapshot} ===\n")

    print("Probing machines:")
    probe = do_probe(machines)
    usable = {n: machines[n] for n, s in probe.items() if s == "USABLE"}
    if args.machines:
        want = {m.strip() for m in args.machines.split(",") if m.strip()}
        usable = {n: k for n, k in usable.items() if n in want}
    print(f"\nUsable: {len(usable)} / {len(machines)}\n")

    if args.dry_run:
        if not usable:
            print("ERROR: zero usable machines (dry-run, zero work requested)",
                  file=sys.stderr)
            sys.exit(2)
        sys.exit(0)

    if not usable:
        print("ERROR: zero usable machines", file=sys.stderr)
        sys.exit(2)

    rev = get_git_rev()
    print(f"Git rev: {rev}")
    print(f"Building tarball {'with failpoint' if args.failpoint else ''}...")
    tmpdir = tempfile.mkdtemp()
    try:
        tarball_bytes = build_tarball(args.include_frontend, args.failpoint, tmpdir)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"Tarball: {len(tarball_bytes)} bytes\n")

    parallel = args.parallel if args.parallel > 0 else len(usable)
    print(f"Running {args.task} on {len(usable)} machines (parallel={parallel}):\n")

    runs = []
    summary = {"rev": rev, "task": args.task,
               "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), "runs": runs}

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {}
            for name, key in usable.items():
                fut = pool.submit(run_job, name, key, args.task, args.sandbox_class,
                                  args.snapshot, tarball_bytes, args.timeout,
                                  args.include_frontend, rev)
                futures[fut] = name
            try:
                for fut in concurrent.futures.as_completed(futures):
                    rec = fut.result()
                    with _lock:
                        runs.append(rec)
            except (KeyboardInterrupt, SystemExit):
                print("\nInterrupted — cancelling pending jobs...")
                for f in futures:
                    f.cancel()
                pool.shutdown(wait=False, cancel_futures=True)
                raise
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        print("\n=== Summary ===\n")
        print(f"{'machine':<14} {'result':<12} {'exit':<10} {'artifact'}")
        print("-" * 60)
        all_ok = True
        for r in runs:
            v = "PASS" if r["ok"] else f"FAIL"
            print(f"{r['machine']:<14} {v:<12} {str(r['exit']):<10} {r.get('artifact') or ''}")
            if not r["ok"]:
                all_ok = False
        pass_count = sum(1 for r in runs if r["ok"])
        fail_count = len(runs) - pass_count
        print(f"\n{pass_count} passed, {fail_count} failed out of {len(runs)} usable machines")

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        summary_path = RESULTS_DIR / f"{args.task}-{rev}-summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nSummary written to {summary_path}")

        if not runs:
            sys.exit(2)
        if all_ok:
            sys.exit(0)
        sys.exit(1)


if __name__ == "__main__":
    main()
