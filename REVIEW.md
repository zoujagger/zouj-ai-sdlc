# REVIEW.md: how pull requests are reviewed

This file drives the Claude PR review (`.github/workflows/claude-pr-review.yml`, `/review`, `code-reviewer` and `security-reviewer` agents).
Human reviewers use it too.

> Review **intent and risk**, not every line. Mechanical checks (format, lint, types, tests, evals) are already
> attached to the PR by CI and hooks, so don't repeat them.

## Inputs
1. The PR diff.
2. The linked `docs/intents/NNNN-slug/` → `intent.md`, `spec.md`, `plan.md` (including the **Deviation log**).
3. `CLAUDE.md`, the relevant ADRs in `docs/adr/`, and the policy skills in `.claude/skills/policy-*/`.

If a non-trivial PR has no linked intent, that is itself a **MAJOR** finding.

## Passes (run in order; report findings per pass)
### Pass 1: Bugs
Logic errors, edge cases, error handling, concurrency, resource leaks, backward compatibility, migration safety.
Every behavior change has a test that would fail without it.

### Pass 2: Security
Only findings with a plausible exploit path: injection, authn/authz, secrets, PII, SSRF, deserialization,
dependency and supply-chain risk, CI workflow permissions and untrusted input. See `.claude/agents/security-reviewer.md`.

### Pass 3: Conformance to spec.md and plan.md
- Every AC in `spec.md` is satisfied and tested, and nothing out of scope is shipped.
- The code matches `plan.md`. Divergences are recorded in the Deviation log **in the same commit**.
- Flags and policy conflicts raised in `spec.md` were resolved as decided.

## Severity
| Level | Meaning | Merge? |
|---|---|---|
| BLOCKER | Incorrect, insecure, or violates the spec | No |
| MAJOR | Likely bug, missing test, unlogged deviation | Fix or justify |
| MINOR | Maintainability, clarity | Author's call |
| NIT | Taste | Optional; prefer omitting |

## Output format
```
## Verdict: LGTM | CHANGES_SUGGESTED   (AI review never approves; humans approve)
### Pass 1 - Bugs
- [SEVERITY] path:line - problem → suggestion
### Pass 2 - Security
### Pass 3 - Conformance (spec.md / plan.md)
### Lessons
- <Pattern worth adding to CLAUDE.md "Lessons", if any>
```

## Rules
- **The agent that wrote the code cannot approve its own PR.** Claude only comments. Approval comes from CODEOWNERS via branch protection.
- Findings that recur go into `CLAUDE.md` → Lessons (via `/learn`) so they stop recurring.
