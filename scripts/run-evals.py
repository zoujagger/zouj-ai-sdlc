#!/usr/bin/env python3
"""Run the agent eval suite in evals/tasks/*.yaml against headless Claude Code.

Each task runs in a throwaway git worktree (so the repo's real .claude/ hooks and skills apply):
setup -> commit -> `claude -p <prompt>` -> check. Exit code 0 only if every task passes.
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TASKS = ROOT / "evals" / "tasks"


def load_tasks(only):
    try:
        import yaml
    except ImportError:
        sys.exit("pyyaml is required: pip install pyyaml")
    tasks = []
    for f in sorted(TASKS.glob("*.yaml")):
        t = yaml.safe_load(f.read_text())
        missing = {"id", "prompt", "check"} - t.keys()
        if missing:
            sys.exit(f"{f}: missing {sorted(missing)}")
        if not only or t["id"] in only:
            tasks.append(t)
    return tasks


def sh(script, cwd, env=None):
    return subprocess.run(["bash", "-euo", "pipefail", "-c", script], cwd=cwd, env=env,
                          capture_output=True, text=True)


def run_task(t, timeout):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"eval-{t['id']}-"))
    wt = tmp / "wt"
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(wt), "HEAD"], cwd=ROOT, check=True)
    try:
        r = sh(t.get("setup") or "true", wt)
        if r.returncode:
            return False, f"setup failed: {r.stderr.strip()[-500:]}"
        sh("git add -A && git -c user.name=eval -c user.email=eval@localhost commit -qm 'eval setup' --allow-empty", wt)

        out = tmp / "output.txt"
        cmd = ["claude", "-p", t["prompt"], "--output-format", "text",
               "--max-turns", str(t.get("max_turns", 30)), "--permission-mode", "acceptEdits"]
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(wt)}
        try:
            res = subprocess.run(cmd, cwd=wt, env=env, capture_output=True, text=True, timeout=timeout)
            out.write_text(res.stdout + "\n" + res.stderr)
        except subprocess.TimeoutExpired:
            return False, f"claude timed out after {timeout}s"

        r = sh(t["check"], wt, env={**env, "EVAL_OUTPUT": str(out)})
        detail = (r.stdout + r.stderr).strip()[-500:]
        return r.returncode == 0, detail
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="list tasks without running")
    ap.add_argument("--only", nargs="*", default=[], help="task ids to run")
    ap.add_argument("--timeout", type=int, default=600, help="seconds per task")
    args = ap.parse_args()

    tasks = load_tasks(set(args.only))
    if args.dry_run:
        for t in tasks:
            print(f"{t['id']:<28} [{t.get('source', 'seed')}] {t.get('description', '')}")
        print(f"{len(tasks)} task(s)")
        return 0

    if not shutil.which("claude"):
        sys.exit("claude CLI not found (npm i -g @anthropic-ai/claude-code)")

    passed = 0
    for t in tasks:
        ok, detail = run_task(t, args.timeout)
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {t['id']}" + ("" if ok else f"\n      {detail}"))
    print(f"\n{passed}/{len(tasks)} passed")
    return 0 if passed == len(tasks) else 1


if __name__ == "__main__":
    sys.exit(main())
