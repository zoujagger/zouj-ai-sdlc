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
from fnmatch import fnmatchcase

from . import approvals, cli
from .machine import PLUGIN_ROOT, config

STATE = ".aiops/install-state.json"
SCHEMA = 1
NOT_OWNED = {".gitignore"}  # init appends a line to it; the file stays the user's


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


def record(root, written, profile=None, stack=None, ref=None, parts=None):
    """Record the scaffold files just written (their bytes on disk) in install-state, and the installed opt-in
    `parts` when given. Files that were only kept are not claimed. Nothing is written when nothing was, so a rerun
    leaves the state as it is."""
    paths = [
        rel for rel in dict.fromkeys(written) if rel not in NOT_OWNED and (cli.TEMPLATES / "scaffold" / rel).is_file()
    ]
    if not paths:
        return
    version = cli.plugin_version()
    st = load(root) or {"schema": SCHEMA, "files": {}, "migrations": []}
    st.update(
        {
            "schema": SCHEMA,
            "plugin_version": version,
            "ref": ref or st.get("ref") or f"v{version}",
            "profile": profile or config(root).get("profile", "team"),
            "stack": stack if stack is not None else st.get("stack"),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    if parts is not None:
        st["parts"] = sorted(parts)
    for rel in paths:
        st["files"][rel] = {
            "sha256": sha256_file(root / rel),
            "version": version,
            "human_owned": bool(cli.HUMAN_OWNED_RE.match(rel)),
        }
    save(root, st)


# security scaffold a repo must not silently lose: offered back by upgrade even if it was missing at adoption
NEVER_DECLINED = {
    ".github/workflows/aiops-gates.yml",
    ".github/CODEOWNERS",
    ".aiops/config/allowed-signers",
    ".aiops/config/secret-paths",
    ".aiops/config/protected-paths",
}

STATUSES = ("current", "stale", "modified", "missing", "unmanaged", "dropped", "new", "declined")

PARTS = ("review", "maintain", "deploy", "governance", "issues")  # opt-in (`--with`); `core` is always installed
PARTS_FILE = PLUGIN_ROOT / "defaults" / "scaffold-parts"


def part_rules():
    """[(part, glob)] from defaults/scaffold-parts: the part each scaffold file belongs to."""
    out = []
    for line in PARTS_FILE.read_text().splitlines():
        part, _, glob = line.strip().partition(" ")
        if part and not part.startswith("#") and glob.strip():
            out.append((part, glob.strip()))
    return out


def part_of(rel, rules=None):
    """The part scaffold path rel belongs to. A path no line matches is core, so a new file is never left out."""
    rules = part_rules() if rules is None else rules
    return next((part for part, glob in rules if fnmatchcase(rel, glob)), "core")


def parse_parts(value):
    """(sorted opt-in part names, None) for a `--with` value (comma-separated names, or `all`), or (None, why)."""
    if value == "all":
        return sorted(PARTS), None
    names = value.split(",")
    bad = [n for n in names if n not in PARTS]
    if bad:
        return None, f"unknown part {bad[0]!r}; --with takes a comma-separated list of {', '.join(PARTS)}, or all"
    return sorted(set(names)), None


def parts_line(parts, command="setup"):
    """One line naming the opt-in parts that aren't installed and how to add them; "" when every part is."""
    missing = [p for p in PARTS if p not in parts]
    if not missing:
        return ""
    return (
        f"Not installed (opt-in parts): {', '.join(missing)}. Add one with `sdlc {command} --with <part>` "
        "(comma-separated, or `--with all`)."
    )


def scaffold_paths(parts=None):
    """Every scaffold path; with `parts` (opt-in part names), only core and those parts."""
    root = cli.TEMPLATES / "scaffold"
    paths = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    if parts is None:
        return paths
    rules, keep = part_rules(), {"core", *parts}
    return [rel for rel in paths if part_of(rel, rules) in keep]


def config_written(root):
    """What setup or init left in .aiops/config.json: "" for the untouched scaffold template (or no file yet: a run
    that stopped before writing it), a profile name for the template with exactly that profile's keys (a human's
    `setup --profile`), and None for anything else (edited by hand, a link, unreadable)."""
    from .setup import PROFILE_CONFIG

    f = root / ".aiops" / "config.json"
    if not f.exists() and not f.is_symlink():
        return ""
    try:
        if f.is_symlink():
            return None
        cfg = json.loads(f.read_text())
        template = json.loads((cli.TEMPLATES / "scaffold" / ".aiops" / "config.json").read_text())
    except (OSError, ValueError):
        return None
    if cfg == template:
        return ""
    return next((name for name, keys in PROFILE_CONFIG.items() if cfg == {**template, **keys}), None)


def config_is_template(root):
    """True if nobody has chosen a profile here: config.json is missing or still exactly the scaffold template."""
    return config_written(root) == ""


def parts_on_disk(root):
    """The opt-in parts with at least one file on disk that a release of the plugin wrote (compared after
    normalize(), against every release's scaffold and the running one). The user's own file at a scaffold path, such
    as their dependabot.yml, doesn't count."""
    rules, released = part_rules(), {}
    for files in history().values():
        for rel, digest in files.items():
            released.setdefault(rel, set()).add(digest)
    found = set()
    for rel in scaffold_paths():
        part, f = part_of(rel, rules), root / rel
        if part == "core" or part in found or not f.is_file() or cli.symlink_on_path(root, rel):
            continue
        digest = sha256_bytes(normalize(f.read_bytes()))
        if digest in released.get(rel, ()) or digest == sha256_bytes(normalize(render(rel, cli.REF_PLACEHOLDER))):
            found.add(part)
    return sorted(found)


def installed_parts(root, st, requested=()):
    """The opt-in parts installed here, sorted, plus the `requested` ones (`--with` only adds):
    - install-state names them (`parts`); state written before 0.2.0-alpha.4 has no such key and means every part
    - with no install-state: a repo whose config.json is what setup writes (the template, with or without a
      profile's keys, or no file yet) has the parts found on disk, so a new repo gets core only and a rerun after a
      setup that stopped part-way installs what the first run chose; a repo with an edited config was initialized
      before install-state existed and has every part."""
    if st is not None:
        base = [p for p in st["parts"] if p in PARTS] if isinstance(st.get("parts"), list) else PARTS
    elif config_written(root) is not None:
        base = parts_on_disk(root)
    else:
        base = PARTS
    return sorted(set(base) | set(requested))


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
    new       in the running plugin's scaffold, never installed here (upgrade creates it)
    declined  part of the adopted release's scaffold, but the user had removed it: never re-created
    A file of an opt-in part that isn't installed (installed_parts) is not listed at all, unless install-state
    records it or it exists on disk (unmanaged): it is never `new` or `missing`, so no command creates it."""
    version = cli.plugin_version()
    scaffold = set(scaffold_paths())
    files = (st or {}).get("files", {})
    rules, installed = part_rules(), {"core", *(installed_parts(root, st) if st else PARTS)}
    out = {}
    for rel, entry in files.items():
        f = root / rel
        if entry.get("declined") and not f.exists():
            out[rel] = "declined"
        elif rel not in scaffold:
            out[rel] = "dropped"
        elif not f.is_file() or f.is_symlink():
            out[rel] = "missing"
        elif sha256_file(f) != entry.get("sha256"):
            out[rel] = "modified"
        elif entry.get("version") == version or sha256_bytes(
            expected(rel, f"v{version}", st.get("stack"))
        ) == entry.get("sha256"):
            out[rel] = "current"
        else:
            out[rel] = "stale"
    for rel in scaffold - set(files):
        if (root / rel).exists():
            out[rel] = "unmanaged"
        elif st and part_of(rel, rules) in installed:
            out[rel] = "new"
    return dict(sorted(out.items()))


def cmd_list_installed(root, args):
    """Read-only: what install-state says the plugin wrote here, against the files and the running plugin."""
    st = load(root)
    if st:
        out(f"zouj-ai-sdlc install state ({STATE})")
        # the profile is read from .aiops/config.json, its one source: the typed phrase and a hand edit change it there
        out(
            f"  recorded: {st.get('plugin_version')} · ref {st.get('ref')} · profile {config(root).get('profile')} · "
            f"stack {st.get('stack') or 'none'}"
        )
    else:
        out(
            f"zouj-ai-sdlc: this repo has no install state ({STATE}); it was initialized before 0.2.0-alpha.3 or "
            "not at all. Below is a preview of what adoption would record (nothing is written): files equal to a "
            "released scaffold become managed, the others are `modified` and are never touched. `sdlc repair` (or "
            "`sdlc upgrade`) records it."
        )
        st = adopt(root)
    out(f"  running plugin: {cli.plugin_version()}")
    rows = classify(root, st)
    for rel, status in rows.items():
        out(f"  {status:<9}  {rel}")
    counts = {s: sum(1 for v in rows.values() if v == s) for s in STATUSES}
    out("Summary: " + ", ".join(f"{n} {s}" for s, n in counts.items() if n))
    left_out = parts_line(installed_parts(root, st))
    if left_out:
        out(left_out)
    return 0


def out(msg, stream=None):
    cli.out(msg, stream)


# ---------------------------------------------------------------- scaffold history and adoption

HISTORY = PLUGIN_ROOT / "defaults" / "scaffold-history.json"  # generated by scripts/scaffold-history.py
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
    newest = max(versions, key=version_key) if versions else None
    release = next((k for k in hist if (running if k == "unreleased" else k) == newest), None)
    parts, rules = installed_parts(root, None), part_rules()  # read from disk: there is no state to name them
    for rel in hist.get(release, {}):  # in the adopted release, but not on disk: the user removed it
        if (
            "+" not in rel
            and rel not in files
            and rel not in NEVER_DECLINED
            and not (root / rel).exists()
            and not (root / rel).is_symlink()
            and part_of(rel, rules) in ("core", *parts)
        ):
            files[rel] = {
                "sha256": None,
                "version": None,
                "declined": True,
                "human_owned": bool(cli.HUMAN_OWNED_RE.match(rel)),
            }
    return {
        "schema": SCHEMA,
        "adopted": True,
        "files": files,
        "migrations": [],
        "stack": stack,
        "ref": ref,
        "plugin_version": newest,
        "parts": parts,
        "profile": config(root).get("profile", "team"),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


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
    file (config, signers, settings, CODEOWNERS, workflows), a protected path, or code under the read-only lock. The
    lock is judged without SDLC_HOOK_PROFILE / AIOPS_INTENT, which the agent's own command line could set."""
    from .machine import lock_env_stripped

    with lock_env_stripped():
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
        return (
            "refusing to write through symlinks; remove these links and run again. Nothing was written:\n  "
            + "\n  ".join(sorted(links))
        )
    return None


def show_diff(rel, old, new, limit=40):
    lines = list(
        difflib.unified_diff(
            old.decode(errors="replace").splitlines(),
            new.decode(errors="replace").splitlines(),
            f"a/{rel}",
            f"b/{rel}",
            lineterm="",
        )
    )
    for ln in lines[:limit]:
        out("      " + ln)
    if len(lines) > limit:
        out(f"      … {len(lines) - limit} more lines")


def write_scaffold(root, st, rel, data, version=None):
    cli.write_file(
        root,
        rel,
        data,
        (cli.TEMPLATES / "scaffold" / rel).stat().st_mode & 0o777
        if (cli.TEMPLATES / "scaffold" / rel).is_file()
        else 0o644,
    )
    st["files"][rel] = {
        "sha256": sha256_bytes(data),
        "version": version or cli.plugin_version(),
        "human_owned": bool(cli.HUMAN_OWNED_RE.match(rel)),
    }


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
        out(
            f"No install state: adopting this repo ({len([1 for e in st['files'].values() if e['sha256']])} files "
            f"match a released scaffold; the others are `modified` and are never touched). Writes {STATE}."
        )
    if not restore and not human and not adopted:
        out("Nothing to repair: every managed file is on disk.")
        return 0
    for rel in restore:
        out(f"  + restore {rel}")
    if human:
        out(
            "Human-owned or locked, not restored when the agent runs repair. The human runs, in their own terminal:\n"
            f"  {human_command('repair')}\n  for: " + ", ".join(human)
        )
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


# ---------------------------------------------------------------- the ref upgrade pins

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def resolve_ref(plugin_root=PLUGIN_ROOT, home=None):
    """(ref, warning or None): the full commit sha of the running plugin, for CI to fetch, in this order:
    1. ~/.claude/plugins/installed_plugins.json: the gitCommitSha of the install whose installPath is this plugin
       (marketplace installs have no .git; Claude Code records the sha there)
    2. this plugin's own git checkout (`claude --plugin-dir`): HEAD, if a remote-tracking branch contains it
    3. the tag v<version>, with a warning: a tag can be moved."""
    from pathlib import Path

    plugin_root = Path(plugin_root).resolve()
    home = Path(home) if home is not None else Path.home()
    try:
        data = json.loads((home / ".claude" / "plugins" / "installed_plugins.json").read_text())
        installs = data.get("plugins", data) if isinstance(data, dict) else {}
        for entries in installs.values() if isinstance(installs, dict) else []:
            for e in entries if isinstance(entries, list) else [entries]:
                if not isinstance(e, dict) or not e.get("installPath"):
                    continue
                sha = str(e.get("gitCommitSha") or "")
                if Path(e["installPath"]).resolve() == plugin_root and SHA_RE.match(sha):
                    return sha, None
    except (OSError, ValueError, TypeError):
        pass
    tag = f"v{cli.plugin_version()}"
    top = cli.git(plugin_root, "rev-parse", "--show-toplevel")
    if top and Path(top).resolve() == plugin_root:
        head = cli.git(plugin_root, "rev-parse", "HEAD") or ""
        if SHA_RE.match(head):
            if (cli.git(plugin_root, "branch", "-r", "--contains", head) or "").strip():
                return head, None
            return tag, (
                f"the plugin checkout's HEAD ({head[:10]}) is not pushed to a remote, so CI couldn't fetch "
                f"it; pinning the tag {tag} instead (a tag can be moved: pin a full sha when you can)"
            )
    return tag, (
        f"no commit sha found for this plugin install; pinning the tag {tag} (a tag can be moved: pin a "
        "full sha when you can)"
    )


# ---------------------------------------------------------------- upgrade

MERGED_JSON = (".aiops/config.json", ".claude/settings.json")  # setup merges its keys into these: never replaced


# Only literal values are pinned: a release tag, a full sha, or the placeholder. An expression (`${{ vars.X }}`) is
# the user's own and is left alone (listed for the human).
PIN_LINE_RE = re.compile(rb"(?m)(ZOUJ_SDLC_REF:[ \t]*)(v\d[\w.+-]*|[0-9a-f]{40}|__ZOUJ_SDLC_REF__)(?=[ \t]*(#|$))")
ZOUJ_REPO_RE = re.compile(rb'"repo"[ \t]*:[ \t]*"zoujagger/zouj-ai-sdlc"')


def _object_span(data, pos):
    """(start, end) of the innermost JSON object around byte offset pos (strings skipped), else None."""
    i, in_str, spans, stack = 0, False, [], []
    while i < len(data):
        c = data[i : i + 1]
        if in_str:
            if c == b"\\":
                i += 1
            elif c == b'"':
                in_str = False
        elif c == b'"':
            in_str = True
        elif c == b"{":
            stack.append(i)
        elif c == b"}" and stack:
            s = stack.pop()
            if s <= pos <= i:
                spans.append((s, i))
        i += 1
    return min(spans, key=lambda sp: sp[1] - sp[0]) if spans else None


def pin(data, ref):
    """data with the plugin's CI ref set to ref, and nothing else changed: each literal `ZOUJ_SDLC_REF:` value, and in
    JSON only the `"ref"` of the zouj-ai-sdlc marketplace source (another marketplace's ref is never touched)."""
    data = PIN_LINE_RE.sub(lambda m: m.group(1) + ref.encode(), data)
    spans = {_object_span(data, m.start()) for m in ZOUJ_REPO_RE.finditer(data)} - {None}
    for s, e in sorted(spans, reverse=True):  # right to left: earlier offsets stay valid
        for r in reversed(list(REF_JSON_RE.finditer(data, s, e + 1))):
            if _object_span(data, r.start()) == (s, e):  # the object's own ref, not a nested one
                data = data[: r.start(2)] + ref.encode() + data[r.end(2) :]
    return data


def unpinnable(data):
    """True if a ZOUJ_SDLC_REF line holds a value pin() leaves alone (an expression)."""
    return len(REF_LINE_RE.findall(data)) > len(PIN_LINE_RE.findall(data))


def plan_upgrade(root, st, ref, agent):
    """(actions, human, advice): actions are (kind, rel, bytes) with kind create (missing or new), replace (stale or
    current, from the running template) or pin (modified, unmanaged or a merged JSON file: only the ref value).
    human lists what the agent may not write; advice lists modified files that differ from the new template."""
    actions, human, advice = [], [], []
    stack = st.get("stack")
    for rel, status in classify(root, st).items():
        f = root / rel
        if status in ("dropped", "declined"):
            continue
        if status in ("missing", "new"):
            act = ("create", rel, expected(rel, ref, stack))
        else:
            disk = f.read_bytes()
            if status in ("current", "stale") and rel not in MERGED_JSON:
                act = ("replace", rel, expected(rel, ref, stack))
            else:
                act = ("pin", rel, pin(disk, ref))
                if status in ("modified", "unmanaged") and normalize(disk) != normalize(expected(rel, ref, stack)):
                    advice.append(rel)
                if unpinnable(disk):
                    advice.append(rel)
            if act[2] == disk:
                continue
        if agent and not agent_may_write(root, rel):
            human.append(rel)
        else:
            actions.append(act)
    return actions, human, advice


def cmd_upgrade(root, args):
    """Bring the repo's scaffold to the running plugin: replace stale files (diff shown), create missing and new ones,
    keep modified files except for the CI ref, pin every ref to a full sha, list migrations. No network."""
    from . import migrations

    opts, why = parse(args, "upgrade")
    if why:
        out(f"{why}. Nothing was written.", sys.stderr)
        return 1
    why = refusal(root)
    if why:
        out(why, sys.stderr)
        return 1
    version, agent = cli.plugin_version(), approvals.running_under_agent()
    st, adopted = load(root), False
    if st is None:
        st, adopted = adopt(root), True
    ref, warning = resolve_ref()
    actions, human, advice = plan_upgrade(root, st, ref, agent)
    done = set(st.get("migrations") or [])
    pending = [m for m in migrations.MIGRATIONS if m.id not in done and m.applies(root)]
    finished = [m.id for m in migrations.MIGRATIONS if m.id not in done and m not in pending]
    if warning:
        out(f"! {warning}")
    if not (actions or human or adopted or finished) and st.get("plugin_version") == version and st.get("ref") == ref:
        out(f"Already at {version} (ref {ref}). Nothing to upgrade.")
        for m in pending:
            out(f"  ! migration {m.id} is pending: {m.why}. The human runs `{m.command}` in their own terminal.")
        return 0
    out(f"Upgrade {st.get('plugin_version') or 'an adopted repo'} → {version}, ref {st.get('ref')} → {ref}")
    if adopted:
        out(f"  No install state: adopting this repo first ({STATE}).")
    for kind, rel, data in actions:
        out(f"  {'+' if kind == 'create' else '~'} {kind} {rel}")
        if kind in ("replace", "pin"):
            show_diff(rel, (root / rel).read_bytes(), data)
    for rel in dict.fromkeys(advice):
        disk = (root / rel).read_bytes()
        if unpinnable(disk):
            out(
                f"  ! {rel}: ZOUJ_SDLC_REF is not a literal (an expression?), so upgrade left it; set it to {ref} by hand"
            )
        if normalize(disk) != normalize(expected(rel, ref, st.get("stack"))):
            out(f"  = kept {rel} (modified): it differs from the new template; compare and merge by hand:")
            show_diff(rel, disk, expected(rel, ref, st.get("stack")))
    for rel, status in classify(root, st).items():
        if status == "declined":
            out(f"  ! {rel} is declined (removed before adoption); upgrade never re-creates it")
    if human:
        out(
            "Human-owned or locked, not written when the agent runs upgrade (install-state keeps them at their old "
            f"version). The human runs, in their own terminal:\n  {human_command('upgrade')}\n  for: "
            + ", ".join(human)
        )
    for m in pending:
        out(
            f"  ! migration {m.id}: {m.why}. "
            + (
                f"Human-only: the human runs `{m.command}` in their own terminal; upgrade never runs it."
                if m.human_only
                else f"Run `{m.command}`."
            )
        )
    rc = confirm(opts, "upgrade")
    if rc is not None:
        return rc
    written = []
    try:
        for kind, rel, data in actions:
            if kind == "pin":
                entry, before = st["files"].get(rel), sha256_file(root / rel)
                cli.write_file(root, rel, data, (root / rel).stat().st_mode & 0o777)
                if entry and entry.get("sha256") == before:  # managed and as recorded (a merged JSON file)
                    entry.update(sha256=sha256_bytes(data), version=version)
            else:
                write_scaffold(root, st, rel, data)
            written.append(rel)
        st["plugin_version"] = version
        if not human:
            st["ref"] = ref
        st["migrations"] = sorted(done | set(finished))
        st.pop("adopted", None)
        stamp(st)
        save(root, st)
    except OSError as exc:
        out(cli.write_failure(exc, written), sys.stderr)
        return 1
    out(
        f"Upgraded: {len(written)} file(s) written; {STATE} updated. Review the diff and commit it."
        + ("" if not human else " The human finishes the human-owned files and the ref.")
    )
    return 0


# ---------------------------------------------------------------- uninstall

ARTIFACT_TREE_RE = re.compile(r"^\.aiops/(\d{4}-[^/]+|state)(/|$)")
GITIGNORE_LINES = ("# zouj-ai-sdlc engine state (active intent, test lock)", ".aiops/state/")


def remove_file(root, rel):
    """Unlink root/rel without following a link anywhere on its path; only a regular file is removed."""
    import os
    import stat
    from pathlib import Path

    *dirs, name = Path(rel).parts
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in dirs:
            sub = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = sub
        if not stat.S_ISREG(os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode):
            raise OSError(f"{rel} is not a regular file; refusing to remove it")
        os.unlink(name, dir_fd=fd)
    finally:
        os.close(fd)


def plan_uninstall(root, st):
    """(remove, kept): remove lists the paths uninstall may delete; kept is [(rel, why)]. A path is removed only if it
    is recorded, is a scaffold path of some release, and still has its recorded hash. Artifacts (.aiops/NNNN-*,
    .aiops/state) are never removed, whatever install-state says."""
    known = {rel for files in history().values() for rel in files if "+" not in rel} | set(scaffold_paths())
    remove, kept = [], []
    for rel, entry in sorted(st.get("files", {}).items()):
        f = root / rel
        if ARTIFACT_TREE_RE.match(rel) or rel == STATE:
            kept.append((rel, "refused: an artifact or engine state, never removed"))
        elif rel not in known:
            kept.append((rel, "refused: not a scaffold path of any release"))
        elif cli.symlink_on_path(root, rel) or not f.is_file():
            if f.exists() or f.is_symlink():
                kept.append((rel, "refused: not a regular file"))
        elif not entry.get("sha256") or sha256_file(f) != entry["sha256"]:
            kept.append((rel, "kept: modified since the plugin wrote it"))
        else:
            remove.append(rel)
    return remove, kept


def cmd_uninstall(root, args):
    """Human-only (the dry run is open to anyone): remove the plugin's unmodified scaffold files, install-state and the
    .gitignore lines init added. Intent folders and .aiops/ stay: they are the audit trail."""
    opts, why = parse(args, "uninstall")
    if why:
        out(f"{why}. Nothing was written.", sys.stderr)
        return 1
    if approvals.running_under_agent() and not opts["--dry-run"]:
        out(
            cli.HUMAN_ONLY.replace("this is a human gate", "uninstall is human-only")
            + " Preview it with `sdlc uninstall --dry-run`.",
            sys.stderr,
        )
        return 1
    why = refusal(root)
    if why:
        out(why, sys.stderr)
        return 1
    st = load(root)
    if st is None:
        st = adopt(root)
        out("No install state: what adoption recognises as the plugin's files is planned for removal.")
    remove, kept = plan_uninstall(root, st)
    for rel in remove:
        out(f"  - remove {rel}")
    if (root / STATE).is_file():
        out(f"  - remove {STATE}")
    out("  - remove the .aiops/state/ lines from .gitignore")
    for rel, reason in kept:
        out(f"  = {rel}: {reason}")
    out("Kept: .aiops/ and its intent folders (the audit trail), and every file the plugin didn't write.")
    rc = confirm(opts, "uninstall")
    if rc is not None:
        return rc
    removed = []
    try:
        for rel in remove:
            remove_file(root, rel)
            removed.append(rel)
        if (root / STATE).is_file() and not (root / STATE).is_symlink():
            remove_file(root, STATE)
        gi = root / ".gitignore"
        if gi.is_file() and not gi.is_symlink():
            lines = [ln for ln in gi.read_text().splitlines() if ln not in GITIGNORE_LINES]
            if any(ln.strip() for ln in lines):
                cli.write_file(root, ".gitignore", ("\n".join(lines).rstrip("\n") + "\n").encode())
            else:
                remove_file(root, ".gitignore")
    except OSError as exc:
        out(f"✗ {exc}. Removed before the error: {', '.join(removed) or 'none'}.", sys.stderr)
        return 1
    out(
        f"Uninstalled: {len(removed)} file(s) removed. Next: review and commit the removal, then remove the plugin "
        "itself with `/plugin uninstall zouj-ai-sdlc@zouj` (and its entries in .claude/settings.json, if you kept "
        "that file)."
    )
    return 0
