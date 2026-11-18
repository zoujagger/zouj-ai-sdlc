"""Stack auto-detection for the Makefile contract (intent 0009).

`detect(root)` looks only at regular files directly at the repo top and proposes a recipe for each contract target
(format, lint, typecheck, test, build) from the repo's own commands. It reads, and nothing else: no subprocess, no
network, no write, no link followed, no file outside `MARKERS`, none over `MAX_BYTES`. A file that can't be parsed
counts as absent and is named in `note`. Stdlib only, and no import of the rest of the engine (cli imports this).
"""

import json
import re
from collections import namedtuple
from pathlib import Path
from xml.etree import ElementTree

Detection = namedtuple("Detection", "kind label recipes evidence note")

TARGETS = ("format", "lint", "typecheck", "test", "build")
KINDS = ("python", "node", "go", "java", "react", "angular")
CHOICES = ("auto", "none") + KINDS
FAMILY_OF = {"python": "python", "go": "go", "java": "java", "node": "node", "react": "node", "angular": "node"}
MAX_BYTES = 1 << 20
STACKS_DIR = Path(__file__).resolve().parents[2] / "templates" / "stacks"

# Each family's marker files, in the order they're tried.
FAMILIES = {
    "java": ("pom.xml", "build.gradle", "build.gradle.kts"),
    "node": ("package.json",),
    "python": ("pyproject.toml", "setup.cfg", "setup.py", "requirements.txt"),
    "go": ("go.mod",),
}
LOCKFILES = (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("bun.lock", "bun"))
WRAPPERS = ("mvnw", "gradlew")
# Every file detection may open or look at. Nothing else is ever read (tests/test_stacks.py::test_reads_only_markers):
# no .env*, .npmrc or settings.xml, which can hold tokens.
MARKERS = frozenset(
    [name for names in FAMILIES.values() for name in names]
    + [name for name, _ in LOCKFILES]
    + ["angular.json", "tsconfig.json"]
    + list(WRAPPERS)
)


def _regular(root, name):
    """root/name when it is a regular file directly at the top (not a link), else None."""
    assert name in MARKERS, name
    p = root / name
    try:
        return p if not p.is_symlink() and p.is_file() else None
    except OSError:
        return None


def _read(root, name):
    """The text of a top-level marker file, or None: missing, a link, not regular, over MAX_BYTES or unreadable."""
    p = _regular(root, name)
    if p is None:
        return None
    try:
        if p.stat().st_size > MAX_BYTES:
            return None
        with open(p, "rb") as f:
            data = f.read(MAX_BYTES + 1)
    except OSError:
        return None
    return None if len(data) > MAX_BYTES else data.decode("utf-8", errors="replace")


def _json(root, name):
    text = _read(root, name)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _xml(root, name):
    text = _read(root, name)
    if text is None:
        return None
    try:
        return ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return None


def _families(root):
    """The families whose markers are present (regular files at the top), in FAMILIES order."""
    return [fam for fam, names in FAMILIES.items() if any(_regular(root, n) for n in names)]


def none(note):
    return Detection(None, None, {}, [], note)


def detect(root, force=None):
    """The Detection for root. `force` (a KINDS name) skips the family choice but still reads the repo."""
    root = Path(root)
    if force is not None:
        if force not in KINDS:
            raise ValueError(f"unknown stack {force!r} (one of: {', '.join(KINDS)})")
        family = FAMILY_OF[force]
        if not any(_regular(root, n) for n in FAMILIES[family]):
            return none(f"--stack {force} needs {' or '.join(FAMILIES[family])} at the repo top; nothing was wired")
    else:
        found = _families(root)
        if not found:
            return none("no stack detected: no build file at the repo top")
        if len(found) > 1:
            return none(
                f"no stack chosen: the repo top has more than one ({', '.join(found)}); "
                f"pass --stack {'|'.join(found)}"
            )
        family = found[0]
    return DETECTORS[family](root, force)


def _node_family(root, force):
    pkg = _json(root, "package.json")
    if pkg is None:
        return none("no stack detected: package.json can't be read as JSON (or is a link, or over 1 MiB)")
    return Detection(force or "node", "Node", {}, ["package.json"], "")


def _java(root, force):
    if _regular(root, "pom.xml"):
        if _xml(root, "pom.xml") is None:
            return none("no stack detected: pom.xml can't be read as XML (or is a link, or over 1 MiB)")
        return Detection("java", "Java · Maven", {}, ["pom.xml"], "")
    name = "build.gradle.kts" if _regular(root, "build.gradle.kts") else "build.gradle"
    if _read(root, name) is None:
        return none(f"no stack detected: {name} can't be read")
    return Detection("java", "Java · Gradle", {}, [name], "")


def _python(root, force):
    return Detection("python", "Python", {}, [n for n in FAMILIES["python"] if _regular(root, n)], "")


def _go(root, force):
    return Detection("go", "Go", {}, ["go.mod"], "")


DETECTORS = {"java": _java, "node": _node_family, "python": _python, "go": _go}

SCRIPT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,63}$")
