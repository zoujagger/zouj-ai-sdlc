"""Install state (.aiops/install-state.json) and the lifecycle commands built on it.

install-state records what the plugin wrote into a repo: the plugin version, the ref pinned in CI, the profile, the
stack, and the sha256 of each scaffold file as written. Only the engine writes it (init, setup, and later upgrade,
repair, uninstall); the guards block the agent's own writes, and CODEOWNERS covers it. It never decides a gate: CI
ignores it.
"""
import datetime
import difflib
import hashlib
import json
import re
import shlex
import sys

from . import approvals, cli
from .machine import PLUGIN_ROOT, config

STATE = ".aiops/install-state.json"
SCHEMA = 1
NOT_OWNED = {".gitignore"}            # init appends a line to it; the file stays the user's


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(path.read_bytes())


def render(rel, ref):
    """The bytes the plugin writes for scaffold file rel, with the CI ref pinned to ref."""
    data = (cli.TEMPLATES / "scaffold" / rel).read_bytes()
    return data.replace(cli.REF_PLACEHOLDER.encode(), ref.encode())


def load(root):
    """The install state, or None if the repo has none (not initialized by 0.2.0-alpha.3+, or unreadable)."""
    f = root / STATE
    if not f.is_file() or f.is_symlink():
        return None
    try:
        st = json.loads(f.read_text())
    except (OSError, ValueError):
        return None
    return st if isinstance(st, dict) and isinstance(st.get("files"), dict) else None


def save(root, st):
    cli.write_file(root, STATE, (json.dumps(st, indent=2, sort_keys=True) + "\n").encode())


