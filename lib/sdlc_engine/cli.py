"""`sdlc`: the zouj-ai-sdlc state engine. Run `sdlc help` for commands.

Exit codes: 0 ok · 1 error or validation failure · 2 hook block (PreToolUse/PostToolUse feed stderr to Claude).
"""
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

from . import approvals, guards
from . import artifacts as A
from .machine import (KINDS, PLUGIN_ROOT, SCHEMAS, active_dir, evaluate, find_dir, git, initialized, intent_dirs,
                      project_root)
from .schema import validate

TEMPLATES = PLUGIN_ROOT / "templates"
APPROVE_RE = re.compile(r"^\s*(intent|spec|plan)\s+approved(?:\s+(\d{1,4}))?\s*[.!]?\s*$", re.I)
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HUMAN_ONLY = "refusing: this is a human gate and it is running inside Claude Code. Run it in your own terminal, " \
             "or type the approval phrase (e.g. `Plan Approved 0001`) in the Claude prompt."

USAGE = """usage: sdlc <command> [args]

Lifecycle (any user or agent)
  status [id] [--json]       state card for an intent (default: active), or a table of all intents
  next [id]                  the exact next step
  new <slug> [--title T]     state 1: create .aiops/NNNN-slug/intent.md (Draft) and make it active
  draft <id> spec|plan|review  create the next artifact from its template (only when its input is approved)
  use <id>                   make an intent the active one (branch names feat/NNNN-* win over this)
  validate [id] [--all] [--ci]  check artifacts against schemas/; --ci also audits approval commits
  lock                       /fix: lock test files after the human approved the failing test
  init [--stack python|node|go] [--force]   scaffold this repo (.aiops/, Makefile contract, CI, REVIEW.md)
  doctor                     check tools and wiring

Human only (refused inside Claude Code)
  approve <id> intent|spec|plan   open a gate (same as typing `Plan Approved NNNN` in the prompt)
  close <id>                 close an intent without implementing it
  unlock                     release the /fix test lock
"""


def out(msg, stream=sys.stdout):
    print(msg, file=stream)


def _root():
    return project_root()


def _need_init(root):
    if not initialized(root):
        out(f"{root} is not initialized for zouj-ai-sdlc. Run: sdlc init", sys.stderr)
        sys.exit(1)


def _resolve(root, ident):
    d = find_dir(root, ident) if ident else active_dir(root)
    if d is None:
        out(f"no intent {ident!r} in .aiops/" if ident else
            "no active intent (branch feat/NNNN-*, `sdlc use NNNN`, or $AIOPS_INTENT). Try: sdlc status", sys.stderr)
        sys.exit(1)
    return d


def card(root, st):
    gates = " · ".join(f"{k} {'✓' if v else '…'}" for k, v in st.gates.items())
    branch = git(root, "branch", "--show-current") or "detached"
    mode = {1: " (read-only)", 2: " (read-only)", 3: " (read-only)", 4: " (autonomous)", 5: " (final human gate)"}
    return "\n".join([
        f"## zouj-ai-sdlc · intent {st.dir.name} · branch {branch}",
        f"- State: {st.state} {st.name}{mode.get(st.state, '')}: {st.detail}",
        f"- Gates: {gates} · Steps: {st.steps_done}/{st.steps_total} · Deviations: {st.deviations}"
        f" · Open questions: {st.open_questions}",
        f"- Waiting on: {st.waiting_on} · Next: {st.next}",
    ])


def cmd_status(root, args):
    _need_init(root)
    as_json = "--json" in args
    ids = [a for a in args if not a.startswith("--")]
    if ids or active_dir(root):
        st = evaluate(root, _resolve(root, ids[0] if ids else None))
        out(json.dumps(st.as_dict(), indent=2) if as_json else card(root, st))
        return 0
    rows = [evaluate(root, d) for d in intent_dirs(root)]
    if as_json:
        out(json.dumps([r.as_dict() for r in rows], indent=2))
        return 0
    if not rows:
        out("No intents yet. Start one: /zouj-ai-sdlc:intent \"<need>\"  (or: sdlc new <slug>)")
        return 0
    out("| Intent | State | Detail | Next |\n|---|---|---|---|")
    for r in rows:
        out(f"| {r.dir.name} | {r.state} {r.name} | {r.detail} | {r.next} |")
    return 0


