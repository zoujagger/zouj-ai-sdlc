---
id: 0012
title: Opt-in dsl part: a validated domain/ model for specs and plans
status: Approved
risk: medium           # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T16:24:06Z
approved-via: cli
approved-sha256: f55cbd3cb110c4bb41998da710cdceebec738532df3fd678b5cabdc155bdb7a6
---

# Spec: Opt-in dsl part: a validated domain/ model for specs and plans

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md, translated into engineering
     requirements. The intent's three questions were answered before its approval: JSON model files, activation by
     install-state or `domain/`, and a required spec section. The spec's two questions were answered by zoujagger
     before approval: `--with all` leaves `dsl` out, and `domain/` stays unprotected. Risk is medium: the Makefile template and the part
     lists reach every adopter through `upgrade`. Policy skills applied (security, compliance). -->

## Summary
This adds an opt-in `dsl` part for teams that want domain-first modeling (intent: Desired outcome):

- `sdlc setup --with dsl` installs `domain/README.md` and a stdlib validator, `scripts/validate-dsl.py`.
- The core Makefile's `check` runs a `validate-dsl` target. It stays dormant until `domain/` exists.
- While the part is active, `spec.md` must have a `## Domain DSL` section, and the spec and plan skills model the
  domain before the storage and transport layers.

The model format is domain-neutral JSON (`domain/*.dsl.json`) with three kinds: state machines, rule sets and
workflows. Implement-time ordering and the review's hardcoding check are the next intent (0013).

## Requirements
- **R-1: the part.**
  - `lifecycle.PARTS` gains `dsl`, and `defaults/scaffold-parts` maps `domain/*` and `scripts/validate-dsl.py` to
    it.
  - `--with dsl` installs it the way the other parts are installed: only missing files, recorded in install-state
    `parts`, and written under the agent only where the agent may write.
  - **`--with all` doesn't include `dsl`.** `dsl` adds a structural requirement to every later spec, so it stays an
    explicit opt-in. `--with all,dsl` installs both. The usage text and `parts_line` say that `all` excludes
    `dsl`.
- **R-2: no silent install.** The two fallbacks in `installed_parts` that mean "every part" both mean the five
  parts that existed before `dsl` (`LEGACY_PARTS`):
  - install-state written before 0.2.0-beta.1, which has no `parts` key;
  - a repo with an edited config and no install-state.

  So `upgrade`, `repair` and a plain `setup` rerun never add `dsl` on their own. Only `--with` does (CLAUDE.md
  rule 5, intent: Constraints).
- **R-3: the model format.** Each `domain/*.dsl.json` holds one JSON object with `"dsl": 1`, a `"kind"`, and a
  `"name"` (an identifier, unique across `domain/`):
  - `state_machine`: `states` (unique names), `initial` (one of them), optional `final` (a subset), `transitions`
    (`from`, `to`, `event`, optional `guard` string; `from` and `to` are known states, and each (`from`, `event`)
    pair is unique).
  - `rules`: `rules`, each with a unique `id`, `when` and `then` (non-empty strings), and an optional
    `description`.
  - `workflow`: `steps`, each with a unique `id` and an optional `next` (ids of known steps), and `start` (a known
    step).

  Unknown keys are errors, so typos surface. The expression strings (`guard`, `when`, `then`) are opaque: they
  name domain concepts and are never evaluated.
- **R-4: the validator.** `scripts/validate-dsl.py [dir]` (default `domain/`) uses only the Python 3.9 stdlib:
  - It prints one line per problem, as `<file>: <json path>: <problem>`, for example
    `domain/order.dsl.json: $.transitions[2].to: unknown state "Shipped"`. Invalid JSON prints
    `<file>:<line>:<col>: invalid JSON: …`.
  - It exits 1 on any problem and 0 otherwise, printing `validate-dsl: N model(s) ok`.
  - With no directory it prints `validate-dsl: no domain/ - skipped` and exits 0.
  - It reads only regular `*.dsl.json` files directly in the directory, each at most 1 MiB, and never follows a link.
    Nesting deeper than 64 levels is a problem, never a crash.
  - Other files (`README.md`) are ignored.
