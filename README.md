# AI-Native SDLC Template

A **stack-agnostic** boilerplate that implements Anthropic's *AI-Native SDLC Playbook* with
[Claude Code](https://docs.claude.com/en/docs/claude-code). Work **starts from an intent**, every stage commits an artifact the next stage reads,
hooks enforce the absolute rules, and humans decide at every gate.

```
Trigger: INTENT → 1 PLAN → 2 DESIGN → 3 BUILD → 4 TEST → 5 DEPLOY → 6 MAINTAIN ─┐
  /intent          (validate)  /spec      /plan      /verify   /review   /triage   │
  intent.md                    spec.md    /implement /fix      /pr       bands.yaml │
     ▲                                    plan.md    evals     /deploy             │
     └──────────────────────── diagnosis becomes a new intent.md ──────────────────┘
```

## What's inside
| Component | Location | Purpose |
|---|---|---|
| Project memory | `CLAUDE.md` | The loop, rules, definition of done, Lessons (about one page) |
| Workflow | `docs/sdlc.md` | Stage-by-stage guide (roles, artifacts, gates) |
| Review rules | `REVIEW.md` | 3-pass PR review: bugs, security, conformance to spec and plan |
| Governance | `docs/governance.md`, `governance/` | Sources of truth, audit trail, metrics, anti-patterns, managed settings |
| Change artifacts | `docs/intents/NNNN-slug/` | `intent.md` → `spec.md` → `plan.md` |
| **Skills** | `.claude/skills/` | Workflow: `/intent` `/spec` `/plan` `/implement` `/parallel` `/verify` `/fix` `/review` `/security-check` `/pr` `/release` `/deploy` `/triage` `/incident` `/postmortem` `/retro` `/learn` `/adr` `/sdlc` `/onboard` · Policy (auto-applied): security, compliance, UX, brand |
| **Subagents** | `.claude/agents/` | product-analyst, architect, planner, implementer, test-engineer, **verifier**, code-reviewer, security-reviewer, docs-writer, release-manager, **diagnostician**, incident-responder |
| **Hooks** | `.claude/hooks/` | guard-bash, guard-files, **guard-tests** (test lock), **guard-deploy** (prod gate), post-edit format+lint, stop-verify (definition of done), session-start |
| **Evals** | `evals/`, `scripts/run-evals.py` | Continuous evaluation of the agent setup; incidents become regression evals |
| **Control bands** | `ops/bands.yaml`, `scripts/check-bands.py` | Deterministic 1σ/2σ/3σ detection → log / diagnose / PR or runbook |
| **GitHub automation** | `.github/workflows/` | `ci`, `claude` (@claude), `claude-pr-review`, `claude-issue-triage`, `claude-evals`, `deploy` (staging auto, prod gated, 1-command rollback), `claude-maintain`, `claude-scheduled-scan`, `claude-release-notes` |
| Build contract | `Makefile` | `format lint typecheck test build check deploy rollback evals` |

## Quickstart
```bash
scripts/bootstrap.sh my-project my-github-org   # personalise, git init
$EDITOR Makefile                                # wire your stack into the contract targets
gh secret set ANTHROPIC_API_KEY                 # or /install-github-app in Claude Code
make validate-template && make check
claude
> /intent "Users can export their account data as CSV"
```

## One change, end to end
```text
/intent "CSV export"   → docs/intents/0001-csv-export/intent.md      ✋ product owner validates
/spec 0001             → spec.md (requirements + design, flags,       ✋ accepted (+ tech lead if high risk)
                          policy conflicts)
/plan 0001             → Plan mode → stress test → plan.md            ✋ engineer accepts
/implement             → TDD per task; plan.md updated with any deviation in the same commit
/verify                → fresh-context verifier: VERIFIED?
/review → /pr          → Claude reviews per REVIEW.md (comments only)  ✋ CODEOWNER approves
/deploy                → staging + prod handoff                       ✋ named human approves production
/triage alert:api_error_rate → diagnosis → new intent.md              ✋ service owner: fix / schedule / close
```
Bug? `/fix "<bug>"`: failing test → you approve it → tests locked → fix.
Repeated mistake? `/learn`: a lesson in CLAUDE.md plus a regression eval.

## Guardrails
- **Hooks (deterministic):** force-push, push to main, destructive deletes, `curl | sh`, reading `.env`, `--no-verify`, merging PRs,
  writing credentials, editing protected paths (`.claude/protected-paths`), editing tests under the test lock, **any production deploy**.
- **Ask first:** `git push`, `gh pr create`, `gh issue create`, tags, releases.
- **Definition of done:** Claude can't end a turn with changes while `make check` fails.
- **Org level:** `governance/managed-settings.example.json`.

## Requirements
`git`, `make`, `bash`, `python3` (+ `pyyaml` for evals and bands), `jq` recommended · Claude Code · `gh` ·
optional: `shellcheck`, `actionlint`.
