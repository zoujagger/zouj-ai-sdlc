---
id: 0012
title: Opt-in dsl part: a validated domain/ model for specs and plans
status: Approved
owner: zoujagger
initiator: zoujagger
source: request for domain-first declarative modeling as an opt-in part (2026-11-20)
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T15:17:17Z
approved-via: cli
approved-sha256: 4f03a7eb6217faf758457c35244594464b6cf936f950ebc7012469c7b165d10e
---

# Intent: Opt-in dsl part: a validated domain/ model for specs and plans

<!-- State 1 BRAINSTORMING. Written from zoujagger's request on 2026-11-20 and the scope-check round in the same
     session. The request had 4 outcomes across setup, three skills, an edit guard and a review check; the human
     chose to split it into two intents: this one (the part, the validator, the spec and plan rules) and a next one
     (implement and review). Other answers: a domain-neutral schema shipped by the plugin, a `validate-dsl` stub in
     the core Makefile template, and advisory enforcement (no new guard). The three open questions were answered by
     zoujagger before approval: JSON files, detection by install-state or `domain/`, and a required spec section.
     Unknowns go in Open questions, never invented. approved-* fields are stamped by the human approval; agents never write them. -->

## Problem
The playbook goes from intent to spec to code with business rules written as prose (spec Requirements and ACs)
and then as code. Nothing keeps a declarative model of the domain:

- State machines, business rules and workflows end up scattered through controllers, services and UI code, where
  the human can't review them as one model and tests can't check them against one source.
- A spec defines DB schemas and API contracts before the domain model is pinned down, so the model is implied by
  the storage and transport layers instead of driving them.
- A team that wants domain-first modeling has no supported way to ask for it, and the plugin must not assume any
  particular business domain or modeling tool to give them one.

## Desired outcome
- **`sdlc setup --with dsl` installs an opt-in `dsl` part**, the same way as the other parts: it records `dsl` in
  `.aiops/install-state.json`, writes only missing files, and scaffolds a `domain/` directory with a README that
  explains the model files and how they are validated.
- **The domain model is validated without tying the plugin to a domain.** The model lives in
  `domain/*.dsl.json`. The plugin ships a domain-neutral schema for state machines, business rules and workflows,
  and a validator built on Python's `json` module alone, so neither the target repo nor CI needs a third-party
  package. It reports each problem with its file and location. A repo without `domain/` passes.
- **`make check` runs it.** The core Makefile template gets a `validate-dsl` target, called by `check`, that passes
  when `domain/` is absent. A Makefile the human has edited isn't changed: setup prints the lines to add.
- **With the part active, the spec models the domain first.** The part is active when install-state records
  `dsl` **or** the repo has a `domain/` directory, so it holds locally and in CI. Then `## Domain DSL` is a
  required section of `spec.md` (`schemas/spec.json`), and State 2 has the architect formalize new business rules
  and state machines there, before the Data model and API contracts. A purely technical or UI intent says so
  explicitly with the body `No domain changes`.
- **With the part active, the plan starts from the model.** State 3 puts the `domain/` updates and their
  validation tests in Step 1, before any application code.

## Users & systems affected
- Users: teams adopting the plugin who want domain-first modeling (opt-in); the human approver, who reviews the
  model in the spec; the agent in states 2-3 (architect, planner).
- Systems: `defaults/scaffold-parts` and `templates/scaffold/` (the new part, `domain/README.md`, the Makefile
  template), `lib/sdlc_engine/` (parts, setup, the validator), `defaults/scaffold-history.json` (the template
  changes), `skills/spec`, `skills/plan`, `skills/setup`, `skills/init`, `agents/architect.md`,
  `agents/planner.md`, the spec template, `tests/`, and the docs that list the parts.

## Constraints
- Engine code is stdlib only (Python ≥ 3.9): the validator uses the `json` module, and the model files are JSON.
- `sdlc init`/`setup` never overwrite an existing file (CLAUDE.md rule 5), and the lifecycle commands never add a
  part on their own. Run by the agent, setup writes only what the agent may write.
- Install-state never decides a gate (threat model). Here it may only *add* a requirement (the `## Domain DSL`
  section), never lift one, and CI, which ignores install-state, still sees the requirement through `domain/`. The
  part adds no guard and no gate.
- Domain-neutral: no business-domain names in the schema, the validator or the templates.
- Engine changes are test-first (CLAUDE.md rule 2).

## Out of scope
- **Next intent (0013):** State 4 (`implement`) ordering and checks around `domain/` before application code, and
  State 5 (`review`) checking that business rules defined in `domain/` aren't hardcoded in controllers or UI
  components.
- A hard pre-edit guard that blocks application-code edits until `domain/` is valid (the human chose advisory
  enforcement).
- Code generation from the model, and any specific notation (SCXML, BPMN, DMN).

## Open questions
- [x] The model file format: **JSON, `domain/*.dsl.json`**, validated with the stdlib `json` module only.
  (zoujagger, 2026-11-20)
- [x] Detecting the part: install-state records `dsl` **or** `domain/` exists, so it works locally and in CI.
  (zoujagger, 2026-11-20)
- [x] Enforcing `## Domain DSL`: a **required section in `schemas/spec.json`** while the part is active, with
  `No domain changes` accepted as an explicit body. (zoujagger, 2026-11-20)
