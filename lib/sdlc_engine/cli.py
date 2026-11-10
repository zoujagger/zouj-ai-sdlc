"""`sdlc`: the zouj-ai-sdlc state engine. Run `sdlc help` for commands.

Exit codes: 0 ok · 1 error or validation failure · 2 hook block (PreToolUse/PostToolUse feed stderr to Claude).
"""
import datetime
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from . import approvals, guards
from . import artifacts as A
from .machine import (KINDS, PLUGIN_ROOT, SCHEMAS, active_dir, config, evaluate, find_dir, git, glob_hit, globs,
                      initialized, intent_dirs, project_root)
from .schema import validate

TEMPLATES = PLUGIN_ROOT / "templates"
APPROVE_RE = re.compile(r"^\s*(intent|spec|plan)\s+approved(?:\s+(\d{1,4}))?\s*[.!]?\s*$", re.I)
# The human's whole prompt `Setup Profile solo|team|strict` sets a repo's first profile (setup.set_first_profile).
PROFILE_RE = re.compile(r"^\s*setup\s+profile(?:\s+([a-z0-9_-]+))?\s*[.!]?\s*$", re.I)
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
  validate [id] [--all] [--ci] [--base REF]  check artifacts against schemas/; --ci also audits approval
                             commits (signers, legacy list and config read from REF when given)
  lock                       /fix: lock test files after the human approved the failing test
  init [--stack python|node|go] [--with PARTS] [--force]   scaffold this repo: the core files (.aiops/, Makefile
                             contract, CI audit, REVIEW.md), plus opt-in PARTS (review, maintain, deploy,
                             governance, issues, comma-separated, or all)
  setup [--profile solo|team|strict] [--stack S] [--with PARTS] [--dry-run] [--yes]   guided, rerunnable setup
  feedback                   issue links and a doctor summary to paste (sends nothing)
  list-installed             what the plugin installed here: current, stale, modified, missing, unmanaged
  repair [--dry-run] [--yes] restore missing managed files (never a modified one)
  upgrade [--dry-run] [--yes]  bring the scaffold to this plugin version: stale files replaced (diff shown),
                             modified ones kept except the CI ref, every ref pinned to a full sha, migrations listed
  why <id>                   explain a block (e.g. `sdlc why G-ENV-03`): reason, stage, safe alternative
  where                      print the sdlc command for your own terminal (the plugin's absolute path)
  doctor                     check tools and wiring

Human only (refused inside Claude Code)
  uninstall [--yes]          remove the plugin's unmodified scaffold files (never .aiops/NNNN-*); --dry-run: anyone
  approve <id> intent|spec|plan   open a gate (same as typing `Plan Approved NNNN` in the prompt)
  close <id>                 close an intent without implementing it
  unlock                     release the /fix test lock
  legacy-approvals [--write [--yes]]  list (or record, confirming each) pre-signing approvals on main as legacy
"""


def out(msg, stream=None):
    print(msg, file=stream or sys.stdout)   # looked up at call time, so redirect_stdout can capture it


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
        *terminal_lines(root, st),
    ])


def terminal_lines(root, st=None):
    """The card lines for a pending human step, [] when there is none:
    - no profile chosen yet: the command for the human's own terminal, and the phrase that sets the profile
    - the intent waits on the human at a gate (states 1-3) and signing needs a terminal: the approve command.
    signing_problem may run ssh-keygen, so it is asked only in that second case."""
    from . import lifecycle, setup
    if setup.no_profile_yet(root)[0]:
        return [f"- Your terminal: {lifecycle.human_command('').rstrip()}",
                "- No profile chosen yet: the human types `Setup Profile solo|team|strict` as the whole prompt"]
    if st is not None and st.waiting_on == "human" and st.state in (1, 2, 3) and approvals.signing_problem(root):
        return [f"- Your terminal: {approvals.approve_command(st.id, KINDS[st.state - 1])}"]
    return []


def cmd_where(root, args):
    """Print the sdlc command for the human's own terminal. `sdlc` is on PATH only inside Claude Code; the commands
    only a human may run need the plugin's absolute path. Reads nothing from the repo and starts no process."""
    from . import lifecycle
    if args:
        out("usage: sdlc where   (prints the sdlc command for your own terminal; it takes no arguments)", sys.stderr)
        return 1
    cmd = lifecycle.human_command("").rstrip()
    out(f"""{cmd}
Run it in your own terminal for the human-only commands (they are refused inside Claude Code):
  … setup --profile solo|team|strict     set or change how approvals are proven
  … approve <id> intent|spec|plan        open a gate (when signing needs your passphrase or key)
  … close <id>      … unlock      … legacy-approvals --write
  … uninstall --dry-run, then … uninstall""")
    return 0


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
    base = None
    if "--base" in args:
        i = args.index("--base")
        base = args[i + 1] if i + 1 < len(args) else ""
        if not base.strip():
            out("--base needs a commit or branch (the target branch: the trust anchor for signers)", sys.stderr)
            return 1
    ids = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--base")]
    trust_warnings = []
    dirs = intent_dirs(root) if "--all" in args or not ids and not active_dir(root) else [_resolve(root, ids[0] if ids else None)]
    failed = 0
    for d in dirs:
        for kind in KINDS:
            if not (d / f"{kind}.md").exists():
                continue
            errors, warnings = validate(d, kind)
            if ci and kind != "review":
                errors += approvals.audit(root, d, kind, base=base, warnings=trust_warnings)
            for e in errors:
                out(f"✗ .aiops/{d.name}/{kind}.md: {e}")
            for w in warnings:
                out(f"! .aiops/{d.name}/{kind}.md: {w}")
            failed += bool(errors)
    for w in dict.fromkeys(trust_warnings):
        out(f"! {w}")
    if ci:
        failed += _allowance_errors(root, base)
    out(f"validate: {len(dirs)} intent(s), {failed} artifact(s) with errors")
    return 1 if failed else 0


def _allowance_errors(root, base):
    """CI: refused allowed-commands entries (rules.allowance_problems), in the change itself and, with --base, on
    the target branch. The hooks ignore such entries; CI makes them visible before and after the merge."""
    from . import rules
    f = root / rules.ALLOWANCES
    if f.is_symlink():
        out(f"✗ {rules.ALLOWANCES} is a symlink; it must be a regular file (the hooks ignore it)")
        return 1
    sources = [(rules.ALLOWANCES, f.read_text() if f.is_file() else None)]
    if base:
        sources.append((f"{base}:{rules.ALLOWANCES}", git(root, "show", f"{base}:{rules.ALLOWANCES}")))
    n = 0
    for where, text in sources:
        for p in rules.allowance_problems(text or ""):
            out(f"✗ {where}: {p}")
            n += 1
    return n


def _confirm(question):
    print(question, end="", flush=True)
    try:
        return input().strip().lower() in ("y", "yes")
    except EOFError:
        print()
        return False


def cmd_legacy_approvals(root, args):
    """Human-only migration aid: unsigned approval commits that predate signing become an explicit legacy list."""
    if approvals.running_under_agent():
        out(HUMAN_ONLY, sys.stderr)
        return 1
    _need_init(root)
    found = approvals.unsigned_approvals(root)
    for sha, what in found:
        who = git(root, "log", "-1", "--format=%an <%ae> %ad", "--date=short", sha)
        out(f"{sha}  {what}  ({who})")
    if not found:
        out("No unsigned approvals of open gates.")
    if "--write" in args and found:
        f = root / approvals.LEGACY
        f.parent.mkdir(parents=True, exist_ok=True)
        known = f.read_text() if f.is_file() else "# Unsigned approval commits accepted by the audit (human-owned, append-only).\n"
        new = [f"{sha}  # {what}" for sha, what in found if sha not in known and ("--yes" in args or _confirm(
            f"Record {sha[:10]} ({what}) as a legacy approval? [y/N] "))]
        f.write_text(known.rstrip("\n") + "\n" + "".join(f"{ln}\n" for ln in new))
        out(f"Recorded {len(new)} commit(s) in {approvals.LEGACY}. Commit it; CI reads it from the base branch.")
    return 0


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


def wire(src, stack, recipes_text=None):
    """(src, wired targets): the Makefile text with the stack preset's recipes in place of the stubs. recipes_text
    defaults to the running plugin's preset (scripts/scaffold-history.py passes a release's)."""
    recipes = {}
    if recipes_text is None:
        recipes_text = (TEMPLATES / "stacks" / f"{stack}.recipes").read_text()
    for line in recipes_text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and not parts[0].startswith("#"):
            recipes[parts[0]] = parts[1]
    wired = []
    for target, cmd in recipes.items():
        src, n = re.subn(rf'^\t@echo "\[{target}\] not configured - edit Makefile"$', "\t" + cmd.replace("\\", "\\\\"),
                         src, flags=re.M)
        if n:
            wired.append(target)
    return src, wired


def _wire_stack(root, stack):
    src, wired = wire((root / "Makefile").read_text(), stack)
    write_file(root, "Makefile", src.encode())
    return wired


REF_PLACEHOLDER = "__ZOUJ_SDLC_REF__"
PROFILES = ("solo", "team", "strict")
STACKS = ("python", "node", "go")             # the presets in templates/stacks/; --stack takes only these names


def plugin_version():
    return json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]


