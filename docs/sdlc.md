# The AI-Native SDLC

This template implements the workflow from Anthropic's *AI-Native SDLC Playbook*.
Work starts from an **intent**. Each stage **commits an artifact the next stage can read**, and every gate is a human decision.

> "The loop keeps running. Human judgement stays above it."

```
            ┌──────────────────────────────────────────────────────────────────────┐
            ▼                                                                      │
 Trigger: INTENT ─▶ 1 PLAN ─▶ 2 DESIGN ─▶ 3 BUILD ─▶ 4 TEST ─▶ 5 DEPLOY ─▶ 6 MAINTAIN
  /intent            (validate)  /spec       /plan      /verify    /review    /triage
  intent.md                      spec.md     /implement /fix       /pr        bands.yaml
                                             plan.md    evals      /deploy    → new intent.md
     ✋ PO validates   ✋ spec accepted  ✋ plan accepted   ✋ PR approved  ✋ prod approval  ✋ owner triages
```
Artifacts for each change: `docs/intents/NNNN-slug/{intent.md, spec.md, plan.md}`. Check status with `/sdlc <id>`.

---

## Trigger: Intent
| | |
|---|---|
| **What happens** | A person, ticket, or alert expresses a need. Claude asks framing questions and drafts `intent.md`, a proto-spec in Markdown |
| **Artifact** | `intent.md`: problem, desired outcome, users and systems affected, constraints, open questions |
| **Human** | The initiator states the need and corrects the draft. The product owner reviews and validates |
| **AI** | `/intent` → `product-analyst` |
| **Gate** | Validated in the shared intents repo (`status: Validated`, or the intent PR merged) |
| **Entry points** | `/intent` in Claude Code · the GitHub "Intent" issue form (→ `claude-issue-triage.yml`) · alerts (→ `claude-maintain.yml`) · postmortem actions |

## 1. Plan
The intent is formalised and shared. Recurring processes are encoded as **skills** in `.claude/skills/`, so every intent is handled the same way.
Prerequisites: the accepted `intent.md` template and a shared repo the product owner watches (`docs/intents/` + CODEOWNERS).

## 2. Design
| | |
|---|---|
| **What happens** | Requirements and design are produced **in one session**. Claude reads `intent.md`, applies the policy skills (`policy-security`, `policy-compliance`, `policy-ux`, `policy-brand`), and writes `spec.md`. It flags points of attention and surfaces policy conflicts |
| **Artifact** | `spec.md`, committed next to `intent.md` |
| **Human** | The product owner reviews and resolves the flags with the compliance owner. The tech lead joins for high-risk changes |
| **AI** | `/spec` → `product-analyst` (requirements) + `architect` (design, ADRs) |
| **Gate** | Human acceptance (`status: Accepted`), which triggers Plan mode in Build |
| **Front end** | Generate a mock-up from `intent.md` (e.g. Claude Design) before acceptance |

## 3. Build
| | |
|---|---|
| **What happens** | The engineer starts in **Plan mode** with `intent.md` + `spec.md`, has Claude build a plan, stress-tests it, and accepts it. It's committed as `plan.md`. Then implementation follows. **If code diverges from the plan, `plan.md` is updated in the same commit** |
| **Auto mode** | The default for routine, well-tested tasks. Review then focuses on the artifacts at the end of the session |
| **Parallelism** | 2-3 sessions, each in its own git worktree (`/parallel`, `scripts/worktree.sh`). Repetitive tasks become subagents in `.claude/agents/` |
| **Institutional memory** | `CLAUDE.md` (about one page: conventions, commands, architecture, Lessons; a repeated mistake → `/learn`) · skills (`.claude/skills/<name>/SKILL.md`) |
| **Hooks** | Block protected paths, format and lint after every edit, block secrets. Keep them fast |
| **Artifacts** | `plan.md`, code, commits |
| **AI** | `/plan` → `planner` · `/implement` → `implementer` |

