"""Validate an artifact against schemas/<kind>.json plus cross-artifact rules (AC coverage, ids)."""

import re

from . import artifacts as A
from .machine import SCHEMAS, read

PLACEHOLDER_RE = re.compile(r"^\s*(?:- )?<[^<>\n]{3,}>\s*$", re.M)
HEX_RE = re.compile(r"^[0-9a-f]{7,40}$")
DSL_FILE_RE = re.compile(r"\bdomain/[A-Za-z0-9][A-Za-z0-9_.-]*\.dsl\.json\b")
NO_DOMAIN_RE = re.compile(r"(?m)^\s*(?:[-*]\s+)?No domain changes\b")
WARN_ACS = 5  # more ACs than this: the scope may be an epic (warning)
MAX_ACS = 8  # more than this while the spec's gate is closed: an error, so it must be split before approval


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
        found = CHECKS[check](d, a, secs, text)
        if isinstance(found, tuple):  # a check may also warn: (errors, warnings)
            errors += found[0]
            warnings += found[1]
        else:
            errors += found
    return errors, warnings


def _has_acs(d, a, secs, text):
    return (
        []
        if A.ac_ids(secs.get("Acceptance criteria", ""))
        else ["`## Acceptance criteria` has no testable criteria with ids (AC-1, AC-2, ...)"]
    )


def _has_steps(d, a, secs, text):
    return [] if A.checkboxes(secs.get("Steps", "")) else ["`## Steps` has no checkbox steps (`- [ ] S1 ...`)"]


def _covers_spec_acs(d, a, secs, text):
    spec = read(d, "spec")
    if spec is None:
        return []
    wanted = A.ac_ids(A.sections(A.parse(spec).body).get("Acceptance criteria", ""))
    have = set(A.ac_ids(a.body))
    missing = [ac for ac in wanted if ac not in have]
    return (
        [f"does not reference {', '.join(missing)} from spec.md (every AC needs a test definition / verdict)"]
        if missing
        else []
    )


def _valid_verdict(d, a, secs, text):
    errs = []
    if a.get("verdict") and a.get("verdict") not in SCHEMAS["review"]["verdicts"]:
        errs.append(f"verdict `{a.get('verdict')}` must be PASS or CHANGES_REQUESTED")
    if a.get("commit") and not HEX_RE.match(a.get("commit")):
        errs.append("commit must be the reviewed git sha (git rev-parse HEAD)")
    return errs


def _scope_size(d, a, secs, text):
    """Distinct AC ids in `## Acceptance criteria`: above WARN_ACS a warning; above MAX_ACS an error while the gate is
    closed (judged on `text`, as machine.gate() judges the file), so approved history only warns (0011)."""
    n = len(A.ac_ids(secs.get("Acceptance criteria", "")))
    if n > MAX_ACS and not _gate_open("spec", a, text):
        return [
            f"Spec exceeds maximum of {MAX_ACS} acceptance criteria; consolidate behavioral outcomes or split into "
            f"smaller intents. (spec.md has {n}.)"
        ], []
    if n > WARN_ACS:
        return [], [
            f"`## Acceptance criteria` has {n} criteria (more than {WARN_ACS}): the scope may be too large for one "
            "intent; consider splitting it into smaller intents"
        ]
    return [], []


def _gate_open(kind, a, text):
    """The gate test of machine.gate() on the text being validated (it may not be on disk yet)."""
    return a.get("status") == SCHEMAS[kind]["gate"] and a.get("approved-sha256") == A.approval_hash(kind, text)


def _domain_dsl(d, a, secs, text):
    """While the dsl part is active and the spec's gate is closed, `## Domain DSL` names the domain/*.dsl.json files
    the change adds or edits, or says `No domain changes` (0012 R-6). Approved, unchanged specs are exempt, so turning
    the part on in a repo with history adds no error to it."""
    from .lifecycle import dsl_active

    if not dsl_active(d.parent.parent) or _gate_open("spec", a, text):
        return []
    forms = (
        "name the domain/<name>.dsl.json files this change adds or edits (model first: the Data model and API "
        "contracts follow from it), or write `No domain changes` with a reason for a purely technical or UI change"
    )
    if "Domain DSL" not in secs:
        return [f"`## Domain DSL` is missing; it is required while the dsl part is active (domain/ exists or "
                f"install-state names dsl): {forms}"]
    body = A.COMMENT_RE.sub("", secs["Domain DSL"])
    if NO_DOMAIN_RE.search(body) or DSL_FILE_RE.search(body):
        return []
    return [f"`## Domain DSL` doesn't say what changes in the domain model: {forms}"]


CHECKS = {
    "has_acceptance_criteria": _has_acs,
    "has_steps": _has_steps,
    "covers_spec_acs": _covers_spec_acs,
    "valid_verdict": _valid_verdict,
    "scope_size": _scope_size,
    "domain_dsl": _domain_dsl,
}