# Scaffold files that, once they exist, belong to the human: the approval proof, the signer and guard lists, Claude
# Code settings, code ownership and CI. `--force` never overwrites them when the agent runs it.
HUMAN_OWNED_RE = re.compile(r"^(\.aiops/config(\.json$|/)|\.claude/|(\.github/|docs/)?CODEOWNERS$|\.github/workflows/)")


GIT_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")   # each can fake a repo top


def scaffold_root_problem(root):
    """Why init/setup must not scaffold root, else None. Only the top of a git work tree is scaffolded (no fallback to
    the current directory), and never the home directory, ~/.claude or a toolchain path (shell startup, PATH,
    installed plugins): files there run, or load, in every session of the human's. git's location variables are
    refused: they would make any directory look like the top of a repo."""
    pointed = [v for v in GIT_LOCATION_VARS if os.environ.get(v)]
    if pointed:
        return (f"{', '.join(pointed)} {'is' if len(pointed) == 1 else 'are'} set, which points git at another "
                "repository or work tree; unset it and run from the repo itself")
    top = git(root, "rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != root.resolve():
        return f"{root} is not the top of a git repository; run `git init` there first (init and setup write only inside a repo)"
    here = git(Path.cwd(), "rev-parse", "--show-toplevel")
    if not here or Path(here).resolve() != root.resolve():        # CLAUDE_PROJECT_DIR named another repo
        return (f"CLAUDE_PROJECT_DIR points at {root}, not at the repo you're in ({here or Path.cwd()}); init and "
                "setup scaffold only the repo they run in: cd there, or unset CLAUDE_PROJECT_DIR")
    real, homes = root.resolve(), {Path.home().resolve()}         # $HOME can be set, so the account record too
    try:
        homes.add(Path(pwd.getpwuid(os.getuid()).pw_dir).resolve())
    except KeyError:                                                # a uid with no passwd entry (containers)
        pass
    for home in homes:
        if real == home:
            return f"{real} is your home directory; scaffold a project repo instead"
        if real == home / ".claude" or home / ".claude" in real.parents:
            return f"{real} is inside ~/.claude (Claude Code's own settings and plugins); scaffold a project repo instead"
    if guards._toolchain_path(real, real):
        return f"{real} is a toolchain path (PATH, shell startup or installed plugins); scaffold a project repo instead"
    return None


def symlink_on_path(root, rel):
    """The first of rel's path components below root that is a symlink (as a relative path), else None."""
    p = root
    for part in Path(rel).parts:
        p = p / part
        if p.is_symlink():
            return str(p.relative_to(root))
        if not p.exists():
            return None
    return None


def write_file(root, rel, data, mode=0o644):
    """Write data to root/rel without following a link: each directory is opened relative to its parent with
    O_NOFOLLOW, and the file is removed and created anew (O_EXCL), so neither a symlink (anywhere on the path) nor a
    hard link is written through. Raises OSError instead."""
    *dirs, name = Path(rel).parts
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in dirs:
            try:
                os.mkdir(part, 0o755, dir_fd=fd)
            except FileExistsError:
                pass
            sub = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = sub
        try:
            if stat.S_ISLNK(os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode):
                raise OSError(f"{rel} is a symlink; refusing to write through it")
            os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            pass
        with os.fdopen(os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=fd), "wb") as f:
            f.write(data)
    finally:
        os.close(fd)


