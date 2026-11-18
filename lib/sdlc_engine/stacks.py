"""Stack auto-detection for the Makefile contract (intent 0009).

`detect(root)` looks only at regular files directly at the repo top and proposes a recipe for each contract target
(format, lint, typecheck, test, build) from the repo's own commands. It reads, and nothing else: no subprocess, no
network, no write, no link followed, no file outside `MARKERS`, none over `MAX_BYTES`. A file that can't be parsed
counts as absent and is named in `note`. Stdlib only, and no import of the rest of the engine (cli imports this).
"""

import json
import os
import re
import stat
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
    """The text of a top-level marker file, or None: missing, a link, not regular, over MAX_BYTES or unreadable.
    The file is opened without following a link and without waiting on a FIFO, then checked to be a regular file
    by its descriptor, so nothing swapped in after _regular() is followed or blocks (review round 1)."""
    p = _regular(root, name)
    if p is None:
        return None
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(p), flags)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_BYTES:
            return None
        chunks, size = [], 0
        while size <= MAX_BYTES:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    except OSError:
        return None
    finally:
        os.close(fd)
    data = b"".join(chunks)
    return None if len(data) > MAX_BYTES else data.decode("utf-8-sig", errors="replace")


def _json(root, name):
    text = _read(root, name)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):  # deep nesting raises RecursionError (review round 1)
        return None
    return data if isinstance(data, dict) else None


DTD_RE = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.I)


def _xml(root, name):
    """The parsed XML, or None. A DTD or entity declaration is refused before parsing: an old expat doesn't limit
    entity expansion, and a build file needs neither."""
    text = _read(root, name)
    if text is None or DTD_RE.search(text):
        return None
    try:
        return ElementTree.fromstring(text)
    except (ElementTree.ParseError, RecursionError, ValueError):
        return None


def _parses(root, name):
    """True when a present marker can be read by the parser its family uses (json, xml or text)."""
    if name == "package.json":
        return _json(root, name) is not None
    if name == "pom.xml":
        return _xml(root, name) is not None
    if name.startswith("build.gradle"):
        return _read(root, name) is not None
    return True  # python and go markers are only looked at, never parsed


def _families(root):
    """([families whose markers are present and parse], [present markers that don't parse]), in FAMILIES order.
    A marker that fails its parser counts as absent (R-2) and is named in the note."""
    found, broken = [], []
    for fam, names in FAMILIES.items():
        present = [n for n in names if _regular(root, n)]
        ok = [n for n in present if _parses(root, n)]
        broken += [n for n in present if n not in ok]
        if ok:
            found.append(fam)
    return found, broken


def _unparsed(broken):
    return f" ({', '.join(broken)} can't be read: a link, over 1 MiB, or not valid)" if broken else ""


def none(note):
    return Detection(None, None, {}, [], note)


def detect(root, force=None):
    """The Detection for root. `force` (a KINDS name) skips the family choice but still reads the repo."""
    root = Path(root)
    if force is not None:
        if force not in KINDS:
            raise ValueError(f"unknown stack {force!r} (one of: {', '.join(KINDS)})")
        family = FAMILY_OF[force]
        if family in ("python", "go"):  # a preset: it reads nothing, as --stack python|go always did
            return DETECTORS[family](root, force)
        if not any(_regular(root, n) for n in FAMILIES[family]):
            return none(f"--stack {force} needs {' or '.join(FAMILIES[family])} at the repo top; nothing was wired")
    else:
        found, broken = _families(root)
        if not found:
            return none("no stack detected: no build file at the repo top" + _unparsed(broken))
        if len(found) > 1:
            return none(
                f"no stack chosen: the repo top has more than one ({', '.join(found)}); "
                f"pass --stack {'|'.join(found)}" + _unparsed(broken)
            )
        family = found[0]
        if broken:
            det = DETECTORS[family](root, force)
            return det._replace(note=(det.note + "; " if det.note else "") + _unparsed(broken).strip(" ()"))
    return DETECTORS[family](root, force)