def cmd_next(root, args):
    _need_init(root)
    out(evaluate(root, _resolve(root, args[0] if args else None)).next)
    return 0


def _render(kind, ident, title):
    text = (TEMPLATES / "artifacts" / f"{kind}.md").read_text()
    return text.replace("NNNN", ident).replace("YYYY-MM-DD", datetime.date.today().isoformat()) \
               .replace("<Title>", title)


def _set_active(root, d):
    state = root / ".aiops" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "active").write_text(d.name[:4] + "\n")


def cmd_new(root, args):
    _need_init(root)
    if not args or not SLUG_RE.match(args[0]):
        out("usage: sdlc new <kebab-slug> [--title \"Title\"]", sys.stderr)
        return 1
    slug = args[0]
    title = args[args.index("--title") + 1] if "--title" in args[:-1] else slug.replace("-", " ").capitalize()
    last = max((int(d.name[:4]) for d in intent_dirs(root)), default=0)
    ident = f"{last + 1:04d}"
    d = root / ".aiops" / f"{ident}-{slug}"
    d.mkdir(parents=True)
    (d / "intent.md").write_text(_render("intent", ident, title))
    _set_active(root, d)
    out(f"Created .aiops/{d.name}/intent.md (Draft), now the active intent.\n"
        f"Suggested branch: git switch -c feat/{ident}-{slug}")
    return 0


def cmd_draft(root, args):
    _need_init(root)
    if len(args) < 2 or args[1] not in ("spec", "plan", "review"):
        out("usage: sdlc draft <id> spec|plan|review", sys.stderr)
        return 1
    d, kind = _resolve(root, args[0]), args[1]
    if (d / f"{kind}.md").exists():
        out(f".aiops/{d.name}/{kind}.md already exists")
        return 0
    req = SCHEMAS[kind]["requires"]
    ok, why = approvals.gate(d, req)
    if not ok:
        out(f"cannot draft {kind}.md: {req}.md is not approved ({why}).", sys.stderr)
        return 1
    title = A.parse((d / "intent.md").read_text()).get("title") or d.name[5:]
    (d / f"{kind}.md").write_text(_render(kind, d.name[:4], title))
    out(f"Created .aiops/{d.name}/{kind}.md from the template.")
    return 0


def cmd_use(root, args):
    _need_init(root)
    d = _resolve(root, args[0] if args else None)
    _set_active(root, d)
    out(f"Active intent: {d.name}")
    return 0


def cmd_validate(root, args):
    _need_init(root)
    ci = "--ci" in args
    ids = [a for a in args if not a.startswith("--")]
    dirs = intent_dirs(root) if "--all" in args or not ids and not active_dir(root) else [_resolve(root, ids[0] if ids else None)]
    failed = 0
    for d in dirs:
        for kind in KINDS:
            if not (d / f"{kind}.md").exists():
                continue
            errors, warnings = validate(d, kind)
            if ci and kind != "review":
                errors += approvals.audit(root, d, kind)
            for e in errors:
                out(f"✗ .aiops/{d.name}/{kind}.md: {e}")
            for w in warnings:
                out(f"! .aiops/{d.name}/{kind}.md: {w}")
            failed += bool(errors)
    out(f"validate: {len(dirs)} intent(s), {failed} artifact(s) with errors")
    return 1 if failed else 0


def cmd_approve(root, args):
    if approvals.running_under_agent():
        out(HUMAN_ONLY, sys.stderr)
        return 1
    _need_init(root)
    if len(args) < 2 or args[1] not in ("intent", "spec", "plan"):
        out("usage: sdlc approve <id> intent|spec|plan", sys.stderr)
        return 1
    ok, msg = approvals.approve(root, _resolve(root, args[0]), args[1], via="cli")
    out(msg, sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def cmd_close(root, args):
    if approvals.running_under_agent():
        out(HUMAN_ONLY, sys.stderr)
        return 1
    _need_init(root)
    ok, msg = approvals.close(root, _resolve(root, args[0] if args else None))
    out(msg)
    return 0 if ok else 1


def cmd_lock(root, args):
    _need_init(root)
    state = root / ".aiops" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "test-lock").write_text(datetime.datetime.now().isoformat() + "\n")
    out("Test lock set: test files are read-only until `make check` is green (the Stop hook releases it).")
    return 0