def _agent_blocked(root, rel):
    """True if the guards would block the agent's own Write of root/rel: `init --force` run by the agent may not reset
    more than the agent could write itself. That is two hooks' rules: check_edit (engine paths, artifacts, the
    read-only lock) and guard-files.sh (protected-paths, default and the repo's, and secret-paths)."""
    if glob_hit(rel, globs(root, "protected-paths")):
        return True
    if not guards._secret_template(rel) and glob_hit(rel, globs(root, "secret-paths")):
        return True
    return guards.check_edit({"tool_name": "Write", "cwd": str(root),
                              "tool_input": {"file_path": str(root / rel), "content": ""}}) is not None


def _agent_blocked_now(root, rel):
    """_agent_blocked, judged without the lock env the agent's own command could set (0005, gap 5)."""
    from .machine import lock_env_stripped
    with lock_env_stripped():
        return _agent_blocked(root, rel)


def init_actions(root, force=False, agent=False, parts=None):
    """[(action, rel)] for every scaffold file (with `parts`, only core and those opt-in parts): "create" (missing,
    or --force) or "keep" (exists). Under the agent, --force keeps existing human-owned files, and any file the guard
    won't let the agent write ("owned"). A file with a symlink on its path is "symlink" (init refuses to run). Writes
    nothing, so `sdlc setup` can preview exactly what `init` will do."""
    from . import lifecycle
    out = []
    for rel in lifecycle.scaffold_paths(parts):
        if symlink_on_path(root, rel):
            out.append(("symlink", rel))
        elif not (root / rel).exists():
            out.append(("create", rel))
        elif force and agent and (HUMAN_OWNED_RE.match(rel) or _agent_blocked_now(root, rel)):
            out.append(("owned", rel))
        else:
            out.append(("create" if force else "keep", rel))
    if symlink_on_path(root, ".gitignore"):
        out.append(("symlink", ".gitignore"))
    return out