NODE_SCRIPTS = (
    ("format", ("format", "prettier")),
    ("lint", ("lint",)),
    ("typecheck", ("typecheck", "type-check", "tsc")),
    ("test", ("test:ci", "test")),
    ("build", ("build",)),
)
NPM_PLACEHOLDER = "no test specified"
NODE_LABELS = {"node": "Node", "react": "React", "angular": "Angular"}


def _node_family(root, force):
    pkg = _json(root, "package.json")
    if pkg is None:
        return none("no stack detected: package.json can't be read as JSON (or is a link, or over 1 MiB)")
    evidence = ["package.json"]
    scripts = pkg.get("scripts")
    scripts = {k: v for k, v in scripts.items() if isinstance(v, str)} if isinstance(scripts, dict) else {}
    deps = {}
    for key in ("dependencies", "devDependencies"):
        if isinstance(pkg.get(key), dict):
            deps.update(pkg[key])
    angular = _json(root, "angular.json") if _regular(root, "angular.json") else None
    if force:
        kind = force
    elif _regular(root, "angular.json"):
        kind = "angular"
    elif "react" in deps:
        kind = "react"
    else:
        kind = "node"
    pm = "npm"
    for lock, name in LOCKFILES:
        if _regular(root, lock):
            pm = name
            evidence.append(lock)
            break
    recipes = {}
    for target, names in NODE_SCRIPTS:
        for name in names:
            body = scripts.get(name)
            if body is None:  # names come from NODE_SCRIPTS, never from the repo: no repo text reaches a recipe
                continue
            if name == "test" and NPM_PLACEHOLDER in body:
                continue
            cmd = f"{pm} run {name}"
            if name == "test" and kind == "react" and re.search(r"\breact-scripts\s+test\b", body):
                cmd = f"CI=true {cmd}"  # CRA's test watches unless CI is set
            elif name == "test" and kind == "angular" and re.search(r"\bng\s+test\b", body):
                cmd += " -- --watch=false" + (" --browsers=ChromeHeadless" if _karma(angular) else "")
            recipes[target] = cmd
            break
    if "typecheck" not in recipes and _regular(root, "tsconfig.json"):
        recipes["typecheck"] = "npx tsc --noEmit"
        evidence.append("tsconfig.json")
    note = ""
    if kind == "angular" and angular is not None:
        evidence.append("angular.json")
    elif kind == "angular" and _regular(root, "angular.json"):
        note = "angular.json can't be read, so a Karma test runs without --browsers=ChromeHeadless"
    ordered = {t: recipes[t] for t in TARGETS if t in recipes}
    return Detection(kind, NODE_LABELS[kind], ordered, evidence, note)


def _karma(angular):
    """True when an angular.json test target uses the Karma builder (it opens a browser)."""
    if not isinstance(angular, dict) or not isinstance(angular.get("projects"), dict):
        return False
    for project in angular["projects"].values():
        architect = project.get("architect") if isinstance(project, dict) else None
        test = architect.get("test") if isinstance(architect, dict) else None
        if isinstance(test, dict) and str(test.get("builder", "")).endswith(":karma"):
            return True
    return False


GRADLE_CHECKSTYLE = re.compile(
    r"""(\bid\s*\(?\s*['"]checkstyle['"]|(^|[{;])\s*checkstyle\s*($|[;}])|plugin:\s*['"]checkstyle['"])""", re.M
)
GRADLE_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _children(el, name):
    return [c for c in el if _local(c.tag) == name]


def _artifact(el):
    ids = _children(el, "artifactId")
    return (ids[0].text or "").strip() if ids else ""


def _maven_ids(tree):
    """(the parent's artifactId, the artifactIds of project/build/plugins/plugin): plugins under pluginManagement or
    reporting don't run in `mvn compile|test`, so they don't count."""
    parent = "".join(_artifact(p) for p in _children(tree, "parent"))
    plugins = {
        _artifact(plugin)
        for build in _children(tree, "build")
        for group in _children(build, "plugins")
        for plugin in _children(group, "plugin")
    }
    return parent, plugins


