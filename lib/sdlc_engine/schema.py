"""Validate an artifact against schemas/<kind>.json plus cross-artifact rules (AC coverage, ids)."""
import re

from . import artifacts as A
from .machine import SCHEMAS, read

PLACEHOLDER_RE = re.compile(r"^\s*(?:- )?<[^<>\n]{3,}>\s*$", re.M)
HEX_RE = re.compile(r"^[0-9a-f]{7,40}$")


def validate(d, kind, text=None):
    """(errors, warnings) for `kind` in intent dir `d`. `text` overrides the file on disk (hook simulation)."""
    schema = SCHEMAS[kind]
    text = read(d, kind) if text is None else text
    if text is None:
        return [f"{kind}.md does not exist"], []
    errors, warnings = [], []
    a = A.parse(text)
    if not a.has_front:
        return [f"{kind}.md has no front matter (--- block)"], []
    for f in schema["front"]:
        if not a.get(f):
            errors.append(f"front matter `{f}` is missing or empty")
    if schema["statuses"] and a.get("status") and a.get("status") not in schema["statuses"]:
        errors.append(f"status `{a.get('status')}` is not one of {', '.join(schema['statuses'])}")
    if a.get("id") and a.get("id") != d.name[:4]:
        errors.append(f"id `{a.get('id')}` does not match the folder {d.name}")
    secs = A.sections(a.body)
    for s in schema["sections"]:
        if s not in secs:
            errors.append(f"missing section `## {s}`")
        elif PLACEHOLDER_RE.search(secs[s]):
            warnings.append(f"section `## {s}` still contains a template placeholder")
    for check in schema["checks"]:
        errors += CHECKS[check](d, a, secs)
    return errors, warnings


def _has_acs(d, a, secs):
    return [] if A.ac_ids(secs.get("Acceptance criteria", "")) else \
        ["`## Acceptance criteria` has no testable criteria with ids (AC-1, AC-2, ...)"]


def _has_steps(d, a, secs):
    return [] if A.checkboxes(secs.get("Steps", "")) else \
        ["`## Steps` has no checkbox steps (`- [ ] S1 ...`)"]


def _covers_spec_acs(d, a, secs):
    spec = read(d, "spec")
    if spec is None:
        return []
    wanted = A.ac_ids(A.sections(A.parse(spec).body).get("Acceptance criteria", ""))
    have = set(A.ac_ids(a.body))
    missing = [ac for ac in wanted if ac not in have]
    return [f"does not reference {', '.join(missing)} from spec.md (every AC needs a test definition / verdict)"] \
        if missing else []


def _valid_verdict(d, a, secs):
    errs = []
    if a.get("verdict") and a.get("verdict") not in SCHEMAS["review"]["verdicts"]:
        errs.append(f"verdict `{a.get('verdict')}` must be PASS or CHANGES_REQUESTED")
    if a.get("commit") and not HEX_RE.match(a.get("commit")):
        errs.append("commit must be the reviewed git sha (git rev-parse HEAD)")
    return errs


CHECKS = {"has_acceptance_criteria": _has_acs, "has_steps": _has_steps,
          "covers_spec_acs": _covers_spec_acs, "valid_verdict": _valid_verdict}