def symlink_refusal(root, actions):
    """The refusal message when init would write through a symlink, else None."""
    links = [f"{rel} ({symlink_on_path(root, rel)} is a symlink)" for act, rel in actions if act == "symlink"]
    return ("refusing to write through symlinks; init writes only regular files inside this repo. Remove these links "
            "and run again. Nothing was written:\n  " + "\n  ".join(links)) if links else None


def write_failure(exc, written):
    """The message for a write that failed part-way: what failed, and what had already been written."""
    return (f"✗ {exc}. Files written before the error: {', '.join(written) or 'none'}. Nothing else was written; fix "
            "the cause and run again.")


def apply_init(root, actions, written=None):
    """Copy the "create" files of init_actions() into root, pinning consumer CI to this plugin's release. Each file
    written is appended to `written`, so a caller can report them if a later write fails."""
    written = [] if written is None else written
    scaffold = TEMPLATES / "scaffold"
    for act, rel in actions:
        if act != "create":
            continue
        data = (scaffold / rel).read_bytes()
        if REF_PLACEHOLDER.encode() in data:
            data = data.replace(REF_PLACEHOLDER.encode(), f"v{plugin_version()}".encode())
        write_file(root, rel, data, (scaffold / rel).stat().st_mode & 0o777)
        written.append(rel)
    if symlink_on_path(root, ".aiops/state"):
        raise OSError(".aiops/state is behind a symlink; refusing to create it")
    (root / ".aiops" / "state").mkdir(parents=True, exist_ok=True)
    gi = root / ".gitignore"
    lines = gi.read_text().splitlines() if gi.is_file() and not gi.is_symlink() else []
    if ".aiops/state/" not in lines:
        write_file(root, ".gitignore", ("\n".join(lines + ["", "# zouj-ai-sdlc engine state (active intent, test lock)",
                                                           ".aiops/state/"]).lstrip("\n") + "\n").encode())
        written.append(".gitignore")


