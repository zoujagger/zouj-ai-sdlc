# Governance, source of truth & metrics

## Single source of truth per artifact
Choose **one** home for each artifact. Duplicated sources drift.

| Artifact | Default home (this template) | Alternative | Rule |
|---|---|---|---|
| Intent | `docs/intents/NNNN-*/intent.md` | Jira / ServiceNow ticket | If the ticket is the source, `intent.md` just links to it |
| Spec (requirements + design) | `spec.md` | Requirements tool | Link both ways |
| Plan | `plan.md` | — | Always in the repo, next to the code |
| Decisions | `docs/adr/` | — | Immutable once accepted |
| Review findings | PR comments → `CLAUDE.md` Lessons | — | Recurring findings become lessons |
| Incidents | `docs/postmortems/` + `evals/tasks/` | Incident tool | Each incident yields a regression eval |

## Audit trail
For any change, git history holds the full chain:
**intent → spec → plan → diff → tests → review findings → deploy**.
The PR template links all three documents, and branch protection records who approved.

## Human gates
| Gate | Decision | Owner |
|---|---|---|
| Intent validated | Worth doing? | Product owner |
| Spec accepted | Right thing, policy conflicts resolved? (tech lead if high risk) | Product owner (+ compliance / tech lead) |
| Plan accepted | Right approach? | Engineer |
| PR approved | Safe to merge? (never the authoring agent) | CODEOWNER |
| Production deploy | Ship it? | Named approver (GitHub Environment) |
| Maintain triage | Fix / schedule / close? | Service owner |

## Skills vs hooks
A skill is **advisory**: it makes violations rare. A hook is **deterministic**: it makes them close to impossible.
Put absolute rules (secrets, protected paths, test lock, prod deploy) in hooks. Put judgement (security policy, UX, brand) in skills.

### Hook profiles (`SDLC_HOOK_PROFILE`)
The inner-loop hooks have three strictness levels. The safety guards (`guard-bash`, `guard-files`, `guard-tests`, `guard-deploy`)
ignore the profile. Production, test-lock, secrets and force-push rules hold in every profile, and `validate-template` checks this.
| Profile | `post-edit-format` | `stop-verify` (definition of done) | Use for |
|---|---|---|---|
| `standard` (default) | lint failures block, format failures warn | `make check` must pass | Normal work |
| `strict` | lint and format failures block | `make check` must pass | Mature codebases, release branches |
| `spike` | lint failures warn | not enforced, unless a `/fix` test lock is active | Throwaway exploration that won't become a PR |

Set it per session (`SDLC_HOOK_PROFILE=spike claude`) or per checkout in `.claude/settings.local.json` (git-ignored) (`"env": {"SDLC_HOOK_PROFILE": "spike"}`).
The session-start hook announces a non-default profile. Leave spike mode before `/verify` or `/pr`. Org admins can pin it in managed settings.

## Managed settings (org-level enforcement)
Copy `governance/managed-settings.example.json` to the OS managed-settings location
(Linux/WSL: `/etc/claude-code/managed-settings.json`; macOS: `/Library/Application Support/ClaudeCode/managed-settings.json`).
Use it to enforce permissions, disable bypass mode, allow only managed hooks, enable the sandbox, and approve plugin marketplaces.
Check the key names against the current Claude Code settings documentation before you roll it out.

## Metrics
| Leading (process health) | Lagging (outcomes) |
|---|---|
| Time from `intent.md` to accepted `spec.md` | Rework after build started (deviation-log entries, reopened PRs) |
| Time from accepted spec to accepted `plan.md` | Change failure rate |
| % PRs with a linked intent/spec/plan | Mean time to restore (MTTR) |
| Eval pass rate on config changes | Escaped defects / incidents per release |
| AI review findings per PR (trend) | Lead time intent → production |

Review these in `/retro`.

## Anti-patterns
- Reviewing every line by hand when agents produced most of the diff and the mechanical checks already pass.
- Relying on a skill alone for an absolute rule, with no hook behind it.
- Letting the agent edit tests to make a fix pass (blocked by the test lock).
- Agents bypassing branch protection or deploying to production.
- Running more parallel sessions than you can actually review (keep it to 2-3).
- Letting `CLAUDE.md` go stale or grow beyond about a page.
- So many approval prompts in the inner loop that people approve without reading. Use auto mode for routine, well-tested work.
- Unmanaged local hooks or MCP servers.
