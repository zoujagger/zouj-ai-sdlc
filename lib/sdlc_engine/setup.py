"""`sdlc setup`: guided, rerunnable onboarding (preflight → inventory → plan → confirm → apply → human steps → doctor).

Profiles change only how strongly a human approval is proven; every profile runs the same playbook workflow
(docs/sdlc.md). External tools are looked up on PATH and run with a short timeout: a missing or hung `claude`/`gh`
becomes a warning, while missing git, make or python >= 3.9 stops setup before anything is written.
"""
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import approvals, cli
from .machine import config, initialized

PROFILES = cli.PROFILES
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
    rows += owned_json_rows(root)
    return rows


OWNED_JSON = (".aiops/config.json", ".claude/settings.json")


def owned_json_rows(root):
    """✗ for an existing human-owned JSON file that doesn't parse: setup would otherwise skip it silently (and read
    the default profile in its place). The human fixes it; setup never rewrites a file it can't read."""
    rows = []
    for rel in OWNED_JSON:
        f = root / rel
        if not f.is_file():
            continue
        try:
            json.loads(f.read_text())
        except (OSError, ValueError) as exc:
            rows.append(("✗", f"{rel} isn't valid JSON ({exc})", f"fix {rel} by hand (it's human-owned), then rerun"))
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
# Pinned to this release: enabling the plugin trusts github.com/zoujagger/zouj-ai-sdlc at that ref, and its hooks run
# as the user, so the ref moves only through a reviewed change (rerunning setup after an upgrade proposes it).
REF = f"v{cli.plugin_version()}"
MARKETPLACE = {"extraKnownMarketplaces": {"zouj": {"source": {"source": "github", "repo": "zoujagger/zouj-ai-sdlc",
                                                              "ref": REF}}},
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
    zouj = ((settings or {}).get("extraKnownMarketplaces") or {}).get("zouj")
    if settings and _with_marketplace(settings) == settings:
        rows.append(("✓", f"project offers the plugin, pinned to {REF} (.claude/settings.json)", ""))
    elif zouj:
        rows.append(("!", f"project offers the plugin from {json.dumps(zouj.get('source'))}, not the official "
                     f"{REF} source (setup proposes the change)", ""))
    else:
        rows.append(("·", "project doesn't offer the plugin yet (.claude/settings.json)", ""))
    user = _json(Path.home() / ".claude" / "settings.json") or {}
    enabled = bool((user.get("enabledPlugins") or {}).get("zouj-ai-sdlc@zouj"))
    rows.append(("✓" if enabled else "·", "plugin enabled in ~/.claude/settings.json" if enabled
                 else "plugin not enabled for this user (Claude Code offers it from the project settings)", ""))
    return rows


def plan(root, profile):
    """[(mark, rel, note)]: `+` create, `~` change (shown as a diff), `=` unchanged."""
    out = []
    for act, rel in cli.init_actions(root):
        if act == "symlink":
            out.append(("✗", rel, f"{cli.symlink_on_path(root, rel)} is a symlink: remove it, setup won't write through links"))
        elif act == "create":
            note = ""
            if rel == ".aiops/config.json":
                note = (f"init's defaults; profile {profile} becomes your human step"
                        if approvals.running_under_agent() else f"profile {profile}: {PROOF[profile]}")
            out.append(("+", rel, note))
        else:
            out.append(("=", rel, "kept"))
    for rel, (_old, _new, keys) in owned_changes(root, profile).items():
        out = [o for o in out if o[1] != rel]
        note = ("add extraKnownMarketplaces.zouj and enabledPlugins (nothing else)" if rel.endswith("settings.json")
                else "set " + ", ".join(f"{k}={json.dumps(v)}" for k, v in keys.items()))
        out.append(("~", rel, note))
    return out


def owned_changes(root, profile):
    """{rel: (old_text, new_text, keys)} for existing human-owned files the plan changes: only the profile's keys in
    .aiops/config.json, and only the two marketplace keys in .claude/settings.json (permissions, hooks and every
    other key keep their values)."""
    changes = {}
    f = root / ".aiops" / "config.json"
    cfg = _json(f)
    if cfg is not None:
        want = {k: v for k, v in PROFILE_CONFIG[profile].items() if cfg.get(k, config(root).get(k)) != v}
        if want:
            changes[".aiops/config.json"] = (f.read_text(), json.dumps({**cfg, **want}, indent=2) + "\n", want)
    f = root / ".claude" / "settings.json"
    settings = _json(f)
    if settings is not None:
        merged = _with_marketplace(settings)
        if merged != settings:                 # missing, or another source/ref (an older release, a fork)
            changes[".claude/settings.json"] = (f.read_text(), json.dumps(merged, indent=2) + "\n", MARKETPLACE)
    return changes


def _with_marketplace(settings):
    """settings with the official, pinned marketplace keys set; every other key is kept as it is."""
    merged = dict(settings)
    for key, value in MARKETPLACE.items():
        merged[key] = {**(merged.get(key) or {}), **value}
    return merged


OPTIONS = {"--profile": PROFILES, "--stack": cli.STACKS, "--dry-run": None, "--yes": None}   # option: its values


def parse(args):
    """({option: value, or True for a flag}, None), or (None, why) for an unknown option or value. The only parser:
    every later step reads its result, so a value can't also count as a flag."""
    opts, i = {}, 0
    while i < len(args):
        name = args[i]
        if name not in OPTIONS:
            return None, (f"unknown option {name!r}; setup takes --profile solo|team|strict, --stack python|node|go, "
                          "--dry-run and --yes")
        allowed = OPTIONS[name]
        if allowed is None:
            opts[name], i = True, i + 1
            continue
        if i + 1 == len(args):
            return None, f"{name} needs a value ({', '.join(allowed)})"
        if args[i + 1] not in allowed:
            return None, f"unknown {name[2:]} {args[i + 1]!r} ({', '.join(allowed)})"
        opts[name], i = args[i + 1], i + 2
    return opts, None


def main(root, args):
    opts, why = parse(args)
    if why:
        print(f"{why}. Nothing was written.", file=sys.stderr)
        return 1
    profile, dry_run, yes = opts.get("--profile"), "--dry-run" in opts, "--yes" in opts
    tty = _is_tty()
    if profile is None and not dry_run and not tty:
        print("setup needs choices and there's no terminal to ask them; nothing was written. Run again with:\n"
              "  sdlc setup --profile solo|team|strict --yes   (or --dry-run to preview)")
        return 2
    if profile is None and dry_run:
        profile = config(root)["profile"]
        if profile not in PROFILES:
            print(f".aiops/config.json has profile {profile!r}; it must be solo, team or strict. Fix it (human-owned) "
                  "or pass --profile; nothing was written.", file=sys.stderr)
            return 1
    if profile is None:
        profile = _ask_profile()
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
    owned = owned_changes(root, profile)
    if owned:                                     # shown before any confirmation (and in --dry-run)
        print("Changes to human-owned files" + (": the agent can't apply these, they become your human steps"
                                                 if approvals.running_under_agent() else ""))
        for rel, (old, new, _keys) in owned.items():
            print("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{rel}", f"b/{rel}"))
                  .rstrip("\n"))
    print(GATES.format(proof=PROOF[profile]))
    if any(mark == "✗" for mark, _, _ in actions):
        print("setup stops: a ✗ file in the plan has a symlink on its path; nothing was written.", file=sys.stderr)
        return 1
    if dry_run:
        print("dry run: nothing was written.")
        return 0
    if not any(mark in "+~" for mark, _, _ in actions):
        print("Already set up: nothing to write.")
        human_steps(root, profile, {})
        return 0
    if not yes and not (tty and _confirm()):
        print("not confirmed: nothing was written. Re-run with --yes to apply without the question."
              if tty else "no terminal to confirm: nothing was written. Re-run with --yes to apply.")
        return 2
    return apply(root, profile, actions, opts.get("--stack"))


