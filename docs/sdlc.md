# Mapping to Anthropic's AI-Native SDLC Playbook

> "The loop keeps running. Human judgement stays above it."

The playbook's six stages, **Plan → Design → Build → Test → Deploy → Maintain → (a new intent, back to Plan)**, map
onto the plugin's five enforced states plus optional Deploy and Maintain skills that feed new intents back in.

| Playbook stage | zouj-ai-sdlc | Artifact | Human gate | Enforced by |
|---|---|---|---|---|
| 1 Plan | 1 BRAINSTORMING · `/zouj-ai-sdlc:intent` (also issues → `claude-issue-triage.yml`, alerts → `claude-maintain.yml`). The intent home is `.aiops/` in the repo, under CODEOWNERS | `intent.md` | `Intent Approved NNNN` (product owner) | prompt hook, pre-edit guard, `aiops-gates.yml` |
| 2 Design | 2 SPECIFICATION · `/zouj-ai-sdlc:spec`, policy skills, `/zouj-ai-sdlc:adr` | `spec.md` (+ ADRs) | `Spec Approved NNNN` (+ tech lead if `risk: high`) | prompt hook, creation order |
| 3 Build: Plan mode | 3 PLAN · `/zouj-ai-sdlc:plan` (read-only lock) | `plan.md` | `Plan Approved NNNN` (engineer) | read-only lock |
| 3 Build: implementation | 4 EXECUTION · `/zouj-ai-sdlc:implement`, `/zouj-ai-sdlc:parallel` | code, commits, Deviation log | none: autonomous | Stop hook (`make check`) |
| 4 Test | TDD inside state 4; `/zouj-ai-sdlc:fix` (test lock); `make evals` | tests, `Red:` evidence | the human confirms the failing test in `/fix` | guard-tests, stale review |
| 5 Deploy: AI review | 5 PRE-REVIEW · `/zouj-ai-sdlc:review` (verifier, code-reviewer, security-reviewer), `/zouj-ai-sdlc:pr` | `review.md`, `pr.md` | **the merge** (CODEOWNER) | merge and push-to-main guards, CI audit |
| 5 Deploy: release | `/zouj-ai-sdlc:deploy` (staging), `/zouj-ai-sdlc:release` | handoff note, CHANGELOG | the production approver | guard-deploy, GitHub Environment |
| 6 Maintain | `/zouj-ai-sdlc:triage`, `:incident`, `:postmortem`, `:retro`, `ops/bands.yaml` | diagnosis → a **new intent.md** | the service owner triages | read-only diagnosis |

## Principles kept from the playbook
- Every stage commits an artifact the next stage reads, so git holds the full chain
  ([audit trail](governance.md#audit-trail)).
- "The agent does everything up to the production gate and nothing past it." Here that gate also covers merging.
- Skills make violations rare. Hooks make the absolute rules close to impossible.
- Every production incident becomes a regression eval (`evals/`).
- Parallelism: at most 2-3 sessions in separate worktrees (`sdlc-worktree`).

## Keeping the work reviewable
- **Scope (intent 0011).** The intent interview runs a scope check: work that covers several workflows or more than 5
  outcomes is offered as a split into smaller intents before `intent.md` exists. Intents aim for 3 to 5 outcomes and
  specs for 3 to 5 user-observable ACs (never more than 7). `sdlc validate` warns above 5 ACs and refuses a draft
  spec above 8 (`scope_size`); approved specs only warn.
- **Spec quality (0014).** The architect writes `None (no changes)` in an untouched `## Data model`,
  `## API contracts` or `## Rollout & rollback` (never in Security or Architecture), opens `## Architecture` with one
  Mermaid diagram for a multi-step flow, a state transition or a table, tags every table, column and endpoint with
  the `[AC-N]` it serves, and closes the Data model with **Queries**: each pattern, its composite index (the tenant
  key leading in multi-tenant data) and how N+1 is prevented. `sdlc validate` refuses a ```mermaid block over 12
  lines in a draft spec (`mermaid_size`).
- **The domain model (the opt-in `dsl` part, 0012-0013).** `sdlc setup --with dsl` adds `domain/README.md` and
  `scripts/validate-dsl.py`; `--with all` leaves it out. The part is active when install-state names `dsl` or a
  `domain/*.dsl.json` file exists; a repo's own `domain/` folder doesn't count. While it is active:
  - `make check` runs `validate-dsl`, which validates the state machines, rule sets and workflows in
    `domain/*.dsl.json` with the standard library alone;
  - every draft spec needs `## Domain DSL` before the Data model and API contracts, naming the model files it changes
    or saying `No domain changes` (`domain_dsl`);
  - plan Step 1 and implementation update the model and get `make validate-dsl` green before application code;
  - the review reports each transition or rule hardcoded in controllers, handlers or UI as a MEDIUM finding in
    `## Domain model`, 3 points off Spec conformance.

## Who does what
| Agent | State | Job |
|---|---|---|
| product-analyst | 1-2 | interview and scope check → intent.md (3-5 outcomes), requirements and 3-5 ACs |
| architect | 2 | DB schema with query patterns and indexes, API contracts, data-leak flags, one diagram, ADRs; `[AC-N]` on every table and endpoint |
| planner | 3 | read-only file-by-file plan |
| implementer | 4 | one step per fresh subagent, strict TDD |
| verifier · code-reviewer · security-reviewer | 5 | independent, fresh-context scoring |
| diagnostician · incident-responder | Maintain | diagnosis → new intent, postmortems |
| test-engineer · docs-writer · release-manager | any | coverage gaps, docs, releases |
