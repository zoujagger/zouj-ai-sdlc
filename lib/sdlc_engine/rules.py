"""The guard rule registry: defaults/rules (one line per rule, greppable by the bash hooks) and defaults/rules.md
(the reason and the safe alternative per rule). `sdlc why <id>` reads both."""
import difflib
import re
from pathlib import Path
from typing import NamedTuple

from .machine import PLUGIN_ROOT

REGISTRY = PLUGIN_ROOT / "defaults" / "rules"
DOCS = PLUGIN_ROOT / "defaults" / "rules.md"
CLASSES = ("gate", "secret", "toolchain", "safety", "heuristic", "retired")
ALLOWABLE = {"heuristic"}            # the only class an exact-command allowance can lift
ID_RE = re.compile(r"^G-[A-Z]+-\d\d$")


class Rule(NamedTuple):
    id: str
    cls: str
    stage: str
    summary: str
    why: str = ""
    instead: str = ""


def parse_registry(text):
    """{id: Rule} from the registry text. Raises ValueError on a malformed or duplicate line."""
    out = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split(None, 3)
        if len(parts) != 4:
            raise ValueError(f"defaults/rules:{n}: expected `<id> <class> <stage> <summary>`: {line!r}")
        rid, cls, stage, summary = parts
        if not ID_RE.match(rid):
            raise ValueError(f"defaults/rules:{n}: bad id {rid!r} (G-<AREA>-NN)")
        if cls not in CLASSES:
            raise ValueError(f"defaults/rules:{n}: unknown class {cls!r} ({', '.join(CLASSES)})")
        if rid in out:
            raise ValueError(f"defaults/rules:{n}: duplicate id {rid}")
        out[rid] = Rule(rid, cls, stage, summary.strip())
    return out


def parse_docs(text):
    """{id: (why, instead)} from rules.md `## <id>` sections."""
    out, cur, fields = {}, None, {}
    for line in text.splitlines() + ["## END"]:
        if line.startswith("## "):
            if cur:
                out[cur] = (fields.get("why", ""), fields.get("instead", ""))
            cur, fields, key = line[3:].strip(), {}, None
            continue
        m = re.match(r"^(Why|Instead):\s*(.*)$", line)
        if m:
            key = m.group(1).lower()
            fields[key] = m.group(2).strip()
        elif cur and line.strip() and fields:
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return out


def load():
    """{id: Rule} with the rules.md text attached."""
    reg = parse_registry(REGISTRY.read_text())
    docs = parse_docs(DOCS.read_text()) if DOCS.is_file() else {}
    return {rid: r._replace(why=docs.get(rid, ("", ""))[0], instead=docs.get(rid, ("", ""))[1])
            for rid, r in reg.items()}


STAGES = {   # the stage column of defaults/rules, as `sdlc why` prints it
    "intent-spec-plan": "the human gates (Intent, Spec, Plan Approved)",
    "read-only-lock": "the read-only lock in states 1-3",
    "artifacts": "the artifacts and .aiops/ (the audit trail)",
    "every-stage": "human-owned files, in every state",
    "merge": "the merge and main (state 5, the human's decision)",
    "deploy": "production (the human's deploy approval)",
    "test-lock": "the /fix test lock",
    "definition-of-done": "the definition of done (make check green)",
    "setup": "setup (scaffold only the session's repo)",
    "every-repo": "safety, in every repo (initialized or not)",
    "initialized-repo": "safety, in repos initialized with sdlc init (.aiops/)",
}


def why(rid):
    """(exit code, text): the explanation of a rule, or near matches for an unknown id."""
    reg = load()
    rid = rid.strip().upper()
    r = reg.get(rid)
    if r is None:
        near = difflib.get_close_matches(rid, list(reg), n=5, cutoff=0.6)
        return 1, f"unknown rule id {rid!r}." + (f" Did you mean: {', '.join(near)}?" if near else
                                                  " The ids are listed in the plugin's defaults/rules.")
    if r.cls in ALLOWABLE:
        allow = (f"allowable class: the human can let one exact command through this rule by adding the line "
                 f"`{r.id} <the exact command>` to .aiops/config/allowed-commands (human-owned, under CODEOWNERS). "
                 "Only that command, and only this rule: every other rule still applies.")
    else:
        allow = f"no allowance: {r.cls} rules can't be lifted (there is no per-rule disable switch)."
    return 0, "\n".join([
        f"{r.id}: {r.summary}",
        f"  class: {r.cls}",
        f"  protects: {STAGES.get(r.stage, r.stage)}",
        f"  why: {r.why}",
        f"  instead: {r.instead}",
        f"  allowance: {allow}",
    ])


