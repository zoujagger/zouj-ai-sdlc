"""Install state (.aiops/install-state.json) and the lifecycle commands built on it.

install-state records what the plugin wrote into a repo: the plugin version, the ref pinned in CI, the profile, the
stack, and the sha256 of each scaffold file as written. Only the engine writes it (init, setup, and later upgrade,
repair, uninstall); the guards block the agent's own writes, and CODEOWNERS covers it. It never decides a gate: CI
ignores it.
"""
import datetime
import hashlib
import json

from . import cli
from .machine import config

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
            "not at all. Scaffold files on disk are listed as unmanaged.")
    out(f"  running plugin: {cli.plugin_version()}")
    rows = classify(root, st)
    for rel, status in rows.items():
        out(f"  {status:<9}  {rel}")
    counts = {s: sum(1 for v in rows.values() if v == s) for s in STATUSES}
    out("Summary: " + ", ".join(f"{n} {s}" for s, n in counts.items() if n))
    return 0


def out(msg):
    cli.out(msg)
