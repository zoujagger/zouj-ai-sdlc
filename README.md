# zouj-ai-sdlc

A [Claude Code](https://code.claude.com) plugin that runs your software lifecycle as a **state machine over Markdown
artifacts versioned in Git**. It's inspired by [Superpowers](https://github.com/obra/superpowers) (a bootstrap skill,
trigger-style skills, red-flag tables, subagent-driven execution) and strictly modeled on Anthropic's *AI-Native SDLC
Playbook*: work starts from an intent, every state commits an artifact the next one reads, and **humans decide at every
gate**. Here those gates are enforced by hooks instead of being left to the model's good behaviour.

```
 1 BRAINSTORMING ──▶ 2 SPECIFICATION ──▶ 3 PLAN (read-only) ──▶ 4 EXECUTION (autonomous) ──▶ 5 PRE-REVIEW
   intent.md          spec.md             plan.md                code + green tests            review.md + pr.md
 ✋ "Intent Approved"  ✋ "Spec Approved"   ✋ "Plan Approved"       (make check green)             ✋ the human merges
```

## Install
```bash
/plugin marketplace add zoujagger/zouj-ai-sdlc
/plugin install zouj-ai-sdlc@zouj
```
Or in one step (Claude Code 2.1.275+): `/plugin install zouj-ai-sdlc --marketplace zoujagger/zouj-ai-sdlc`.
Then, in each repo that should follow the workflow: `/zouj-ai-sdlc:init` (or `sdlc init --stack python|node|go`).

The plugin is **dormant in repos without `.aiops/`**: no hook blocks anything until you run init.
Requirements: `git`, `make`, `python3` ≥ 3.9 (stdlib only). `gh` and `jq` are optional.

## How it works
| State | You run | The agent produces | Leaves the state when |
|---|---|---|---|
| 1 BRAINSTORMING | `/zouj-ai-sdlc:intent "<need>"` | a targeted clarification interview → `.aiops/NNNN-slug/intent.md` | you type **`Intent Approved NNNN`** |
| 2 SPECIFICATION | `/zouj-ai-sdlc:spec` | `spec.md`: requirements, ACs, **DB schema, API contracts, security and data-leak flags** | you type **`Spec Approved NNNN`** |
| 3 PLAN | `/zouj-ai-sdlc:plan` | `plan.md`: chronological file-by-file steps, risks, test definitions. **Code is read-only** | you type **`Plan Approved NNNN`** |
| 4 EXECUTION | `/zouj-ai-sdlc:implement` | per step: proof test → see it fail → code → green, on `feat/NNNN-slug`, no questions asked | every step ticked, `make check` green |
| 5 PRE-REVIEW | `/zouj-ai-sdlc:review` | fresh-context verifier, code-reviewer and security-reviewer → `review.md` (score /100) + `pr.md` | **you** merge (the agent can't) |

`sdlc status` (or `/zouj-ai-sdlc:status`) always shows the state, who it's waiting on, and the exact next step.
The state is **derived** from the artifacts and git, never stored.

## What is enforced (and how)
| Rule | Mechanism |
|---|---|
| Only a human opens a gate | A `UserPromptSubmit` hook accepts the phrase only as the *whole* prompt. It stamps `approved-by/at/via/sha256` and commits the file alone with an `AIOps-Approval:` trailer. Edits to `status`/`approved-*`, `sdlc approve`, and forged trailers are blocked |
| States 1-3 are read-only | `sdlc hook pre-edit` and `pre-bash` block writes outside `.aiops/` and docs: Edit/Write, redirects, `sed -i`, `cp/mv/rm`, package installs, formatters, `git add/commit/apply/stash` of code |
| Artifacts in order | `spec.md` needs an approved intent, `plan.md` an approved spec, `review.md` an approved plan. New artifacts start as Draft |
| Approvals can't silently drift | Editing an approved body re-closes its gate. Plans keep their approval when steps are ticked and the Deviation log grows |
| Schema-valid artifacts | `schemas/*.json`: required front matter and sections, AC ids, every AC covered by the plan and the review. Checked after each edit and before each approval |
| Definition of done | The Stop hook requires `make check` green. A PASS review goes stale if code changes after it |
| Human-only final gate | Merging on main, `gh pr merge`/approve, pushing to main, and production deploys are blocked |
| CI audit | `aiops-gates.yml` runs `sdlc validate --all --ci`: every open gate must trace to a non-agent approval commit |
| Existing safety guards | secrets, `.env`, force-push, history rewrites, protected paths, the `/fix` test lock |

Local hooks are a strong deterrent, not a sandbox. The CI audit plus CODEOWNERS on `.aiops/` are the backstop
([docs/architecture.md](docs/architecture.md#threat-model)).

## Components
| Kind | Location | Contents |
|---|---|---|
| Skills | `skills/` | `using-zouj-ai-sdlc` (bootstrap, injected at session start) · core states `intent` `spec` `plan` `implement` `review` `pr` `status` · `init` `fix` `parallel` · Maintain `deploy` `triage` `incident` `postmortem` `retro` `release` `learn` `adr` `security-check` · `help-me` `onboard` · policies (security, compliance, UX, brand) |
| Agents | `agents/` | product-analyst, architect, planner, implementer, verifier, code-reviewer, security-reviewer, test-engineer, docs-writer, release-manager, diagnostician, incident-responder |
| Hooks | `hooks/hooks.json` | SessionStart, UserPromptSubmit (approvals), PreToolUse (gate, lock, bash, files, tests, deploy guards), PostToolUse (validate + format/lint), Stop (`make check`) |
| Engine | `bin/sdlc`, `lib/sdlc_engine/`, `schemas/` | `status next new draft use validate approve close lock unlock init doctor` |
| Templates | `templates/artifacts/`, `templates/scaffold/` | artifact templates · what `init` copies into a repo (Makefile contract, CLAUDE.md, REVIEW.md, CI, bands) |
| Tests / evals | `tests/`, `evals/` | deterministic guard tests (`make test`) · behavioural evals (`make evals`, the `claude plugin eval` format) |

## Configuration (per repo, human-owned)
- `.aiops/config.json`: `lock_when_idle` (code is read-only with no active intent, default true), `commit_approvals`, `main_branch`.
- `.aiops/config/{readonly-exempt,protected-paths,test-paths}` extend the plugin's `defaults/`.
- `SDLC_HOOK_PROFILE=spike` lifts the read-only lock and `make check` for throwaway exploration. The approval and merge gates still hold.
- The active intent comes from the branch (`feat/NNNN-*`), else `sdlc use NNNN`, else `$AIOPS_INTENT`.
- Unattended state 4: plugins can't grant permissions, so add the allow-rules from `.aiops/README.md` to `.claude/settings.json`.

## Develop
```bash
make check        # lint + compile + 58 unit/hook tests
make validate     # claude plugin validate .
make dev          # claude --plugin-dir .
make evals        # behavioural evals against a live model
```
Docs: [state machine](docs/state-machine.md) · [architecture](docs/architecture.md) · [playbook mapping](docs/sdlc.md) ·
[governance](docs/governance.md) · [worked example](docs/examples/0001-csv-export/). This repo dogfoods itself:
see [`.aiops/0001-zouj-ai-sdlc-plugin/`](.aiops/0001-zouj-ai-sdlc-plugin/).
