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