def _wrapper(root, name, fallback, evidence):
    """`./<name>` when the repo has it as an executable regular file at the top, else the installed tool."""
    p = _regular(root, name)
    if p is not None and os.access(p, os.X_OK):
        evidence.append(name)
        return f"./{name}"
    return fallback


def _java(root, force):
    if _regular(root, "pom.xml"):
        tree = _xml(root, "pom.xml")
        if tree is None:
            return none("no stack detected: pom.xml can't be read as XML (or is a link, or over 1 MiB)")
        parent, ids = _maven_ids(tree)
        evidence = ["pom.xml"]
        run = _wrapper(root, "mvnw", "mvn", evidence) + " -B -q"
        boot = parent == "spring-boot-starter-parent" or "spring-boot-maven-plugin" in ids
        recipes = {}
        if "spotless-maven-plugin" in ids:
            recipes["format"] = f"{run} spotless:apply"
        if "maven-checkstyle-plugin" in ids:
            recipes["lint"] = f"{run} checkstyle:check"
        recipes.update(typecheck=f"{run} compile", test=f"{run} test", build=f"{run} package -DskipTests")
        tool = "Maven"
    else:
        name = "build.gradle.kts" if _regular(root, "build.gradle.kts") else "build.gradle"
        text = _read(root, name)
        if text is None:
            return none(f"no stack detected: {name} can't be read (or is a link, or over 1 MiB)")
        evidence = [name]
        text = GRADLE_COMMENT.sub("", text)  # a commented-out plugin doesn't count
        run = _wrapper(root, "gradlew", "gradle", evidence) + " -q"
        boot = "org.springframework.boot" in text
        recipes = {}
        if "com.diffplug.spotless" in text:
            recipes["format"] = f"{run} spotlessApply"
        if GRADLE_CHECKSTYLE.search(text):
            recipes["lint"] = f"{run} checkstyleMain"
        recipes.update(typecheck=f"{run} classes", test=f"{run} test", build=f"{run} assemble")
        tool = "Gradle"
    label = "Java · Spring Boot · " + tool if boot else "Java · " + tool
    return Detection("java", label, recipes, evidence, "")


def parse_recipes(text):
    """{target: command} from a templates/stacks/*.recipes text (`<target> <command>` lines, `#` comments). The one
    recipe parser: cli.parse_recipes is this function."""
    out = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and not parts[0].startswith("#"):
            out[parts[0]] = parts[1]
    return out


def preset(name):
    """{target: command} from the running plugin's templates/stacks/<name>.recipes (python, node, go)."""
    return parse_recipes((STACKS_DIR / f"{name}.recipes").read_text())


# The grammar of every recipe this module can emit. lifecycle.recipes_ok accepts a recorded recipe only if it matches,
# so a tampered install-state can't carry `$(shell …)`, `;`, a pipe or a redirection into the Makefile (review round 1).
EMITTABLE = (
    re.compile(
        r"^(CI=true )?(npm|pnpm|yarn|bun) run (format|prettier|lint|typecheck|type-check|tsc|test:ci|test|build)"
        r"( -- --watch=false( --browsers=ChromeHeadless)?)?$"
    ),
    re.compile(r"^npx tsc --noEmit$"),
    re.compile(r"^(\./mvnw|mvn) -B -q (spotless:apply|checkstyle:check|compile|test|package -DskipTests)$"),
    re.compile(r"^(\./gradlew|gradle) -q (spotlessApply|checkstyleMain|classes|test|assemble)$"),
)


def emittable(cmd):
    """True when cmd is a recipe detection or a preset of the running plugin can produce."""
    if not isinstance(cmd, str):
        return False
    if any(rx.match(cmd) for rx in EMITTABLE):
        return True
    return any(cmd in preset(name).values() for name in ("python", "node", "go"))


def _python(root, force):
    return Detection("python", "Python", preset("python"), [n for n in FAMILIES["python"] if _regular(root, n)], "")


def _go(root, force):
    return Detection("go", "Go", preset("go"), ["go.mod"], "")


DETECTORS = {"java": _java, "node": _node_family, "python": _python, "go": _go}
