"""The guard rule registry: defaults/rules (one line per rule, greppable by the bash hooks) and defaults/rules.md
(the reason and the safe alternative per rule). `sdlc why <id>` reads both."""
import difflib
import re
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


STAGES = {"every-repo": "safety, in every repo (initialized or not)"}


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
        allow = (f"an exact-command allowance is possible: the human adds `{r.id} <the exact command>` to "
                 ".aiops/config/allowed-commands (human-owned, under CODEOWNERS). It lifts only this rule, for only "
                 "that command.")
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
