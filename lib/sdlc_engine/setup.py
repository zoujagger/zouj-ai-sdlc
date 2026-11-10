"""`sdlc setup`: guided, rerunnable onboarding (preflight → inventory → plan → confirm → apply → human steps → doctor).

Profiles change only how strongly a human approval is proven; every profile runs the same playbook workflow
(docs/sdlc.md). External tools are looked up on PATH and run with a short timeout: a missing or hung `claude`/`gh`
becomes a warning, while missing git, make or python >= 3.9 stops setup before anything is written.
"""
import difflib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from . import approvals, cli
from . import artifacts as A
from .machine import config, git, initialized, intent_dirs

PROFILES = cli.PROFILES
TIMEOUT = 5


def _run(cmd, path, timeout, cwd=None):
    """Combined stdout+stderr of cmd with PATH=path, or None if it can't run or doesn't finish in time. stdin is
    closed: a tool never reads the human's terminal (a passphrase, a confirmation)."""
    exe = cmd[0] if os.path.isabs(cmd[0]) else shutil.which(cmd[0], path=path)
    if not exe:
        return None
    try:
        r = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=timeout, cwd=cwd,
                           stdin=subprocess.DEVNULL, env={**os.environ, "PATH": path})
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (r.returncode, (r.stdout or "") + (r.stderr or ""))


def _outside_repo(path, root):
    """PATH without its directories inside the repo (an activated .venv/bin, ./bin, a relative entry): the agent can
    write there, and preflight runs in the human's session."""
    real = Path(root).resolve()
    keep = [d for d in path.split(os.pathsep)
            if d and Path(d).resolve() != real and real not in Path(d).resolve().parents]
    return os.pathsep.join(keep)


def preflight(root, profile, version=None, path=None, timeout=TIMEOUT):
    """[(status, label, fix)] with status ✓ (ok), ! (warning, setup continues) or ✗ (setup stops)."""
    path = _outside_repo(path if path is not None else os.environ.get("PATH", ""), root)
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
        res = _run([approvals.GIT, "config", "--get-all", "credential.helper"], path, timeout, cwd=root)
        ok = bool(res and res[0] == 0 and res[1].strip())
        rows.append(("✓" if ok else "!", "git credential helper" + ("" if ok else " (git push over https will fail)"),
                     "" if ok else "gh auth setup-git (or configure any git credential helper)"))

    if profile in ("team", "strict"):
        rows += _signing_rows(root, profile)
    rows += owned_json_rows(root)
    return rows


OWNED_JSON = (".aiops/config.json", ".claude/settings.json")


def owned_json_rows(root):
    """✗ for an existing human-owned JSON file that doesn't parse, isn't an object, or has a marketplace key that
    isn't an object: setup would otherwise skip it silently (and read the default profile in its place) or fail on
    it. The human fixes it; setup never rewrites a file it can't read."""
    rows = []
    for rel in OWNED_JSON:
        f = root / rel
        if not f.is_file():
            continue
        fix = f"fix {rel} by hand (it's human-owned), then rerun"
        try:
            data = json.loads(f.read_text())
        except (OSError, ValueError) as exc:
            rows.append(("✗", f"{rel} isn't valid JSON ({exc})", fix))
            continue
        if not isinstance(data, dict):
            rows.append(("✗", f"{rel} isn't a JSON object (it holds a {type(data).__name__})", fix))
            continue
        for key in MARKETPLACE:
            if key in data and not isinstance(data[key], dict):
                rows.append(("✗", f"{rel}: {key} isn't a JSON object", fix))
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


CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def shown(text):
    """text with control characters (other than newline and tab) escaped: content setup didn't write is printed for the
    human to review, and terminal escapes in it must not hide or rewrite a line."""
    return CONTROL_RE.sub(lambda m: f"\\x{ord(m.group()):02x}", text)


