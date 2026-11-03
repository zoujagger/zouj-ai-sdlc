"""`sdlc setup`: guided, rerunnable onboarding (preflight → inventory → plan → confirm → apply → human steps → doctor).

Profiles change only how strongly a human approval is proven; every profile runs the same playbook workflow
(docs/sdlc.md). External tools are looked up on PATH and run with a short timeout: a missing or hung `claude`/`gh`
becomes a warning, while missing git, make or python >= 3.9 stops setup before anything is written.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import approvals, cli
from .machine import config, initialized

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


# What each profile writes into a new .aiops/config.json. Only how an approval is proven differs; the workflow and
# every gate are identical (tests/test_playbook.py).
PROFILE_CONFIG = {
    "solo": {"profile": "solo", "require_signed_approvals": False, "commit_approvals": True, "approval_key_policy": "any"},
    "team": {"profile": "team", "require_signed_approvals": True, "commit_approvals": True, "approval_key_policy": "human"},
    "strict": {"profile": "strict", "require_signed_approvals": True, "commit_approvals": True, "approval_key_policy": "sk"},
}
MARKETPLACE = {"extraKnownMarketplaces": {"zouj": {"source": {"source": "github", "repo": "zoujagger/zouj-ai-sdlc"}}},
               "enabledPlugins": {"zouj-ai-sdlc@zouj": True}}
GATES = """Gates
  The AI-Native SDLC Playbook workflow, the same in every profile:
  1 BRAINSTORMING → intent.md, opened only by the human: `Intent Approved NNNN`
  2 SPECIFICATION → spec.md, opened only by the human: `Spec Approved NNNN`
  3 PLAN (code is read-only in states 1-3) → plan.md, opened only by the human: `Plan Approved NNNN`
  4 EXECUTION, autonomous TDD; the Stop hook requires `make check` green
  5 PRE-REVIEW, fresh-context reviewers → review.md + pr.md; only a human may merge (no merge or push to main by the agent)
  Production deploys are a human gate. The profile only sets how an approval is proven ({proof})."""
PROOF = {"solo": "typed phrase + an unsigned approval commit", "team": "an SSH-signed commit, a human per signature",
         "strict": "an SSH-signed commit with an sk- key touch"}


def _json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def inventory(root):
    """[(status, label, "")] describing what's already there."""
    rows = []
    if initialized(root):
        cfg = config(root)
        rows.append(("✓", f"initialized (.aiops/), profile: {cfg['profile']}", ""))
    else:
        rows.append(("·", "not initialized (no .aiops/)", ""))
    settings = _json(root / ".claude" / "settings.json")
    has = bool(settings and all(k in settings and all(kk in settings[k] for kk in v) for k, v in MARKETPLACE.items()))
    rows.append(("✓" if has else "·", "project offers the plugin (.claude/settings.json marketplace keys)"
                 if has else "project doesn't offer the plugin yet (.claude/settings.json)", ""))
    user = _json(Path.home() / ".claude" / "settings.json") or {}
    enabled = bool((user.get("enabledPlugins") or {}).get("zouj-ai-sdlc@zouj"))
    rows.append(("✓" if enabled else "·", "plugin enabled in ~/.claude/settings.json" if enabled
                 else "plugin not enabled for this user (Claude Code offers it from the project settings)", ""))
    return rows


def plan(root, profile):
    """[(mark, rel, note)]: `+` create, `~` change (shown as a diff), `=` unchanged."""
    out = []
    for act, rel in cli.init_actions(root):
        if act == "create":
            note = f"profile {profile}: {PROOF[profile]}" if rel == ".aiops/config.json" else ""
            out.append(("+", rel, note))
        else:
            out.append(("=", rel, "kept"))
    cfg = _json(root / ".aiops" / "config.json")
    if cfg is not None:
        want = {k: v for k, v in PROFILE_CONFIG[profile].items() if cfg.get(k, config(root).get(k)) != v}
        if want:
            out = [o for o in out if o[1] != ".aiops/config.json"]
            out.append(("~", ".aiops/config.json", "set " + ", ".join(f"{k}={json.dumps(v)}" for k, v in want.items())))
    settings = _json(root / ".claude" / "settings.json")
    if settings is not None and not all(k in settings for k in MARKETPLACE):
        out = [o for o in out if o[1] != ".claude/settings.json"]
        out.append(("~", ".claude/settings.json", "add extraKnownMarketplaces.zouj and enabledPlugins (nothing else)"))
    return out


def _choices(args):
    profile = args[args.index("--profile") + 1] if "--profile" in args[:-1] else None
    return profile, "--dry-run" in args, "--yes" in args


def main(root, args):
    profile, dry_run, yes = _choices(args)
    if profile is not None and profile not in PROFILES:
        print(f"unknown profile {profile!r} (solo, team, strict)", file=sys.stderr)
        return 1
    tty = sys.stdin.isatty()
    if profile is None and not dry_run and not tty:
        print("setup needs choices and there's no terminal to ask them; nothing was written. Run again with:\n"
              "  sdlc setup --profile solo|team|strict --yes   (or --dry-run to preview)")
        return 2
    if profile is None:
        profile = config(root)["profile"] if dry_run else _ask_profile()
    rows = preflight(root, profile)
    show("Preflight", rows)
    if blocking(rows):
        print("setup stops: fix the ✗ rows above and run it again; nothing was written.")
        return 1
    show("Inventory", inventory(root))
    actions = plan(root, profile)
    print("Plan")
    for mark, rel, note in actions:
        print(f"  {mark} {rel}" + (f"  ({note})" if note else ""))
    print(GATES.format(proof=PROOF[profile]))
    if dry_run:
        print("dry run: nothing was written.")
        return 0
    if not yes and not (tty and _confirm()):
        print("not confirmed: nothing was written. Re-run with --yes to apply without the question."
              if tty else "no terminal to confirm: nothing was written. Re-run with --yes to apply.")
        return 2
    return apply(root, profile, actions, args)


def _ask_profile():
    answer = input("Profile? solo (unsigned), team (signed, passphrase), strict (sk- key) [team]: ").strip() or "team"
    if answer not in PROFILES:
        raise SystemExit(f"unknown profile {answer!r}")
    return answer


def _confirm():
    try:
        return input("Apply this plan? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def apply(root, profile, actions, args):
    print("apply: not part of this step yet (S7); nothing was written.")
    return 1