def _is_tty():
    return sys.stdin.isatty()


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


def apply(root, profile, actions, stack=None):
    creates = [("create", rel) for mark, rel, _ in actions if mark == "+"]
    cli.apply_init(root, creates)
    created = {rel for _, rel in creates}
    if ".aiops/config.json" in created and not approvals.running_under_agent():
        # a human's new config takes the profile; the agent's is exactly init's, and the profile is a human step
        f = root / ".aiops" / "config.json"
        cli.write_file(root, ".aiops/config.json",
                       (json.dumps({**(_json(f) or {}), **PROFILE_CONFIG[profile]}, indent=2) + "\n").encode())
    if stack and "Makefile" in created:
        wired = cli._wire_stack(root, stack)
        print(f"Makefile: wired {', '.join(wired) or 'nothing'} from the {stack} preset")
    print("Applied")
    for rel in sorted(created):
        print(f"  + {rel}")
    pending = owned_changes(root, profile)
    if pending and not approvals.running_under_agent():  # a human confirmed this plan: apply it, showing each diff
        for rel, (_old, new, _keys) in pending.items():   # the diff was shown in the plan, before the question
            cli.write_file(root, rel, new.encode())
            print(f"  ~ {rel}")
        pending = {}
    human_steps(root, profile, pending)
    print("Doctor")
    cli.cmd_doctor(root, [])
    return 0


def human_steps(root, profile, pending):
    """What only the human can do: install the plugin, set up signing, own .aiops/, apply changes to human-owned
    files, commit, and start the first intent."""
    steps = ["In Claude Code (or just reopen Claude Code here: the project settings offer the plugin):\n"
             f"       /plugin marketplace add zoujagger/zouj-ai-sdlc@{REF}\n"
             "       /plugin install zouj-ai-sdlc@zouj"]
    if profile in ("team", "strict") and approvals.signing_problem(root):
        key = "~/.ssh/aiops_signing_sk" if profile == "strict" else "~/.ssh/aiops_signing"
        gen = (f"ssh-keygen -t ed25519-sk -f {key}            # a FIDO key: a touch for every approval"
               if profile == "strict" else f"ssh-keygen -t ed25519 -f {key}   # set a passphrase; keep it out of ssh-agent")
        steps.append("In your own terminal, set up approval signing:\n"
                     f"       {gen}\n"
                     "       git config --global gpg.format ssh\n"
                     f"       git config --global user.signingkey {key}.pub\n"
                     f"       echo \"$(git config user.email) namespaces=\\\"git\\\" $(cat {key}.pub)\" >> "
                     ".aiops/config/allowed-signers")
    if profile == "strict" and not cli.codeowners_cover_aiops(root):
        steps.append("Give /.aiops/ a real owner (strict requires it): in .github/CODEOWNERS replace the @your-org/... "
                     "placeholders, at least:\n       /.aiops/ @<approver>")
    for rel, (_old, _new, keys) in pending.items():   # under the agent: the human applies these
        snippet = json.dumps(keys, indent=2).replace("\n", "\n       ")
        steps.append(f"Change {rel} yourself (human-owned; setup run by the agent doesn't touch it), merging:\n"
                     f"       {snippet}")
    steps.append(f'Commit: git add -A && git commit -m "chore: adopt zouj-ai-sdlc (profile {profile})"')
    steps.append('Start the workflow: /zouj-ai-sdlc:intent "<your first need>"')
    print("Human steps")
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")