def _text(path):
    return path.read_bytes().decode("utf-8", "replace")      # a planted file need not be UTF-8


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
    """The JSON object in path, or None (missing, invalid, or not an object; owned_json_rows reports those)."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


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


def _uncommitted(root, rel):
    """True if root/rel is not in HEAD as it is on disk (untracked, or changed since HEAD; no HEAD counts)."""
    return git(root, "ls-files", "--error-unmatch", "--", rel) is None or \
        git(root, "diff", "--quiet", "HEAD", "--", rel) is None


def _as_setup_writes(root, rel):
    """True if root/rel holds exactly what setup writes there: the scaffold template (release-pinned) or, for
    config.json, the template with one profile's keys. Setup's own files from an earlier run look like this."""
    try:
        data = (root / rel).read_bytes()
    except OSError:
        return False
    template = (cli.TEMPLATES / "scaffold" / rel).read_bytes().replace(cli.REF_PLACEHOLDER.encode(),
                                                                       f"v{cli.plugin_version()}".encode())
    if data == template:
        return True
    if rel != ".aiops/config.json":
        return False
    try:
        cfg = json.loads(data)
    except ValueError:
        return False
    return any(cfg == {**json.loads(template), **PROFILE_CONFIG[p]} for p in PROFILES)


def unreviewed(root):
    """Human-owned scaffold files that no commit has as they are, holding something setup doesn't write, or staged
    content that isn't on disk (git plumbing). The agent may have planted one while the guards were off (a key in
    allowed-signers would make CI trust it), so the human reviews them and they stay out of the commit setup suggests.
    "Committed" counts as reviewed: a file the agent committed before setup is a documented residual."""
    out = []
    for act, rel in cli.init_actions(root):
        if act != "keep" or not cli.HUMAN_OWNED_RE.match(rel) or not (root / rel).is_file():
            continue
        staged_off_disk = git(root, "diff", "--cached", "--quiet", "HEAD", "--", rel) is None and \
            git(root, "diff", "--quiet", "--", rel) is None
        if staged_off_disk or (_uncommitted(root, rel) and not _as_setup_writes(root, rel)):
            out.append(rel)
    return out


def uncommitted_scaffold(root):
    """Every scaffold file of the installed parts (and .gitignore) on disk that no commit has as it is: what the
    commit step lists. A file of a part that isn't installed is the user's own and is left out."""
    from . import lifecycle
    parts = lifecycle.installed_parts(root, lifecycle.load(root))
    rels = [rel for act, rel in cli.init_actions(root, parts=parts) if act != "symlink"] + [".gitignore"]
    return [rel for rel in rels if (root / rel).is_file() and _uncommitted(root, rel)]


def plan(root, profile, parts=None):
    """[(mark, rel, note)] for the scaffold files of core and the opt-in `parts` (None: every part): `+` create, `~`
    change (shown as a diff), `=` unchanged, `!` an existing human-owned file that no commit has (shown, for the
    human to review)."""
    out, review = [], unreviewed(root)
    for act, rel in cli.init_actions(root, parts=parts):
        if act == "symlink":
            out.append(("✗", rel, f"{cli.symlink_on_path(root, rel)} is a symlink: remove it, setup won't write through links"))
        elif act == "create":
            note = ""
            if rel == ".aiops/config.json":
                note = (f"init's defaults; profile {profile} becomes your human step"
                        if approvals.running_under_agent() else f"profile {profile}: {PROOF[profile]}")
            out.append(("+", rel, note))
        elif rel in review:
            out.append(("!", rel, "not in any commit yet, and not what setup writes: review it before committing"))
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
WITH = "--with"                               # its value is a list of opt-in parts (lifecycle.parse_parts)


def parse(args):
    """({option: value, or True for a flag}, None), or (None, why) for an unknown option or value. The only parser:
    every later step reads its result, so a value can't also count as a flag. `--with` holds the sorted part names."""
    from . import lifecycle
    opts, i = {}, 0
    while i < len(args):
        name = args[i]
        if name == WITH:
            parts, why = lifecycle.parse_parts(args[i + 1] if i + 1 < len(args) else "")
            if why:
                return None, why
            opts[name], i = sorted(set(opts.get(name, [])) | set(parts)), i + 2
            continue
        if name not in OPTIONS:
            return None, (f"unknown option {name!r}; setup takes --profile solo|team|strict, --stack python|node|go, "
                          f"--with {','.join(lifecycle.PARTS)} (or all), --dry-run and --yes")
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
    problem = cli.scaffold_root_problem(root)
    if problem:
        print(f"setup stops: {problem}. Nothing was written.", file=sys.stderr)
        return 1
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
    from . import lifecycle
    parts = lifecycle.installed_parts(root, lifecycle.load(root), opts.get(WITH, []))
    actions = plan(root, profile, parts)
    print("Plan")
    for mark, rel, note in actions:
        print(f"  {mark} {rel}" + (f"  ({note})" if note else ""))
    left_out = lifecycle.parts_line(parts)
    if left_out:
        print(f"  {left_out}")
    owned = owned_changes(root, profile)
    if owned:                                     # shown before any confirmation (and in --dry-run)
        print("Changes to human-owned files" + (": the agent can't apply these, they become your human steps"
                                                 if approvals.running_under_agent() else ""))
        for rel, (old, new, _keys) in owned.items():
            print(shown("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{rel}",
                                                     f"b/{rel}")).rstrip("\n")))
    review = unreviewed(root)
    if review:                                    # shown before any confirmation (and in --dry-run)
        print("Review before committing: human-owned, not in any commit yet, not what setup writes")
        for rel in review:
            template = (cli.TEMPLATES / "scaffold" / rel).read_text()
            print(shown("".join(difflib.unified_diff(template.splitlines(True), _text(root / rel).splitlines(True),
                                                     f"template/{rel}", rel)).rstrip("\n"))
                  or f"  (same as the template: {rel})")
    print(GATES.format(proof=PROOF[profile]))
    if any(mark == "✗" for mark, _, _ in actions):
        print("setup stops: a ✗ file in the plan has a symlink on its path; nothing was written.", file=sys.stderr)
        return 1
    if dry_run:
        print("dry run: nothing was written.")
        return 0
    agent = approvals.running_under_agent()
    if not any(mark in ("+" if agent else "+~") for mark, _, _ in actions):   # the agent never writes a ~ change
        print("Nothing for the agent to write: the ~ changes above are yours (see the human steps)." if agent and owned
              else "Already set up: nothing to write.")
        human_steps(root, profile, owned if agent else {}, review=review)
        return 0
    if not yes and not (tty and _confirm()):
        print("not confirmed: nothing was written. Re-run with --yes to apply without the question."
              if tty else "no terminal to confirm: nothing was written. Re-run with --yes to apply.")
        return 2
    return apply(root, profile, actions, opts.get("--stack"), review, parts)


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