def cmd_init(root, args):
    stack = args[args.index("--stack") + 1] if "--stack" in args[:-1] else None
    force = "--force" in args
    if stack and stack not in STACKS:
        out(f"unknown stack {stack!r} (python, node, go)", sys.stderr)
        return 1
    from . import lifecycle
    requested = []
    if "--with" in args:
        i = args.index("--with")
        requested, why = lifecycle.parse_parts(args[i + 1] if i + 1 < len(args) else "")
        if why:
            out(f"{why}. Nothing was written.", sys.stderr)
            return 1
    problem = scaffold_root_problem(root)
    if problem:
        out(f"refusing: {problem}. Nothing was written.", sys.stderr)
        return 1
    parts = lifecycle.installed_parts(root, lifecycle.load(root), requested)
    actions = init_actions(root, force, agent=approvals.running_under_agent(), parts=parts)
    refusal = symlink_refusal(root, actions)
    if refusal:
        out(refusal, sys.stderr)
        return 1
    written = []
    try:
        apply_init(root, actions, written)
    except OSError as exc:
        out(write_failure(exc, written), sys.stderr)
        return 1
    created = [rel for act, rel in actions if act == "create"]
    skipped = [rel for act, rel in actions if act == "keep"]
    owned = [rel for act, rel in actions if act == "owned"]
    if owned:
        out("Human-owned or locked, not reset (init --force was run by the agent). To reset them, the human runs "
            "`sdlc init --force` in your own terminal:\n  " + "\n  ".join(owned))
    if stack and "Makefile" in created:
        wired = _wire_stack(root, stack)
        out(f"Makefile: wired {', '.join(wired) or 'nothing'} from the {stack} preset")
    try:
        lifecycle.record(root, written, stack=stack, parts=parts)
    except OSError as exc:
        out(write_failure(exc, written), sys.stderr)
        return 1
    out("Created:\n  " + ("\n  ".join(created) or "(nothing)"))
    if skipped:
        out("Kept existing (compare them with the plugin's templates/scaffold/):\n  "
            + "\n  ".join(skipped))
    left_out = lifecycle.parts_line(parts, "init")
    if left_out:
        out(left_out)
    out("""
zouj-ai-sdlc is now active in this repo. Next:
  1. Wire the Makefile contract (format/lint/typecheck/test/build): copy the recipes from the plugin's
     templates/stacks/<python|node|go>.recipes.
  2. Optional, for an unattended state 4: add the allow-rules from .aiops/README.md to .claude/settings.json.
  3. Commit the scaffold, then start: /zouj-ai-sdlc:intent "<your first need>".""")
    return 0


def _is_ssh_identity(private):
    cfg = Path.home() / ".ssh" / "config"
    return cfg.is_file() and private.name in cfg.read_text(errors="replace")


def _doctor_signing(root, row):
    problem = approvals.signing_problem(root)
    row(problem is None, "approval signing configured (ssh)" if problem is None else f"approval signing: {problem}",
        "git config --global gpg.format ssh && git config --global user.signingkey ~/.ssh/aiops_signing.pub "
        "(a dedicated key with a passphrase; repo-local signing settings are refused)")
    if problem:
        return
    key = git(root, "config", "user.signingkey") or ""
    pub = Path(key).expanduser()
    pubtext = pub.read_text().split() if pub.is_file() else key.split()
    signers = root / ".aiops" / "config" / "allowed-signers"
    listed = len(pubtext) >= 2 and signers.is_file() and pubtext[1] in signers.read_text()
    row(listed, "signing key is in .aiops/config/allowed-signers",
        "add `<email> namespaces=\"git\" <public key>` to .aiops/config/allowed-signers (human-owned) via a reviewed PR")
    private = pub.with_suffix("") if pub.suffix == ".pub" else None
    if private and private.is_file():
        probe = subprocess.run([approvals.SSH_KEYGEN, "-y", "-P", "", "-f", str(private)], capture_output=True, text=True)
        if probe.returncode == 0:
            out("  ! signing key has no passphrase: anything running as you could sign approvals. "
                "Add one (ssh-keygen -p) and keep it out of ssh-agent")
    if private and (private.name.startswith("id_") or _is_ssh_identity(private)):
        out("  ! signing key is also an SSH login identity: ssh (AddKeysToAgent) can load it into an agent that "
            "signs silently. Prefer a dedicated signing key")


CODEOWNERS_FILES = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")   # GitHub's lookup order
AIOPS_PATTERNS = {"*", "**", "/**", ".aiops", ".aiops/", ".aiops/*", ".aiops/**", "/.aiops", "/.aiops/", "/.aiops/*",
                  "/.aiops/**"}