def cmd_unlock(root, args):
    if approvals.running_under_agent():
        out(HUMAN_ONLY, sys.stderr)
        return 1
    (root / ".aiops" / "state" / "test-lock").unlink(missing_ok=True)
    out("Test lock released.")
    return 0


def _wire_stack(makefile, stack):
    recipes = {}
    for line in (TEMPLATES / "stacks" / f"{stack}.recipes").read_text().splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and not parts[0].startswith("#"):
            recipes[parts[0]] = parts[1]
    src, wired = makefile.read_text(), []
    for target, cmd in recipes.items():
        src, n = re.subn(rf'^\t@echo "\[{target}\] not configured - edit Makefile"$', "\t" + cmd.replace("\\", "\\\\"),
                         src, flags=re.M)
        if n:
            wired.append(target)
    makefile.write_text(src)
    return wired


def cmd_init(root, args):
    stack = args[args.index("--stack") + 1] if "--stack" in args[:-1] else None
    force = "--force" in args
    if stack and not (TEMPLATES / "stacks" / f"{stack}.recipes").is_file():
        out(f"unknown stack {stack!r} (python, node, go)", sys.stderr)
        return 1
    scaffold = TEMPLATES / "scaffold"
    created, skipped = [], []
    for src in sorted(p for p in scaffold.rglob("*") if p.is_file()):
        rel = src.relative_to(scaffold)
        dst = root / rel
        if dst.exists() and not force:
            skipped.append(str(rel))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        created.append(str(rel))
    for p in (root / ".aiops" / "state",):
        p.mkdir(parents=True, exist_ok=True)
    if stack and "Makefile" in created:
        wired = _wire_stack(root / "Makefile", stack)
        out(f"Makefile: wired {', '.join(wired) or 'nothing'} from the {stack} preset")
    gi = root / ".gitignore"
    lines = gi.read_text().splitlines() if gi.exists() else []
    if ".aiops/state/" not in lines:
        gi.write_text("\n".join(lines + ["", "# zouj-ai-sdlc engine state (active intent, test lock)", ".aiops/state/"])
                      .lstrip("\n") + "\n")
    out("Created:\n  " + ("\n  ".join(created) or "(nothing)"))
    if skipped:
        out("Kept existing (compare with the plugin's templates/scaffold/ or re-run with --force):\n  "
            + "\n  ".join(skipped))
    out("""
zouj-ai-sdlc is now active in this repo. Next:
  1. Wire the Makefile contract (format/lint/typecheck/test/build), or re-run with --stack python|node|go.
  2. Optional, for an unattended state 4: add the allow-rules from .aiops/README.md to .claude/settings.json.
  3. Commit the scaffold, then start: /zouj-ai-sdlc:intent "<your first need>".""")
    return 0


def cmd_doctor(root, args):
    fail = 0

    def row(ok, msg, fix=""):
        nonlocal fail
        out(f"  {'✓' if ok else '✗'} {msg}" + ("" if ok or not fix else f"\n      fix: {fix}"))
        fail |= not ok

    for b in ("git", "make", "python3"):
        row(shutil.which(b) is not None, b, "see README → Prerequisites")
    row(sys.version_info >= (3, 9), f"python {sys.version.split()[0]} (>= 3.9)", "upgrade python3")
    row(initialized(root), f"{root} initialized (.aiops/)", "sdlc init")
    if initialized(root) and (root / "Makefile").exists():
        mk = (root / "Makefile").read_text()
        unwired = [t for t in ("format", "lint", "typecheck", "test", "build") if f'"[{t}] not configured' in mk]
        row(not unwired, "Makefile contract wired" + (f" (not: {', '.join(unwired)})" if unwired else ""),
            "edit the Makefile or: sdlc init --stack python|node|go --force")
    for b in ("gh", "jq"):
        out(f"  {'✓' if shutil.which(b) else '!'} {b} (optional)")
    if initialized(root):
        for d in intent_dirs(root):
            for kind in KINDS:
                if (d / f"{kind}.md").exists():
                    errs, _ = validate(d, kind)
                    row(not errs, f".aiops/{d.name}/{kind}.md valid", "; ".join(errs[:2]))
    out("doctor: " + ("problems found (✗)" if fail else "ready"))
    return 1 if fail else 0


# ---------------------------------------------------------------- hooks (stdin = hook JSON)