def apply(root, profile, actions, stack=None, review=(), parts=None):
    creates = [("create", rel) for mark, rel, _ in actions if mark == "+"]
    created = {rel for _, rel in creates}
    written, changed, wired = [], [], None
    try:
        cli.apply_init(root, creates, written)
        if ".aiops/config.json" in created and not approvals.running_under_agent():
            # a human's new config takes the profile; the agent's is exactly init's, and the profile is a human step
            f = root / ".aiops" / "config.json"
            cli.write_file(root, ".aiops/config.json",
                           (json.dumps({**(_json(f) or {}), **PROFILE_CONFIG[profile]}, indent=2) + "\n").encode())
        if stack and "Makefile" in created:
            wired = cli._wire_stack(root, stack)
        from . import lifecycle
        pending = owned_changes(root, profile)
        if pending and not approvals.running_under_agent():  # a human confirmed this plan: apply it
            for rel, (_old, new, _keys) in pending.items():   # the diff was shown in the plan, before the question
                cli.write_file(root, rel, new.encode())
                written.append(rel)
                changed.append(rel)
            pending = {}
        lifecycle.record(root, written, profile=profile, stack=stack, parts=parts)
    except OSError as exc:
        print(cli.write_failure(exc, written), file=sys.stderr)
        return 1
    if wired is not None:
        print(f"Makefile: wired {', '.join(wired) or 'nothing'} from the {stack} preset")
    print("Applied")
    for rel in sorted(created):
        print(f"  + {rel}")
    for rel in changed:
        print(f"  ~ {rel}")
    human_steps(root, profile, pending, review)
    print("Doctor")
    cli.cmd_doctor(root, [])
    return 0


