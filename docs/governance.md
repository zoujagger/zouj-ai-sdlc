# Governance, sources of truth and metrics

## Single source of truth per artifact
| Artifact | Home | Rule |
|---|---|---|
| Intent, spec, plan, review | `.aiops/NNNN-slug/*.md` (in the code repo) | When a ticket is the source, `intent.md` links to it (`source: #412`) |
| Gate approvals | front matter `approved-*` + the `AIOps-Approval:` commit | Written only by the human approval path. Audited in CI |
| Decisions | `docs/adr/` | Immutable once accepted |
| Review findings | `review.md` + PR comments → `CLAUDE.md` Lessons | Recurring findings become lessons (`/zouj-ai-sdlc:learn`) |
| Incidents | `docs/postmortems/` + `evals/` | Each incident yields a regression eval |

## Audit trail
For any change, git holds the full chain: **intent → spec → plan → approval commits → step commits (`Red:`/`Green:`) →
review.md → PR → merge → deploy**. Branch protection records who merged, and `sdlc validate --ci` proves who opened each gate.

## Human gates
| Gate | Decision | Owner | How |
|---|---|---|---|
| Intent | Worth doing? | Product owner | types `Intent Approved NNNN` |
| Spec | Right thing? Flags and data-leak risks resolved? | Product owner (+ tech lead if `risk: high`) | types `Spec Approved NNNN` |
| Plan | Right approach? | Engineer | types `Plan Approved NNNN` |
| Merge | Safe to merge? (never the authoring agent) | CODEOWNER | merges the PR |
| Production deploy | Ship it? | Named approver | GitHub Environment `production` |
| Maintain triage | Fix / schedule / close? | Service owner | `/zouj-ai-sdlc:triage` → new intent or `sdlc close` |

## Skills vs hooks
A skill is **advisory**: it makes violations rare. A hook is **deterministic**: it makes them close to impossible.
Absolute rules (gates, the read-only lock, secrets, protected paths, the test lock, merge and prod deploy) live in hooks.
Judgement (security policy, UX, brand) lives in skills.

### Hook profiles (`SDLC_HOOK_PROFILE`)
| Profile | Read-only lock | `post-edit-format` | Stop (`make check`) | Use for |
|---|---|---|---|---|
| `standard` (default) | enforced | lint blocks, format warns | must pass | normal work |
| `strict` | enforced | lint and format block | must pass | mature codebases, release branches |
| `spike` | **lifted** | lint warns | not enforced (unless a `/fix` lock is active) | throwaway exploration that won't become a PR |

Approval, merge, production, secrets, force-push and test-lock rules hold in **every** profile.

## Org-level enforcement
- Make `aiops-gates / audit` a required status check, and require CODEOWNERS review on `.aiops/`.
- Managed settings (`governance/managed-settings.example.json`, copied by `sdlc init`) can enforce permissions,
  disable bypass mode, and allow only approved marketplaces, including this plugin's.

## Metrics (`/zouj-ai-sdlc:retro`)
| Leading (process health) | Lagging (outcomes) |
|---|---|
| Time intent → spec approved → plan approved (`approved-at` stamps) | Rework: deviation-log rows, re-approvals after stale gates |
| % of merged PRs with a complete `.aiops/` chain | Change failure rate |
| Review scores and CHANGES_REQUESTED rate | MTTR |
| Hook blocks per session (approval fatigue vs real catches) | Escaped defects per release |

## Anti-patterns
- Typing an approval phrase without reading the artifact. The gate is only as good as the review behind it.
- Widening `.aiops/config/readonly-exempt` until the read-only lock means nothing.
- Leaving `spike` on for work headed to a PR.
- Running more parallel sessions than you can review (keep it to 2-3).
- Letting `CLAUDE.md` go stale or grow beyond about a page.