def bootstrap_text():
    skill = (PLUGIN_ROOT / "skills" / "using-zouj-ai-sdlc" / "SKILL.md").read_text()
    return A.parse(skill).body.strip()


def hook(event):
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}
    try:
        return HOOKS[event](data)
    except Exception as exc:  # noqa: BLE001: a guard that crashes must not silently allow
        if event in ("pre-edit", "pre-bash"):
            out(f"BLOCKED by zouj-ai-sdlc: the guard crashed ({type(exc).__name__}: {exc}), so it fails closed.\n"
                "Procedure: tell the human. They can fix the plugin or run /plugin disable zouj-ai-sdlc.", sys.stderr)
            return 2
        out(f"zouj-ai-sdlc {event} hook error: {exc}", sys.stderr)
        return 0


def _pre(check):
    def run(data):
        msg = check(data)
        if msg:
            out(msg, sys.stderr)
            return 2
        return 0
    return run


def hook_prompt(data):
    m = APPROVE_RE.match(data.get("prompt") or "")
    if not m:
        return 0
    root = project_root(data.get("cwd"))
    if not initialized(root):
        return 0
    kind, ident = m.group(1).lower(), m.group(2)
    d = find_dir(root, ident) if ident else active_dir(root)
    if d is None:
        msg = (f"zouj-ai-sdlc: the human typed an approval but no intent {ident or '(active)'} was found, so "
               "nothing was approved. Ask which intent they mean (e.g. `Plan Approved 0001`).")
    else:
        ok, msg = approvals.approve(root, d, kind, via="prompt")
        msg = f"zouj-ai-sdlc gate {'OPENED' if ok else 'NOT opened'}. {msg}"
    out(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": msg}}))
    return 0


def hook_session_start(data):
    root = project_root(data.get("cwd"))
    if not initialized(root):
        out("zouj-ai-sdlc is installed but this repo is not initialized (no .aiops/), so its gates are off here. "
            "To use the AI-native SDLC workflow: /zouj-ai-sdlc:init")
        return 0
    d = active_dir(root)
    status = card(root, evaluate(root, d)) if d else \
        f"## zouj-ai-sdlc · no active intent ({len(intent_dirs(root))} in .aiops/). Code is read-only until an " \
        "intent's plan is approved. Start: /zouj-ai-sdlc:intent"
    lockf = root / ".aiops" / "state" / "test-lock"
    if lockf.exists():
        status += "\n- ⚠️ Test lock active (/fix): test files are read-only until make check is green."
    if os.environ.get("SDLC_HOOK_PROFILE") == "spike":
        status += "\n- ⚠️ Spike profile: the read-only lock and make check are not enforced. Not for work headed to a PR."
    out(status + "\n\n" + bootstrap_text())
    return 0


def hook_post_edit(data):
    path = (data.get("tool_input") or {}).get("file_path") or ""
    root = project_root(data.get("cwd"))
    if not initialized(root):
        return 0
    try:
        rel = Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return 0
    m = guards.ARTIFACT_RE.match(rel)
    if not m:
        return 0
    errors, warnings = validate(root / ".aiops" / m.group(1), m.group(2))
    if errors:
        out(f"zouj-ai-sdlc: {rel} does not validate yet (fix before asking for approval):\n- "
            + "\n- ".join(errors + warnings), sys.stderr)
        return 2
    return 0


HOOKS = {"pre-edit": _pre(guards.check_edit), "pre-bash": _pre(guards.check_bash), "prompt": hook_prompt,
         "session-start": hook_session_start, "post-edit": hook_post_edit}

COMMANDS = {"status": cmd_status, "next": cmd_next, "new": cmd_new, "draft": cmd_draft, "use": cmd_use,
            "validate": cmd_validate, "approve": cmd_approve, "close": cmd_close, "lock": cmd_lock,
            "unlock": cmd_unlock, "init": cmd_init, "doctor": cmd_doctor}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("help", "-h", "--help"):
        out(USAGE)
        return 0
    if argv[0] == "hook":
        return hook(argv[1] if len(argv) > 1 else "")
    if argv[0] not in COMMANDS:
        out(f"unknown command {argv[0]!r}\n\n{USAGE}", sys.stderr)
        return 1
    return COMMANDS[argv[0]](_root(), argv[1:])
