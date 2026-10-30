"""Derive the lifecycle state of each intent from its artifacts and git. State is computed, never stored.

  1 BRAINSTORMING  intent.md missing, Draft, or changed since approval
  2 SPECIFICATION  spec.md  missing, Draft, or changed since approval
  3 PLAN           plan.md  missing, Draft, or changed since approval   (read-only: no code edits)
  4 EXECUTION      plan approved, Steps still open                       (autonomous TDD loop)
  5 PRE-REVIEW     all Steps done; review.md missing, failing, stale, or PASS awaiting the human merge
  6 DONE           review.md (PASS) is on the main branch
  0 CLOSED         intent closed by a human
"""
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path

from . import artifacts as A

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
KINDS = ("intent", "spec", "plan", "review")
SCHEMAS = {k: json.loads((PLUGIN_ROOT / "schemas" / f"{k}.json").read_text()) for k in KINDS}
STATE_NAMES = {0: "CLOSED", 1: "BRAINSTORMING", 2: "SPECIFICATION", 3: "PLAN", 4: "EXECUTION", 5: "PRE-REVIEW", 6: "DONE"}
LOCKED_STATES = (1, 2, 3)
DIR_RE = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*$")
BRANCH_RE = re.compile(r"(?:^|/)(\d{4})-")
DEFAULT_CONFIG = {"lock_when_idle": True, "commit_approvals": True, "main_branch": "main",
                  "require_signed_approvals": False}