ALLOWANCES = ".aiops/config/allowed-commands"     # human-owned: protected by .aiops/config* and CODEOWNERS
ENTRY_RE = re.compile(r"^(\S+)(?:[ \t]+(.*?))?[ \t]*$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")   # any control character but tab: no multi-line, no \r tricks


def _entries(text):
    """[(line number, id, command or "")] for each non-comment line of an allowed-commands file."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = ENTRY_RE.match(line)
        out.append((n, m.group(1), m.group(2) or "") if m else (n, line.strip(), ""))
    return out


# G-ENV-03 allowances accept only commands that can't print the whole environment (0005, gap 6): `printenv NAME…`,
# or a command that doesn't run env/printenv at all. Anything else is refused: no list of known dumps to outgrow.
SAFE_ENV_COMMANDS = {"ls", "cd", "cat", "head", "tail", "wc", "file", "stat", "du", "tree", "source", ".",
                     "virtualenv"}                    # commands that never run their arguments
ENV_WORD_RE = re.compile(r"(^|/)(env|printenv)$")
SUBSTITUTION_RE = re.compile(r"\$\(|`|<\(|>\(|[<>]")


def safe_env_command(command):
    """True if the command can't print the whole environment: every simple command is `printenv NAME…` (names only),
    or doesn't mention env/printenv as a word, or is one of SAFE_ENV_COMMANDS (or `python -m venv`) with env only
    as an argument. Substitutions and redirections are refused outright."""
    import shlex
    if SUBSTITUTION_RE.search(command):
        return False
    for part in re.split(r"[;&|\n(){}]+", command):
        try:
            words = shlex.split(part)
        except ValueError:
            return False
        while words and re.match(r"^[A-Za-z_]\w*=", words[0]):
            words = words[1:]
        if not words:
            continue
        name, args = Path(words[0]).name, words[1:]
        if name == "printenv":
            if args and all(re.match(r"^[A-Za-z_]\w*$", a) for a in args):
                continue
            return False
        if not any(ENV_WORD_RE.search(w) for w in words):
            continue
        if name in SAFE_ENV_COMMANDS or (name in ("python", "python3") and args[:2] == ["-m", "venv"]):
            continue
        return False
    return True


def dumps_environment(command):
    """Deprecated alias (0.2.0-alpha.3): True if the command isn't a safe G-ENV-03 form."""
    return not safe_env_command(command)


def allowed(root, rule_id, command):
    """True only if rule_id is in an allowable class and `<rule_id> <command>` is listed, byte-equal, in the repo's
    allowed-commands. The command is compared after trimming surrounding spaces, tabs and newlines, and must hold no
    other control character. An allowance lifts this one rule for this one command; callers keep checking the rest."""
    r = load().get(rule_id)
    if r is None or r.cls not in ALLOWABLE:
        return False
    cmd = (command or "").strip(" \t\n")
    if not cmd or CONTROL_RE.search(cmd):
        return False
    if rule_id == "G-ENV-03" and not safe_env_command(cmd):   # could print every token: never allowable
        return False
    f = Path(root) / ALLOWANCES
    try:
        text = f.read_text() if f.is_file() and not f.is_symlink() else ""
    except (OSError, UnicodeDecodeError):
        return False
    return any(rid == rule_id and entry == cmd for _, rid, entry in _entries(text))


def allowance_problems(text):
    """Why each allowed-commands entry is refused: an unknown id, a class that can't be allowed, or no command.
    The hooks ignore such entries; doctor and `validate --ci` report them."""
    reg, probs = load(), []
    for n, rid, cmd in _entries(text):
        r = reg.get(rid)
        if not ID_RE.match(rid):                          # never echo text that isn't a rule id
            probs.append(f"line {n}: doesn't start with a rule id (format: `<rule id> <exact command>`)")
        elif r is None:
            probs.append(f"line {n}: unknown rule id {rid} (see `sdlc why`)")
        elif r.cls not in ALLOWABLE:
            probs.append(f"line {n}: {rid} is a {r.cls} rule; only heuristic rules "
                         f"({', '.join(sorted(k for k, v in reg.items() if v.cls in ALLOWABLE))}) can be allowed")
        elif not cmd:
            probs.append(f"line {n}: {rid} has no command (format: `<rule id> <exact command>`)")
        elif CONTROL_RE.search(cmd):
            probs.append(f"line {n}: the command contains a control character")
        elif rid == "G-ENV-03" and not safe_env_command(cmd):
            probs.append(f"line {n}: G-ENV-03 allows only `printenv NAME…` or a command that doesn't run env/printenv "
                         "(it could print the whole environment)")
    return probs