- **R-5: the Makefile.**
  - The core template `templates/scaffold/Makefile` gains a `validate-dsl` target, listed in `.PHONY`, and
    `check: lint typecheck test validate-dsl`.
  - The recipe runs `python3 scripts/validate-dsl.py` when `domain/` exists. Otherwise it prints
    `[validate-dsl] no domain/ - skipped`, and if `domain/` exists but the script doesn't, it fails with a message
    naming `sdlc setup --with dsl`.
  - Detection wiring (`cli.wire`, recorded recipes, `upgrade` of an untouched or wired Makefile) keeps working, and
    `defaults/scaffold-history.json` gets the new hashes through `scripts/scaffold-history.py`.
  - A Makefile that doesn't define `validate-dsl` isn't edited. While the part is installed, setup prints the target
    and the `check` line as a human step.
- **R-6: the active part and the spec section.**
  - The part is **active** for a repo when its install-state `parts` list names `dsl`, or `<root>/domain` is a
    directory. Only an explicit `dsl` entry counts; R-2's legacy fallbacks never do.
  - While the part is active, the spec schema check `domain_dsl` requires `## Domain DSL`. Its body, with HTML
    comments removed, is either:
    - a line starting `No domain changes` (an explicit opt-out for a technical or UI intent, a reason may follow);
      or
    - at least one reference to a `domain/<name>.dsl.json` path.

    Anything else, an empty body included, is an error that states the reason and both accepted forms
    (CLAUDE.md rule 2).
  - While the part is inactive, the section is optional and unchecked.
  - Activation can only add this requirement. An approved spec keeps its gate: the check reads the text and never
    the hash.
- **R-7: the draft.** While the part is active, `sdlc draft <id> spec` writes the template with a `## Domain DSL`
  section placed before `## Data model`. The section holds a comment naming the two accepted forms and a
  placeholder. The spec template itself is unchanged.
- **R-8: the advice.**
  - `skills/spec/SKILL.md` and `agents/architect.md`: while the part is active, formalize new business rules,
    state machines and workflows in `domain/*.dsl.json` terms in `## Domain DSL` first, then derive the Data model
    and API contracts from it.
  - `skills/plan/SKILL.md` and `agents/planner.md`: while the part is active, S1 updates `domain/` and its
    validation (`make validate-dsl` red, then green) before any application code.
  - `skills/setup/SKILL.md`, `skills/init/SKILL.md`, the `cli.py` usage text, `domain/README.md`, the CHANGELOG
    and the docs that list the parts name `dsl`. `domain/README.md` documents R-3 with one example per kind.
- **Non-functional:** stdlib only (engine and script); domain-neutral (no business names in the schema, the
  validator or the templates); `make check` passes.

## Acceptance criteria
- **AC-1**: Given a repo set up without `dsl`, when the human runs `sdlc setup --with dsl --yes`, then install-state
  `parts` names `dsl`, and `domain/README.md` and `scripts/validate-dsl.py` exist, with no existing file changed.
  Given `--with all`, then `dsl` isn't installed. Given install-state without a `parts` key, or a repo set up before `dsl` existed, when `upgrade` or `repair` runs,
  then no `dsl` file is planned.
- **AC-2**: Given `domain/` with valid models of all three kinds, when `scripts/validate-dsl.py` runs, then it
  exits 0. Given one invalid file per problem class (invalid JSON, an unknown kind or key, a reference to an unknown
  state or step, a duplicate id or name, a missing `initial`), then it exits 1 and prints each problem with its file
  and JSON path or line. Given no `domain/`, it exits 0 with the skip line.
- **AC-3**: Given the scaffold Makefile, when `make check` runs with no `domain/`, then it passes. With a valid
  `domain/` it runs the validator and passes, and with an invalid one it fails. A Makefile wired by stack detection
  keeps its recipes through `upgrade`.
- **AC-4**: Given the part active (install-state names `dsl`, or `domain/` exists), when `sdlc validate` runs, then:
  - a spec without `## Domain DSL`, or with an empty or unrelated body, fails;
  - `No domain changes` or a body naming `domain/order.dsl.json` passes;
  - `sdlc draft <id> spec` writes the section before `## Data model`.

  Given the part inactive, a spec without the section passes.
- **AC-5**: Given the shipped text, then the spec skill and the architect (Domain DSL first), the plan skill and
  the planner (S1 is `domain/` and its validation), and the setup and init skills (`dsl` among the parts) say so,
  and `make check` passes.