def codeowners_cover_aiops(root):
    """True if the first CODEOWNERS file GitHub would read gives /.aiops/ an owner. The last matching rule wins, as on
    GitHub, so a later `/.aiops/` line without owners removes the coverage."""
    f = next((root / rel for rel in CODEOWNERS_FILES if (root / rel).is_file()), None)
    owned = False
    for line in (f.read_text(errors="replace").splitlines() if f else []):
        words = line.split("#", 1)[0].split()
        if words and words[0] in AIOPS_PATTERNS:
            owned = any(not w.startswith("@your-org/") for w in words[1:])   # the scaffold's placeholder isn't an owner
    return owned


ISSUES = "https://github.com/zoujagger/zouj-ai-sdlc/issues/new"


def cmd_feedback(root, args):
    """Where to report a problem or an idea, plus a doctor summary to paste. Prints only: nothing is sent anywhere."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_doctor(root, [])
    summary = buf.getvalue().replace(str(root), root.name).replace(str(Path.home()), "~")
    out(f"""zouj-ai-sdlc {plugin_version()}: feedback

  Install or runtime problem:  {ISSUES}?template=install-problem.yml
  Quick feedback (20 seconds): {ISSUES}?template=quick-feedback.yml
  Anything else:               {ISSUES}/choose

Paste this doctor summary into the issue (paths are reduced to the repo name):

{summary.rstrip()}