## 4. Test
- **Feedback loop.** Claude checks its own work (tests, build, screenshots) and iterates before a human sees it. The definition of done lives in `CLAUDE.md`, and the Stop hook enforces `make check`.
- **Bug fixes.** Write a failing test first, a human approves it, then fix. The `guard-tests.sh` hook blocks test edits while `.claude/state/test-lock` exists (`/fix`).
- **Verification subagent.** A final check in a **fresh context window** that doesn't inherit the session's assumptions (`/verify` → `verifier`).
- **Continuous evals.** A suite of 20-50 real tasks in `evals/` runs in CI whenever `CLAUDE.md`, skills, hooks or `REVIEW.md` change (`claude-evals.yml`). **Every production incident becomes a new regression eval.**

## 5. Deploy
- **AI PR review.** Claude reviews every PR against [`REVIEW.md`](../REVIEW.md) in three passes (bugs, security, conformance to `spec.md` and `plan.md`) and responds to `@claude` comments. Recurring findings feed `CLAUDE.md` Lessons.
- **Human approval** comes from branch protection and CODEOWNERS. **The agent that wrote the code can't approve its own PR.** The AI review only comments.
- **Hooks as checkpoints.** `guard-deploy.sh` blocks production deploys. Every block states the reason and the procedure.
- **Managed settings.** The platform enforces permissions, sandbox, managed hooks, approved marketplaces and minimum version (`governance/managed-settings.example.json`).
- **CI/CD.** Start with read-only analysis (`claude -p`), then add writes behind PRs. Deploys are exposed per environment (`deploy.yml`, optionally MCP for staging). **Rollback is a single command** (`make rollback ENV=…`), tested in staging.
- **Principle:** *"The agent does everything up to the production gate and nothing past it."*

## 6. Maintain
- **Closing the loop.** A trigger (threshold breach, ticket, channel message, schedule) invokes Claude with nobody in the invocation path (`claude-maintain.yml`).
- **Control bands** (`ops/bands.yaml`). Detection is deterministic, from a rolling baseline (`scripts/check-bands.py`):
  | Band | Action |
  |---|---|
  | 1σ | Log the event |
  | 2σ | Read-only diagnosis (`diagnostician`) |
  | 3σ | Propose a PR, or trigger a pre-approved runbook (e.g. rollback) |
- **Back into the loop.** The diagnosis is written as `intent.md` and starts again at stage 1. The service owner triages: fix, schedule, or close (`/triage`).
- **Recurring scans.** A weekly security and health scan (`claude-scheduled-scan.yml`). Narrow fixes go through PR review. Broad ones become a new `intent.md`.
- **In channels.** Claude in Slack/Teams and tickets (Claude Tag) can run triage and produce versioned postmortems (`/postmortem` → `docs/postmortems/`).

---

## Component map
| Stage | Skills | Agents | Hooks / automation |
|---|---|---|---|
| Intent / Plan | `/intent`, `/sdlc` | product-analyst | `claude-issue-triage.yml` |
| Design | `/spec`, `/adr`, policy-* | product-analyst, architect | — |
| Build | `/plan`, `/implement`, `/parallel` | planner, implementer, test-engineer | guard-files, post-edit-format, session-start |
| Test | `/verify`, `/fix`, `/learn` | verifier | guard-tests, stop-verify, `claude-evals.yml` |
| Deploy | `/review`, `/security-check`, `/pr`, `/release`, `/deploy` | code-reviewer, security-reviewer, release-manager, docs-writer | guard-bash, guard-deploy, `ci.yml`, `claude-pr-review.yml`, `claude.yml`, `deploy.yml` |
| Maintain | `/triage`, `/incident`, `/postmortem`, `/retro` | diagnostician, incident-responder | `claude-maintain.yml`, `claude-scheduled-scan.yml` |

## Skill vs hook
A skill is advisory and makes violations rare. A hook is deterministic and makes them close to impossible.
See [governance.md](governance.md) for sources of truth, the audit trail, metrics and anti-patterns.