## Data model
No database. One new file format, `domain/*.dsl.json` (R-3), with `"dsl": 1` as its version so a later format can be
told apart. It is classified **internal**: it holds domain names and rules, never data records or secrets.
Install-state `parts` may now contain `dsl`; the file's shape is unchanged.

## API contracts
- **CLI:**
  - `sdlc setup|init --with dsl` (not through `all`; `--with all,dsl` names both);
  - `--with`'s error message and the usage text list `dsl`;
  - `sdlc draft <id> spec` adds the section while the part is active.
- **Script:** `scripts/validate-dsl.py [dir]` → exit 0/1, with R-4's output lines.
- **Make:** `make validate-dsl`, and `check` depends on it.
- **Schema:** `schemas/spec.json` `checks` gains `domain_dsl`. `sections` is unchanged, because the requirement is
  conditional and lives in the check.

## Security & data-leak flags
- ⚠️ **The validator runs in every Stop hook**, through `make check`, in repos that install the part:
  - It is a fixed script from the plugin, run on repo files the agent can write.
  - Mitigation (R-4): it only parses JSON with stdlib `json` and evaluates nothing; it reads regular files only, with
    no links, at most 1 MiB each, and a depth limit. A parse problem is reported, never raised.

  (zoujagger)
- ⚠️ **Removing `domain/` turns the requirement off in CI.** CI ignores install-state, so an agent that deletes
  `domain/` makes a spec without `## Domain DSL` pass `validate --ci`.
  - Mitigation: the deletion is a visible diff in the PR, under CODEOWNERS review. Locally, install-state (which
    the agent can't edit, `GUARDED_RE`) keeps the requirement on.
  - **Decided (zoujagger):** `domain/` stays out of `protected-paths`, so the agent can create and update
    `domain/*.dsl.json` in Step 1 of implementation.
- ⚠️ **Install-state now feeds a schema check.** It can only add a requirement (R-6), never open a gate or lift a
  check, so the threat model's rule "install-state never decides a gate" holds. `docs/architecture.md`'s row is
  updated to say so. (zoujagger)
- No personal data, secrets or network access. The model files are classified internal (Data model).

## Architecture
- **`lifecycle.py`:**
  - `PARTS` gains `dsl`, and a new `LEGACY_PARTS` holds the five older parts;
  - `parse_parts("all")` returns `LEGACY_PARTS` (every part but `dsl`), and a list may name `all` beside `dsl`;
  - `installed_parts` uses `LEGACY_PARTS` in its two "every part" fallbacks (`:209`, `:213`) and at `:268`;
  - `dsl_active(root)` implements R-6. It reads install-state through `load()` and accepts only a `parts` list that
    names `dsl`.
- **`schema.py`:** `_domain_dsl(d, a, secs, text)` (0011's check signature). The root is `d.parent.parent`, as for
  every intent folder.
- **`cli.cmd_draft`:** when `dsl_active`, it inserts the section from a small template fragment.
- **`setup.py`:** the human step for a Makefile without `validate-dsl`, beside the existing Makefile steps.
- **Scaffold:**
  - `templates/scaffold/domain/README.md` and `templates/scaffold/scripts/validate-dsl.py`, as `maintain` ships
    `scripts/check-bands.py`, so a target repo's CI runs it without the plugin;
  - the Makefile template change (R-5).
- **Not taken:**
  - a JSON Schema file with a generic validator (the stdlib has none, and hand-coded checks give better messages);
  - YAML (it needs pyyaml);
  - a plan validator check that S1 touches `domain/` (the human chose advisory enforcement);
  - a pre-edit guard (intent: Out of scope);
  - `sdlc validate-dsl` as an engine command (the target repo's CI may not have the plugin).

## Rollout & rollback
- One PR, released with the next beta. Adopters get the Makefile template change through `upgrade`, and it stays
  dormant until `domain/` exists. Nobody gets `dsl` without `--with`.
- **Rollback:** revert the PR. Repos that installed the part keep `domain/` and the script as their own files, and
  their specs keep `## Domain DSL` sections, which the old engine ignores.

## Open questions
- [x] `--with all` includes `dsl`? **No**: it adds a structural requirement to every later spec, so it stays an
  explicit `--with dsl` (R-1). (zoujagger, 2026-11-20)
- [x] `domain/` in `protected-paths`? **No**: the agent must be able to create and update `domain/*.dsl.json` in
  Step 1 of implementation (second flag). (zoujagger, 2026-11-20)