def human_steps(root, profile, pending, review=()):
    """Print what only the human can do: install the plugin, set up signing, own .aiops/, apply changes to
    human-owned files, commit, and start the first intent."""
    print("Human steps")
    for i, step in enumerate(steps_for_human(root, profile, pending, review), 1):
        print(f"  {i}. {step}")


def steps_for_human(root, profile, pending, review=(), install=True):
    """The human steps as a list. `install=False` leaves out installing the plugin (it is already running: the
    prompt hook's reply)."""
    steps = ["In Claude Code (or just reopen Claude Code here: the project settings offer the plugin):\n"
             f"       /plugin marketplace add zoujagger/zouj-ai-sdlc@{REF}\n"
             "       /plugin install zouj-ai-sdlc@zouj"] if install else []
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
        if rel == ".aiops/config.json":
            current = config(root)["profile"]
            command = f"{shlex.quote(str(cli.PLUGIN_ROOT / 'bin' / 'sdlc'))} setup --profile {profile}"
            if current in PROFILES and PROFILES.index(profile) < PROFILES.index(current):   # solo < team < strict
                steps.append(f"Downgrade requested by the agent's run ({current} to {profile}): approvals would be "
                             f"proven by {PROOF[profile]} instead of {PROOF[current]}. Skip the next step unless you "
                             "asked for it.")
            if no_profile_yet(root)[0]:           # the repo's first profile: the human's typed phrase sets it
                steps.append(f"Choose the profile: type `Setup Profile {profile}` as your whole prompt in Claude "
                             "Code (.aiops/config.json is human-owned; setup run by the agent leaves it at init's "
                             "defaults). The phrase sets these keys and commits the file alone:\n"
                             f"       {snippet}\n"
                             f"       Or run in your own terminal, then confirm the diff: {command}")
            else:
                steps.append(f"Apply profile {profile} in your own terminal (.aiops/config.json is human-owned; setup "
                             f"run by the agent leaves it as it is). Run, then confirm the diff:\n"
                             f"       {command}\n"
                             f"       It sets:\n       {snippet}")
        else:
            steps.append(f"Change {rel} yourself (human-owned; setup run by the agent doesn't touch it), merging:\n"
                         f"       {snippet}")
    if review:                                    # unreviewed(), taken before setup wrote anything
        steps.append("Review these human-owned files yourself before committing them (no commit has them yet, and they "
                     "hold something setup doesn't write; an unexpected key in allowed-signers would let CI trust it):"
                     "\n       "
                     + "\n       ".join(review))
    files = sorted(set(uncommitted_scaffold(root)) - set(review))
    if files:                                     # exactly these paths: never `git add -A`, never the rest of the index
        paths = " ".join(shlex.quote(f) for f in files)
        steps.append(f"Commit the scaffold:\n       git add -- {paths} && git commit -m \"chore: adopt zouj-ai-sdlc "
                     f"(profile {config(root)['profile']})\" -- {paths}")
    steps.append('Start the workflow: /zouj-ai-sdlc:intent "<your first need>"')
    return steps