Nothing was sent: zouj-ai-sdlc never uploads diagnostics.""")
    return 0


def cmd_repair(root, args):
    from . import lifecycle
    return lifecycle.cmd_repair(root, args)


def cmd_upgrade(root, args):
    from . import lifecycle
    return lifecycle.cmd_upgrade(root, args)


def cmd_uninstall(root, args):
    from . import lifecycle
    return lifecycle.cmd_uninstall(root, args)


def cmd_list_installed(root, args):
    from . import lifecycle
    return lifecycle.cmd_list_installed(root, args)


def cmd_why(root, args):
    from . import rules
    if not args:
        out("usage: sdlc why <rule id>   (the id is in the block message, e.g. BLOCKED [G-ENV-03])", sys.stderr)
        return 1
    rc, text = rules.why(args[0])
    out(text, sys.stderr if rc else None)
    return rc


def cmd_setup(root, args):
    from . import setup   # imported here: setup builds on init_actions/apply_init in this module
    return setup.main(root, args)


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
            "edit the Makefile's recipes (presets: the plugin's templates/stacks/<python|node|go>.recipes)")
    for b in ("gh", "jq"):
        out(f"  {'✓' if shutil.which(b) else '!'} {b} (optional)")
    if initialized(root):
        cfg = config(root)
        row(cfg["profile"] in PROFILES, f"profile: {cfg['profile']} (approval_key_policy: "
            f"{cfg.get('approval_key_policy')}, signed approvals: {'yes' if cfg.get('require_signed_approvals') else 'no'})",
            'set "profile" in .aiops/config.json to solo, team or strict (human-owned), or run '
            "`sdlc setup --profile <p>` in your own terminal")
        covered, msg = codeowners_cover_aiops(root), "CODEOWNERS covers /.aiops/"
        fix = "add `/.aiops/ @<approver>` to .github/CODEOWNERS (human-owned) and require CODEOWNER review on main"
        if cfg["profile"] == "strict":                 # strict: a CODEOWNER must review every change to .aiops/
            row(covered, msg, fix)
        else:
            out(f"  {'✓' if covered else '!'} {msg}" + ("" if covered else f" (recommended)\n      fix: {fix}"))
        if cfg.get("approval_key_policy") == "sk":   # strict: only touch keys may be allow-listed
            f = root / ".aiops" / "config" / "allowed-signers"
            weak = approvals.non_touch_signers(f.read_text() if f.is_file() else "")
            row(not weak, "allowed-signers: strict accepts only sk- keys that need a touch"
                + (f" ({len(weak)} other: {', '.join(w.split()[0] for w in weak[:3])})" if weak else ""),
                "replace those entries with sk- keys, without no-touch-required (human-owned, via a reviewed PR)")
    if initialized(root) and not (root / ".github" / "workflows" / "aiops-gates.yml").is_file():
        out("  ! .github/workflows/aiops-gates.yml missing: CI doesn't audit the approvals (the hard guarantee)\n"
            "      fix: `sdlc upgrade` offers it back, or copy it from the plugin's templates/scaffold/")
    if initialized(root) and config(root).get("require_signed_approvals"):
        _doctor_signing(root, row)
    if initialized(root) and (root / ".aiops" / "config" / "allowed-commands").is_symlink():
        row(False, ".aiops/config/allowed-commands is a symlink (the hooks ignore it)",
            "replace it with a regular file (human-owned)")
    elif initialized(root) and (root / ".aiops" / "config" / "allowed-commands").is_file():
        from . import rules
        probs = rules.allowance_problems((root / rules.ALLOWANCES).read_text(errors="replace"))
        for p in probs:
            row(False, f"{rules.ALLOWANCES} {p}", "remove or fix that line (human-owned); `sdlc why <id>` shows "
                "whether a rule can be allowed")
        if not probs:
            out(f"  ✓ {rules.ALLOWANCES}: ok")
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
            out(f"BLOCKED [G-FAIL-01] by zouj-ai-sdlc: the guard crashed ({type(exc).__name__}: {exc}), so it fails "
                "closed.\nProcedure: tell the human. They can fix the plugin or run /plugin disable zouj-ai-sdlc. "
                "(details: `sdlc why G-FAIL-01`)", sys.stderr)
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


def hook_profile(data, m):
    """The human typed `Setup Profile <name>` as the whole prompt: set this repo's first profile. Like an approval,
    it runs in-process and reads no CLAUDECODE / CLAUDE_CODE_CHILD_SESSION marker: Claude Code sets both for the
    hooks of every session, so they say nothing about who typed the prompt. Dormant without .aiops/."""
    root = project_root(data.get("cwd"))
    if not initialized(root):
        return 0
    from . import setup
    _ok, msg = setup.set_first_profile(root, (m.group(1) or "").lower())
    out(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                           "additionalContext": f"zouj-ai-sdlc {msg}"}}))
    return 0


def hook_prompt(data):
    prompt = data.get("prompt") or ""
    m = APPROVE_RE.match(prompt)
    if not m:
        m = PROFILE_RE.match(prompt)
        return hook_profile(data, m) if m else 0
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
        "intent's plan is approved. Start: /zouj-ai-sdlc:intent" + "".join(f"\n{ln}" for ln in terminal_lines(root))
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
        out(f"NOT VALID [G-ART-09] by zouj-ai-sdlc: {rel} was saved but does not validate yet (fix before asking "
            "for approval):\n- "
            + "\n- ".join(errors + warnings)
            + f"\nProcedure: fix the errors above; `sdlc validate {m.group(1)[:4]}` lists them. "
              "(details: `sdlc why G-ART-09`)", sys.stderr)
        return 2
    return 0


HOOKS = {"pre-edit": _pre(guards.check_edit), "pre-bash": _pre(guards.check_bash), "prompt": hook_prompt,
         "session-start": hook_session_start, "post-edit": hook_post_edit}

COMMANDS = {"status": cmd_status, "next": cmd_next, "new": cmd_new, "draft": cmd_draft, "use": cmd_use,
            "validate": cmd_validate, "approve": cmd_approve, "close": cmd_close, "lock": cmd_lock,
            "unlock": cmd_unlock, "legacy-approvals": cmd_legacy_approvals, "init": cmd_init, "doctor": cmd_doctor,
            "setup": cmd_setup, "feedback": cmd_feedback, "why": cmd_why, "where": cmd_where,
            "list-installed": cmd_list_installed, "repair": cmd_repair,
            "upgrade": cmd_upgrade, "uninstall": cmd_uninstall}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("help", "-h", "--help"):
        out(USAGE)
        return 0
    if argv[0] == "hook":
        return hook(argv[1] if len(argv) > 1 else "")
    if argv[0] == "where":                       # needs no repo: not even the lookup of its root
        return cmd_where(None, argv[1:])
    if argv[0] not in COMMANDS:
        out(f"unknown command {argv[0]!r}\n\n{USAGE}", sys.stderr)
        return 1
    return COMMANDS[argv[0]](_root(), argv[1:])
