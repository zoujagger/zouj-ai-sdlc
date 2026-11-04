# Commands quick reference

Type `/` in Claude Code to see them. Each command belongs to a stage of the AI-Native SDLC Playbook, and only a human
opens a gate (✋). The engine itself is `sdlc` (see `sdlc --help`).

## Get started
| Command | What it does |
|---|---|
| `/zouj-ai-sdlc:setup [solo\|team\|strict]` | Guided setup: checks prerequisites, previews every change and the gates, applies after you confirm, lists your human steps. Rerunnable |
| `/zouj-ai-sdlc:init [--stack python\|node\|go]` | The bare scaffold, without setup's guidance |
| `/zouj-ai-sdlc:onboard` | An interactive tour of the workflow for your role |
| `/zouj-ai-sdlc:help-me "<goal>"` | Maps what you want to do to the right command |
| `/zouj-ai-sdlc:status [id]` | Where an intent is, and the exact next step |

## The five states
| Command | State | Ends when |
|---|---|---|
| `/zouj-ai-sdlc:intent "<need>"` | 1 BRAINSTORMING → `intent.md` | ✋ `Intent Approved NNNN` |
| `/zouj-ai-sdlc:spec [id]` | 2 SPECIFICATION → `spec.md` | ✋ `Spec Approved NNNN` |
| `/zouj-ai-sdlc:plan [id]` | 3 PLAN (code read-only) → `plan.md` | ✋ `Plan Approved NNNN` |
| `/zouj-ai-sdlc:implement [id] [step]` | 4 EXECUTION, autonomous TDD | every step ticked, `make check` green |
| `/zouj-ai-sdlc:parallel <id> <steps>` | 4, independent steps in git worktrees | as above |
| `/zouj-ai-sdlc:review [id] [base]` | 5 PRE-REVIEW → `review.md` + `pr.md` | ✋ the human merges |
| `/zouj-ai-sdlc:pr [id] [base]` | 5, opens the PR from `pr.md` (never merges) | ✋ the human merges |

## Test and fix
| Command | What it does |
|---|---|
| `/zouj-ai-sdlc:fix "<bug>"` | Bug lane: a compact intent, spec and plan (three short approvals), the failing test first, test files locked |
| `/zouj-ai-sdlc:security-check [base\|path]` | A security pass over a diff or a path |

## Deploy and release
| Command | What it does |
|---|---|
| `/zouj-ai-sdlc:deploy [staging]` | Deploys to staging and prepares the production handoff. ✋ Production is a human |
| `/zouj-ai-sdlc:release [major\|minor\|patch]` | Version bump, CHANGELOG and release notes. Never tags or publishes |

## Maintain
| Command | What it does |
|---|---|
| `/zouj-ai-sdlc:triage <alert:metric \| #issue \| text>` | Read-only diagnosis and a draft intent |
| `/zouj-ai-sdlc:incident "<symptom>"` | Live incident response: triage, runbook, mitigation, timeline |
| `/zouj-ai-sdlc:postmortem "<title>"` | Blameless postmortem; actions become intents and regression evals |
| `/zouj-ai-sdlc:retro [since]` | Retrospective with the playbook's metrics |
| `/zouj-ai-sdlc:learn "<what went wrong>"` | Adds a lesson to CLAUDE.md so a mistake isn't repeated |
| `/zouj-ai-sdlc:adr "<decision>"` | An Architecture Decision Record in `docs/adr/` |

## Engine commands (terminal)
| Command | What it does |
|---|---|
| `sdlc setup [--profile P] [--stack S] [--dry-run] [--yes]` | The guided setup, as above |
| `sdlc status [--json]` · `sdlc next` | State and next step |
| `sdlc doctor` | Checks prerequisites, the profile, signing and artifacts |
| `sdlc feedback` | Issue links and a doctor summary to paste (sends nothing) |
| `sdlc approve <id> intent\|spec\|plan` | ✋ Human only, in your own terminal (refused inside Claude Code) |
| `sdlc validate [--all] [--ci --base REF]` | Schema and approval audit (what CI runs) |
