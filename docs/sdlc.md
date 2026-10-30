# Mapping to Anthropic's AI-Native SDLC Playbook

> "The loop keeps running. Human judgement stays above it."

The playbook's loop, **Intent → Plan → Design → Build → Test → Deploy → Maintain → (new intent)**, maps onto the
plugin's five enforced states plus optional Deploy and Maintain skills that feed new intents back in.

| Playbook stage | zouj-ai-sdlc | Artifact | Human gate | Enforced by |
|---|---|---|---|---|
| Trigger: Intent | 1 BRAINSTORMING · `/zouj-ai-sdlc:intent` (also issues → `claude-issue-triage.yml`, alerts → `claude-maintain.yml`) | `intent.md` | `Intent Approved NNNN` (product owner) | prompt hook, pre-edit guard |
| 1 Plan (formalise and share) | `.aiops/` in the repo, CODEOWNERS on `.aiops/`, skills encode the process | — | — | `aiops-gates.yml` |
| 2 Design | 2 SPECIFICATION · `/zouj-ai-sdlc:spec`, policy skills, `/zouj-ai-sdlc:adr` | `spec.md` (+ ADRs) | `Spec Approved NNNN` (+ tech lead if `risk: high`) | prompt hook, creation order |
| 3 Build: Plan mode | 3 PLAN · `/zouj-ai-sdlc:plan` (read-only lock) | `plan.md` | `Plan Approved NNNN` (engineer) | read-only lock |
| 3 Build: implementation | 4 EXECUTION · `/zouj-ai-sdlc:implement`, `/zouj-ai-sdlc:parallel` | code, commits, Deviation log | none: autonomous | Stop hook (`make check`) |
| 4 Test | TDD inside state 4; `/zouj-ai-sdlc:fix` (test lock); `make evals` | tests, `Red:` evidence | the human confirms the failing test in `/fix` | guard-tests, stale review |
| 5 Deploy: AI review | 5 PRE-REVIEW · `/zouj-ai-sdlc:review` (verifier, code-reviewer, security-reviewer), `/zouj-ai-sdlc:pr` | `review.md`, `pr.md` | **the merge** (CODEOWNER) | merge and push-to-main guards, CI audit |
| 5 Deploy: release | `/zouj-ai-sdlc:deploy` (staging), `/zouj-ai-sdlc:release` | handoff note, CHANGELOG | the production approver | guard-deploy, GitHub Environment |
| 6 Maintain | `/zouj-ai-sdlc:triage`, `:incident`, `:postmortem`, `:retro`, `ops/bands.yaml` | diagnosis → a **new intent.md** | the service owner triages | read-only diagnosis |

## Principles kept from the playbook
- Every stage commits an artifact the next stage reads, so git holds the full chain:
  **intent → spec → plan → diff → tests → review → approval commits → merge**.
- "The agent does everything up to the production gate and nothing past it." Here that gate also covers merging.
- Skills make violations rare. Hooks make the absolute rules close to impossible.
- Every production incident becomes a regression eval (`evals/`).
- Parallelism: at most 2-3 sessions in separate worktrees (`sdlc-worktree`).

## Who does what
| Agent | State | Job |
|---|---|---|
| product-analyst | 1-2 | interview → intent.md, requirements and ACs |
| architect | 2 | DB schema, API contracts, data-leak flags, ADRs |
| planner | 3 | read-only file-by-file plan |
| implementer | 4 | one step per fresh subagent, strict TDD |
| verifier · code-reviewer · security-reviewer | 5 | independent, fresh-context scoring |
| diagnostician · incident-responder | Maintain | diagnosis → new intent, postmortems |
| test-engineer · docs-writer · release-manager | any | coverage gaps, docs, releases |
