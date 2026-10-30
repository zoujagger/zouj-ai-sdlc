# REVIEW.md: how changes are reviewed

This file drives state 5 (`/zouj-ai-sdlc:review` → `review.md`), the PR review workflow, and human reviewers.
Review **intent and risk**, not every line. Mechanical checks (format, lint, types, tests) already run in CI and hooks.

## Inputs
1. The diff (`git diff main...HEAD`).
2. The linked `.aiops/NNNN-slug/`: `intent.md`, `spec.md`, `plan.md` (including the **Deviation log**).
3. `CLAUDE.md`, the relevant ADRs in `docs/adr/`, and the policy skills.

A non-trivial change with no linked intent is a **MAJOR** finding.

## Passes
1. **Spec conformance**: every AC is met and proven by a test that would fail without the change, and nothing out of scope ships.
2. **Bugs**: logic, edge cases, error handling, concurrency, compatibility, migration safety.
3. **Security**: findings with a plausible exploit path only. Check that every spec **Security & data-leak flag** is mitigated.
4. **Plan conformance**: the code matches the plan's Steps, and every divergence is in the Deviation log.
5. **Test-first evidence**: the proof tests went red before the code (`Red:` lines in the commits, or run output).

## Severity
| Level | Meaning | Verdict |
|---|---|---|
| BLOCKER | Incorrect, insecure, or violates the spec | CHANGES_REQUESTED |
| MAJOR | Likely bug, missing test, unlogged deviation | Fix or justify |
| MINOR | Maintainability, clarity | Author's call |

## Score (review.md)
Spec conformance 40 · Security 25 · Test quality & test-first 20 · Plan conformance 10 · Maintainability 5.
**PASS** needs ≥ 80, no BLOCKER, no CRITICAL/HIGH security finding, and every AC met. PASS is advice: **the human decides the merge**.

## Rules
- The agent that wrote the code never approves or merges. Approval comes from CODEOWNERS via branch protection.
- Findings that recur go into `CLAUDE.md` → Lessons (`/zouj-ai-sdlc:learn`).