def record(root, written, profile=None, stack=None, ref=None):
    """Record the scaffold files just written (their bytes on disk) in install-state. Files that were only kept are
    not claimed. Nothing is written when nothing was, so a rerun leaves the state as it is."""
    paths = [rel for rel in dict.fromkeys(written) if rel not in NOT_OWNED and (cli.TEMPLATES / "scaffold" / rel).is_file()]
    if not paths:
        return
    version = cli.plugin_version()
    st = load(root) or {"schema": SCHEMA, "files": {}, "migrations": []}
    st.update({
        "schema": SCHEMA,
        "plugin_version": version,
        "ref": ref or st.get("ref") or f"v{version}",
        "profile": profile or config(root).get("profile", "team"),
        "stack": stack if stack is not None else st.get("stack"),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    for rel in paths:
        st["files"][rel] = {"sha256": sha256_file(root / rel), "version": version,
                            "human_owned": bool(cli.HUMAN_OWNED_RE.match(rel))}
    save(root, st)


STATUSES = ("current", "stale", "modified", "missing", "unmanaged", "dropped", "new")


def scaffold_paths():
    root = cli.TEMPLATES / "scaffold"
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def expected(rel, ref, stack=None):
    """The bytes the running plugin would write for rel today (ref pinned, the stack's recipes wired in)."""
    data = render(rel, ref)
    if rel == "Makefile" and stack in cli.STACKS:
        data = cli.wire(data.decode(), stack)[0].encode()
    return data


def classify(root, st):
    """{rel: status} for the scaffold and every recorded path:
    current   on disk as recorded, and what the running plugin would write
    stale     on disk as recorded, but written by an older plugin whose template has changed (upgrade replaces it)
    modified  changed since the plugin wrote it (never touched)
    missing   recorded, but not on disk (repair restores it)
    unmanaged a scaffold path on disk that install-state doesn't claim (never touched)
    dropped   recorded, but no longer in the plugin's scaffold
    new       in the running plugin's scaffold, never installed here (upgrade creates it)"""
    version = cli.plugin_version()
    scaffold = set(scaffold_paths())
    files = (st or {}).get("files", {})
    out = {}
    for rel, entry in files.items():
        f = root / rel
        if rel not in scaffold:
            out[rel] = "dropped"
        elif not f.is_file() or f.is_symlink():
            out[rel] = "missing"
        elif sha256_file(f) != entry.get("sha256"):
            out[rel] = "modified"
        elif entry.get("version") == version or \
                sha256_bytes(expected(rel, f"v{version}", st.get("stack"))) == entry.get("sha256"):
            out[rel] = "current"
        else:
            out[rel] = "stale"
    for rel in scaffold - set(files):
        if (root / rel).exists():
            out[rel] = "unmanaged"
        elif st:
            out[rel] = "new"
    return dict(sorted(out.items()))


def cmd_list_installed(root, args):
    """Read-only: what install-state says the plugin wrote here, against the files and the running plugin."""
    st = load(root)
    if st:
        out(f"zouj-ai-sdlc install state ({STATE})")
        out(f"  recorded: {st.get('plugin_version')} · ref {st.get('ref')} · profile {st.get('profile')} · "
            f"stack {st.get('stack') or 'none'}")
    else:
        out(f"zouj-ai-sdlc: this repo has no install state ({STATE}); it was initialized before 0.2.0-alpha.3 or "
            "not at all. Below is a preview of what adoption would record (nothing is written): files equal to a "
            "released scaffold become managed, the others are `modified` and are never touched.")
        st = adopt(root)
    out(f"  running plugin: {cli.plugin_version()}")
    rows = classify(root, st)
    for rel, status in rows.items():
        out(f"  {status:<9}  {rel}")
    counts = {s: sum(1 for v in rows.values() if v == s) for s in STATUSES}
    out("Summary: " + ", ".join(f"{n} {s}" for s, n in counts.items() if n))
    return 0


def out(msg, stream=None):
    cli.out(msg, stream)


# ---------------------------------------------------------------- scaffold history and adoption

HISTORY = PLUGIN_ROOT / "defaults" / "scaffold-history.json"   # generated by scripts/scaffold-history.py
REF_LINE_RE = re.compile(rb"(ZOUJ_SDLC_REF:[ \t]*)([^\s#]+)")
REF_JSON_RE = re.compile(rb'("ref":[ \t]*")([^"]*)(")')


def normalize(data):
    """data with the CI ref value put back to the placeholder: the hash then names the template, whatever ref the
    install pinned (v0.1.0 hard-coded it; later releases use the placeholder)."""
    data = REF_LINE_RE.sub(lambda m: m.group(1) + cli.REF_PLACEHOLDER.encode(), data)
    return REF_JSON_RE.sub(lambda m: m.group(1) + cli.REF_PLACEHOLDER.encode() + m.group(3), data)


def pinned_ref(data):
    m = REF_LINE_RE.search(data) or REF_JSON_RE.search(data)
    return m.group(2).decode(errors="replace") if m and m.group(2) != cli.REF_PLACEHOLDER.encode() else None


def history():
    """{version: {path: normalized sha256}}, with `Makefile+<stack>` for the stack-wired Makefiles. `unreleased`
    holds the working tree's scaffold while its version is already tagged."""
    try:
        return json.loads(HISTORY.read_text())
    except (OSError, ValueError):
        return {}


def history_key():
    """The history entry for the running plugin's scaffold."""
    return "unreleased" if "unreleased" in history() else cli.plugin_version()


def version_key(v):
    """Sort key for versions: 0.1.0 < 0.2.0-alpha.1 < 0.2.0-alpha.2 < 0.2.0 < unreleased."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", v or "")
    if not m:
        return (float("inf"),) if v == "unreleased" else (-1,)
    pre = m.group(4)
    tail = (1,) if pre is None else (0,) + tuple((0, int(p)) if p.isdigit() else (1, p) for p in pre.split("."))
    return tuple(int(x) for x in m.groups()[:3]) + tail


def adopt(root):
    """The install state for a repo initialized before install-state existed, without writing anything. Each scaffold
    path (of any release) that is a regular file is hashed after normalize(): equal to a release's template (a
    stack-wired Makefile included) it becomes managed at that release, else it is recorded as `modified` (sha256
    None), which no lifecycle command ever touches. Links are never claimed."""
    hist = history()
    paths = sorted({rel for files in hist.values() for rel in files if "+" not in rel} | set(scaffold_paths()))
    running, files, stack, ref, versions = cli.plugin_version(), {}, None, None, []
    for rel in paths:
        f = root / rel
        if cli.symlink_on_path(root, rel) or not f.is_file():
            continue
        data = f.read_bytes()
        h = sha256_bytes(normalize(data))
        hits = [v for v, m in hist.items() if m.get(rel) == h]
        if rel == "Makefile" and not hits:
            for s in cli.STACKS:
                hits = [v for v, m in hist.items() if m.get(f"Makefile+{s}") == h]
                if hits:
                    stack = s
                    break
        entry = {"sha256": None, "version": None, "human_owned": bool(cli.HUMAN_OWNED_RE.match(rel))}
        if hits:
            pin = pinned_ref(data)
            v = pin[1:] if pin and pin.startswith("v") and pin[1:] in hits else max(hits, key=version_key)
            v = running if v == "unreleased" else v
            entry.update(sha256=sha256_bytes(data), version=v)
            versions.append(v)
            if rel == ".github/workflows/aiops-gates.yml":
                ref = pin
        files[rel] = entry
    return {"schema": SCHEMA, "adopted": True, "files": files, "migrations": [], "stack": stack, "ref": ref,
            "plugin_version": max(versions, key=version_key) if versions else None,
            "profile": config(root).get("profile", "team"),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


# ---------------------------------------------------------------- shared by repair, upgrade and uninstall

def parse(args, name):
    """({"--dry-run": bool, "--yes": bool}, None) or (None, why): the lifecycle commands take only these flags."""
    opts = {"--dry-run": False, "--yes": False}
    for a in args:
        if a not in opts:
            return None, f"unknown option {a!r}; `sdlc {name}` takes --dry-run and --yes"
        opts[a] = True
    return opts, None


def human_command(name):
    """The exact command the human runs in their own terminal (absolute python and plugin path, isolated)."""
    return f"{approvals.PYTHON} -I {shlex.quote(str(PLUGIN_ROOT / 'bin' / 'sdlc'))} {name}"


def agent_may_write(root, rel):
    """Run by the agent, a lifecycle command writes only what the agent could write itself: never a human-owned
    file (config, signers, settings, CODEOWNERS, workflows), a protected path, or code under the read-only lock."""
    return not (cli.HUMAN_OWNED_RE.match(rel) or cli._agent_blocked(root, rel))


def confirm(opts, name):
    """None to go ahead, else the exit code: 0 for --dry-run, 2 when there's no terminal or no yes."""
    if opts["--dry-run"]:
        out("Dry run: nothing was written.")
        return 0
    if opts["--yes"]:
        return None
    from . import setup
    if not setup._is_tty():
        out(f"no terminal to confirm: nothing was written. Re-run with --yes to apply (`sdlc {name} --yes`).")
        return 2
    if not setup._confirm():
        out("not confirmed: nothing was written.")
        return 2
    return None


def refusal(root):
    """Why a lifecycle command must not touch root (the same rules as init and setup), else None."""
    problem = cli.scaffold_root_problem(root)
    if problem:
        return f"refusing: {problem}. Nothing was written."
    links = [rel for rel in set(scaffold_paths()) | {STATE} if cli.symlink_on_path(root, rel)]
    if links:
        return ("refusing to write through symlinks; remove these links and run again. Nothing was written:\n  "
                + "\n  ".join(sorted(links)))
    return None


def show_diff(rel, old, new, limit=40):
    lines = list(difflib.unified_diff(old.decode(errors="replace").splitlines(), new.decode(errors="replace").splitlines(),
                                      f"a/{rel}", f"b/{rel}", lineterm=""))
    for ln in lines[:limit]:
        out("      " + ln)
    if len(lines) > limit:
        out(f"      … {len(lines) - limit} more lines")


def write_scaffold(root, st, rel, data, version=None):
    cli.write_file(root, rel, data, (cli.TEMPLATES / "scaffold" / rel).stat().st_mode & 0o777
                   if (cli.TEMPLATES / "scaffold" / rel).is_file() else 0o644)
    st["files"][rel] = {"sha256": sha256_bytes(data), "version": version or cli.plugin_version(),
                        "human_owned": bool(cli.HUMAN_OWNED_RE.match(rel))}


def stamp(st):
    st["updated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- repair

def cmd_repair(root, args):
    """Re-create missing managed files. Never touches a modified, stale or current one (upgrade does stale)."""
    opts, why = parse(args, "repair")
    if why:
        out(f"{why}. Nothing was written.", sys.stderr)
        return 1
    why = refusal(root)
    if why:
        out(why, sys.stderr)
        return 1
    st, adopted = load(root), False
    if st is None:
        st, adopted = adopt(root), True
    agent = approvals.running_under_agent()
    ref = st.get("ref") or f"v{cli.plugin_version()}"
    restore, human = [], []
    for rel, status in classify(root, st).items():
        if status != "missing":
            continue
        (human if agent and not agent_may_write(root, rel) else restore).append(rel)
    if adopted:
        out(f"No install state: adopting this repo ({len([1 for e in st['files'].values() if e['sha256']])} files "
            f"match a released scaffold; the others are `modified` and are never touched). Writes {STATE}.")
    if not restore and not human and not adopted:
        out("Nothing to repair: every managed file is on disk.")
        return 0
    for rel in restore:
        out(f"  + restore {rel}")
    if human:
        out("Human-owned or locked, not restored when the agent runs repair. The human runs, in their own terminal:\n"
            f"  {human_command('repair')}\n  for: " + ", ".join(human))
    rc = confirm(opts, "repair")
    if rc is not None:
        return rc
    written = []
    try:
        for rel in restore:
            write_scaffold(root, st, rel, expected(rel, ref, st.get("stack")))
            written.append(rel)
        stamp(st)
        save(root, st)
    except OSError as exc:
        out(cli.write_failure(exc, written), sys.stderr)
        return 1
    out(f"Repaired: {len(written)} file(s) restored; {STATE} updated. Commit the result.")
    return 0