# ---------------------------------------------------------------- the first profile, set by a typed phrase

def no_profile_yet(root):
    """(True, "") while this repo has no profile and nothing depends on one, else (False, why). That is when the
    human's typed phrase `Setup Profile <name>` may set the first profile:
    - .aiops/config.json is a regular file that still equals the scaffold template (no `profile` key, nothing edited)
    - no artifact is Approved or Closed: no gate has been opened under the default yet.
    Changing a profile later, a downgrade included, is a run in the human's own terminal."""
    from . import lifecycle
    f = root / ".aiops" / "config.json"
    if f.is_symlink():
        return False, ".aiops/config.json is a symlink; a profile is written only to a regular file"
    if not f.is_file():
        return False, "there is no .aiops/config.json to set it in (run /zouj-ai-sdlc:setup first)"
    written = lifecycle.config_written(root)
    if written:
        return False, f"a profile is already set here ({written})"
    if written is None:
        current = _json(f) or {}
        if current.get("profile"):
            return False, f"a profile is already set here ({current['profile']})"
        return False, ".aiops/config.json was edited after setup (it no longer equals the scaffold template)"
    for d in intent_dirs(root):
        for kind in ("intent", "spec", "plan"):
            art = d / f"{kind}.md"
            if not art.is_file():
                continue
            status = A.parse(art.read_text()).get("status")
            if status in ("Approved", "Closed"):
                return False, (f".aiops/{d.name}/{kind}.md is already {status}: a gate has been opened under the "
                               "default profile, so changing it now is a deliberate change")
    return True, ""


def set_first_profile(root, name):
    """(ok, message) for the human's typed phrase `Setup Profile <name>` (the prompt hook calls this in-process, as
    it does approvals.approve). Sets this repo's first profile: writes the template's keys plus the profile's into
    .aiops/config.json, exactly what a terminal `sdlc setup --profile <name>` writes into a new config, and commits
    that file alone, unsigned. Never changes a profile that is set (no_profile_yet)."""
    from . import lifecycle
    if name not in PROFILES:
        return False, (f"profile NOT set: {f'unknown profile {name!r}' if name else 'no profile was named'}. The "
                       "human types `Setup Profile solo`, `Setup Profile team` or `Setup Profile strict` as the "
                       "whole prompt.")
    if not initialized(root):
        return False, "profile NOT set: this repo isn't set up yet (no .aiops/). Run /zouj-ai-sdlc:setup first."
    ok, why = no_profile_yet(root)
    if not ok:
        return False, (f"profile NOT set: {why}. The typed phrase only sets a repo's first profile. To change one, "
                       f"the human runs in their own terminal: `{lifecycle.human_command(f'setup --profile {name}')}`.")
    rel = ".aiops/config.json"
    template = json.loads((cli.TEMPLATES / "scaffold" / rel).read_text())
    try:
        cli.write_file(root, rel, (json.dumps({**template, **PROFILE_CONFIG[name]}, indent=2) + "\n").encode())
    except OSError as exc:
        return False, f"profile NOT set: {rel} could not be written ({exc}). Nothing changed."
    title = f"chore(aiops): Setup Profile {name}"
    done = approvals._commit_alone(root, rel, title, f"AIOps-Profile: {name}\nSet-By: {approvals.approver(root)}", [])
    if done is None:
        note = f"The change is in the working tree, but committing it failed: commit it yourself ({rel}, alone)."
    else:
        note = f"Committed alone as `{title}`." + (f" The index was busy and still holds the old file: run "
                                                    f"`{done[1]}` before your next commit." if done[1] else "")
    steps = steps_for_human(root, name, {}, install=False)
    return True, (f"profile SET: {name}. From now on an approval is proven by {PROOF[name]}. {note}\n"
                  "Relay the remaining human steps:\n"
                  + "\n".join(f"  {i}. {step}" for i, step in enumerate(steps, 1)))
