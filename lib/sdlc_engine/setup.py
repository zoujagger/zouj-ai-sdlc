"""`sdlc setup`: guided, rerunnable onboarding (preflight → inventory → plan → confirm → apply → human steps → doctor).

Profiles change only how strongly a human approval is proven; every profile runs the same playbook workflow
(docs/sdlc.md). External tools are looked up on PATH and run with a short timeout: a missing or hung `claude`/`gh`
becomes a warning, while missing git, make or python >= 3.9 stops setup before anything is written.
"""
import os
import re
import shutil
import subprocess
import sys

from . import approvals

PROFILES = ("solo", "team", "strict")
TIMEOUT = 5


def _run(cmd, path, timeout, cwd=None):
    """Combined stdout+stderr of cmd with PATH=path, or None if it can't run or doesn't finish in time."""
    exe = shutil.which(cmd[0], path=path)
    if not exe:
        return None
    try:
        r = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=timeout, cwd=cwd,
                           env={**os.environ, "PATH": path})
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (r.returncode, (r.stdout or "") + (r.stderr or ""))


def preflight(root, profile, version=None, path=None, timeout=TIMEOUT):
    """[(status, label, fix)] with status ✓ (ok), ! (warning, setup continues) or ✗ (setup stops)."""
    path = path if path is not None else os.environ.get("PATH", "")
    v = tuple(version or sys.version_info[:3])
    rows = []
    for tool in ("git", "make"):
        ok = shutil.which(tool, path=path) is not None
        rows.append(("✓" if ok else "✗", tool, "" if ok else f"install {tool}"))
    rows.append(("✓" if v >= (3, 9) else "✗", f"python {'.'.join(map(str, v))} (>= 3.9)",
                 "" if v >= (3, 9) else "install python 3.9 or newer"))

    res = _run(["claude", "--version"], path, timeout)
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", res[1]) if res else None
    if not shutil.which("claude", path=path):
        rows.append(("!", "claude (Claude Code) not on PATH", "install Claude Code 2.1 or newer"))
    elif not m:
        rows.append(("!", "claude --version didn't answer", "check that Claude Code runs: claude --version"))
    else:
        ver = m.group(0)
        ok = (int(m.group(1)), int(m.group(2))) >= (2, 1)
        rows.append(("✓" if ok else "!", f"claude {ver} (>= 2.1)", "" if ok else "update Claude Code to 2.1 or newer"))

    if shutil.which("gh", path=path):
        res = _run(["gh", "auth", "status"], path, timeout)          # never -t/--show-token: no token in the output
        scopes = re.search(r"Token scopes:\s*(.*)", res[1]) if res else None
        if not res or res[0] != 0:
            rows.append(("!", "gh is not logged in (needed to push and open PRs)", "gh auth login"))
        elif scopes and "workflow" not in scopes.group(1):
            rows.append(("!", "gh token lacks the `workflow` scope (pushing .github/workflows is refused)",
                         "gh auth refresh -h github.com -s workflow"))
        else:
            rows.append(("✓", "gh logged in", ""))
    else:
        rows.append(("!", "gh (optional: push, PRs, issues)", "install the GitHub CLI"))

    if shutil.which("git", path=path):
        res = _run(["git", "config", "--get-all", "credential.helper"], path, timeout, cwd=root)
        ok = bool(res and res[0] == 0 and res[1].strip())
        rows.append(("✓" if ok else "!", "git credential helper" + ("" if ok else " (git push over https will fail)"),
                     "" if ok else "gh auth setup-git (or configure any git credential helper)"))

    if profile in ("team", "strict"):
        rows += _signing_rows(root, profile)
    return rows


def _signing_rows(root, profile):
    pubtext, _private = approvals._signing_key_files(root)
    if not pubtext.strip():
        return [("!", "no SSH signing key configured (setup prints the steps)", "see the human steps below")]
    if profile == "strict" and not pubtext.startswith("sk-"):
        return [("!", "strict needs a FIDO sk- key that requires a touch", "see the human steps below")]
    weak = approvals.key_protection(root)
    return [("!" if weak else "✓", f"signing key: {weak}" if weak else "signing key protected (a human per signature)",
             "see the human steps below" if weak else "")]


def blocking(rows):
    return any(st == "✗" for st, _, _ in rows)


def show(title, rows):
    print(title)
    for st, label, fix in rows:
        print(f"  {st} {label}" + (f"\n      fix: {fix}" if fix and st != "✓" else ""))


def main(root, args):
    profile = args[args.index("--profile") + 1] if "--profile" in args[:-1] else None
    if profile is not None and profile not in PROFILES:
        print(f"unknown profile {profile!r} (solo, team, strict)", file=sys.stderr)
        return 1
    rows = preflight(root, profile)
    show("Preflight", rows)
    if blocking(rows):
        print("setup stops: fix the ✗ rows above and run it again; nothing was written.")
        return 1
    return 0