def git(root, *args):
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def project_root(start=None):
    """Git top level of `start` (worktree-aware), else CLAUDE_PROJECT_DIR, else start."""
    start = Path(start or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    top = git(start, "rev-parse", "--show-toplevel") if start.is_dir() else None
    return Path(top or start).resolve()


def initialized(root):
    return (root / ".aiops").is_dir()


def config(root):
    cfg = dict(DEFAULT_CONFIG)
    f = root / ".aiops" / "config.json"
    if f.is_file():
        try:
            cfg.update(json.loads(f.read_text()))
        except ValueError:
            pass
    return cfg


def globs(root, name):
    """[(glob, reason)] from the plugin defaults plus the project's .aiops/config/<name>."""
    out = []
    for f in (PLUGIN_ROOT / "defaults" / name, root / ".aiops" / "config" / name):
        if f.is_file():
            for line in f.read_text().splitlines():
                glob, _, reason = line.strip().partition(" ")
                if glob and not glob.startswith("#"):
                    out.append((glob, reason.strip()))
    return out


def glob_hit(rel, patterns):
    """Bash-style glob match (`*` crosses `/`), mirroring hooks/lib.sh glob_match."""
    return next(((g, r) for g, r in patterns if fnmatchcase(rel, g)), None)


def intent_dirs(root):
    base = root / ".aiops"
    return sorted(d for d in base.iterdir() if d.is_dir() and DIR_RE.match(d.name)) if base.is_dir() else []


def find_dir(root, ident):
    ident = str(ident).strip()
    for d in intent_dirs(root):
        if d.name == ident or d.name[:4] == ident.zfill(4)[:4]:
            return d
    return None


def current_branch(root):
    return git(root, "branch", "--show-current") or ""


def active_dir(root):
    """The intent this session works on: $AIOPS_INTENT, else the branch's NNNN, else .aiops/state/active."""
    if os.environ.get("AIOPS_INTENT"):
        return find_dir(root, os.environ["AIOPS_INTENT"])
    m = BRANCH_RE.search(current_branch(root))
    if m and (d := find_dir(root, m.group(1))):
        return d
    f = root / ".aiops" / "state" / "active"
    if f.is_file():
        return find_dir(root, f.read_text().strip())
    return None


def read(d, kind):
    p = d / f"{kind}.md"
    return p.read_text() if p.is_file() else None


def gate(d, kind):
    """(open, why) for a human gate: status is the gate value and the body is unchanged since approval."""
    text = read(d, kind)
    if text is None:
        return False, "missing"
    a = A.parse(text)
    want = SCHEMAS[kind]["gate"]
    if a.get("status") != want:
        return False, f"status is {a.get('status') or 'unset'}"
    if a.get("approved-sha256") != A.approval_hash(kind, text):
        return False, "changed since approval"
    return True, ""


def phrase(kind, ident):
    return f"{SCHEMAS[kind]['approval_phrase']} {ident}"


@dataclass
class Status:
    id: str
    dir: Path
    state: int
    detail: str
    next: str
    waiting_on: str = "agent"   # agent | human
    steps_done: int = 0
    steps_total: int = 0
    open_questions: int = 0
    deviations: int = 0
    gates: dict = field(default_factory=dict)

    @property
    def name(self):
        return STATE_NAMES[self.state]

    def as_dict(self):
        return {"id": self.id, "dir": str(self.dir), "state": self.state, "name": self.name, "detail": self.detail,
                "next": self.next, "waiting_on": self.waiting_on, "steps": [self.steps_done, self.steps_total],
                "open_questions": self.open_questions, "deviations": self.deviations, "gates": self.gates}


def _pending_gate(ident, d, kind, state, why, skill):
    if why == "missing":
        return Status(ident, d, state, f"{kind}.md not written yet", f"/zouj-ai-sdlc:{skill} {ident}")
    if why == "changed since approval":
        return Status(ident, d, state, f"{kind}.md changed after it was approved; the approval no longer holds",
                      f"human re-approves: type `{phrase(kind, ident)}`", "human")
    return Status(ident, d, state, f"{kind}.md is drafted ({why}); waiting for human sign-off",
                  f"human types `{phrase(kind, ident)}` (or asks for changes)", "human")


def review_stale(root, commit):
    """True if code outside .aiops changed after the reviewed commit (committed or not)."""
    if not commit or git(root, "cat-file", "-e", f"{commit}^{{commit}}") is None:
        return True
    changed = git(root, "diff", "--name-only", commit, "--", ".", ":(exclude).aiops")
    dirty = git(root, "status", "--porcelain", "--", ".", ":(exclude).aiops")
    return bool(changed) or bool(dirty)


def evaluate(root, d):
    ident = d.name[:4]
    st = _evaluate(root, d, ident)
    st.gates = {k: gate(d, k)[0] for k in ("intent", "spec", "plan")}
    for kind in ("intent", "spec"):
        text = read(d, kind)
        if text:
            st.open_questions += len([1 for s, _ in A.checkboxes(A.sections(A.parse(text).body).get("Open questions", ""))
                                      if s != "x"])
    plan = read(d, "plan")
    if plan:
        log = A.sections(A.parse(plan).body).get("Deviation log", "")
        st.deviations = len([ln for ln in log.splitlines() if ln.startswith("|") and not re.match(r"^\|[\s|:-]*\|?$", ln)
                             and not ln.lower().startswith("| date")])
    return st


def _evaluate(root, d, ident):
    intent = read(d, "intent")
    if intent and A.parse(intent).get("status") == "Closed":
        return Status(ident, d, 0, "closed by a human", "none (start a new intent with /zouj-ai-sdlc:intent)")
    for state, kind, skill in ((1, "intent", "intent"), (2, "spec", "spec"), (3, "plan", "plan")):
        ok, why = gate(d, kind)
        if not ok:
            return _pending_gate(ident, d, kind, state, why, skill)
    steps = A.checkboxes(A.sections(A.parse(read(d, "plan")).body).get("Steps", ""))
    done = sum(1 for s, _ in steps if s == "x")
    if done < len(steps) or not steps:
        nxt = next((t for s, t in steps if s != "x"), "")
        st = Status(ident, d, 4, f"executing: next step {nxt[:80]}", f"/zouj-ai-sdlc:implement {ident}")
    else:
        st = _review_state(root, d, ident)
    st.steps_done, st.steps_total = done, len(steps)
    return st


def _review_state(root, d, ident):
    text = read(d, "review")
    if text is None:
        return Status(ident, d, 5, "all steps done; no review yet", f"/zouj-ai-sdlc:review {ident}")
    a = A.parse(text)
    main = config(root)["main_branch"]
    rel = f".aiops/{d.name}/review.md"
    on_main = git(root, "show", f"{main}:{rel}")
    if on_main and A.parse(on_main).get("verdict") == "PASS" and current_branch(root) == main:
        return Status(ident, d, 6, f"merged into {main}", "none (Maintain: /zouj-ai-sdlc:triage on alerts)")
    if a.get("verdict") != "PASS":
        return Status(ident, d, 5, f"review verdict {a.get('verdict') or 'unset'}: fix the findings",
                      f"/zouj-ai-sdlc:implement {ident}, then /zouj-ai-sdlc:review {ident}")
    if review_stale(root, a.get("commit")):
        return Status(ident, d, 5, "code changed after the review; it no longer covers HEAD",
                      f"/zouj-ai-sdlc:review {ident}")
    return Status(ident, d, 5, f"review PASS (score {a.get('score')}); waiting for the human merge decision",
                  f"/zouj-ai-sdlc:pr {ident}, then a human reviews and merges", "human")


def profile():
    p = os.environ.get("SDLC_HOOK_PROFILE", "standard")
    return p if p in ("strict", "spike") else "standard"


def lock(root):
    """(locked, reason, Status|None): is editing code outside .aiops/ forbidden right now?"""
    if not initialized(root):
        return False, "repo not initialized", None
    if profile() == "spike":
        return False, "spike profile", None
    d = active_dir(root)
    idle = config(root)["lock_when_idle"]
    if d is None:
        if idle:
            return True, "no active intent: code changes start from an intent", None
        return False, "no active intent", None
    st = evaluate(root, d)
    if st.state in LOCKED_STATES:
        return True, f"intent {st.id} is in state {st.state} {st.name} (read-only until `Plan Approved`)", st
    if st.state in (0, 6) and idle:
        return True, f"intent {st.id} is {st.name}; start a new intent for further changes", st
    return False, f"intent {st.id} is in state {st.state} {st.name}", st
