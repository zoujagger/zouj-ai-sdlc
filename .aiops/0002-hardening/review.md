---
id: 0002
verdict: CHANGES_REQUESTED
commit: 417a48e42435f8c8fbf450b9499e2e6398e2491a
score: 69/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-02
---

# Review: Harden gates and guards (review 0001 findings)

<!-- State 5 PRE-REVIEW. Compiled only from the three fresh-context persona reports (base main @ c26f691, head 417a48e).
     The human decides what happens next. -->

## Summary
`make check` passes (79 tests) and `claude plugin validate .` passes (ICON_MISSING warning). `sdlc validate --all --ci --base main`
passes through the documented bootstrap rule. All three reviewers confirm:
- every AC's listed cases are tested, and the tests assert real behaviour
- the code-reviewer **independently reproduced red for all 15 steps**
- gate order was correct (approvals before S1)
- only allow-listed keys verify (`%G?` = G), and a PR can't add its own signer when the base has a list

But the change doesn't meet its central outcome under default settings:
- **[BLOCKER] Regression.** The new heredoc stripper treats `<<WORD` inside quotes or comments as a marker, which hides
  the following lines from the guard. `main` blocks these cases.
- **[HIGH] Forgery still works.** Plain-shell forms of R-4 (`export -n`, wrapper functions, `sdlc $(echo approve)`,
  `env -`, a copied binary) let an agent produce a *signed* approval when the key is unprotected. Only the key's
  protection stands in the way, and `doctor` merely warns about it.
- **[MAJOR] An unresolvable `--base` fails open** into the bootstrap path (flagged by all three reviewers).

Verdict: **CHANGES_REQUESTED, 69/100.** The verifier says VERIFIED with one MAJOR gap, the security reviewer says
PASS 19/25 with 3 MEDIUM, and the code reviewer says CHANGES_REQUESTED with a BLOCKER and a HIGH.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ⚠️ partial | `tests/test_guards.py:137` (listed cases). Marker detection inside quotes and comments breaks R-2 (BLOCKER) |
| AC-2 | ✅ met | `tests/test_guards.py:137` (state 4: artifact, state, config) |
| AC-3 | ✅ met | `tests/test_guards.py:149` |
| AC-4 | ⚠️ partial | `tests/test_guards.py:158` (listed cases). Allowed: `rm -rf .ai*`, `rm -rf $PWD/.aiops`, `"$(pwd)/.aiops"`, `cd .aiops && rm -rf *`, `find . -name test-lock -delete`, `tar -xf … -C .aiops` |
| AC-5 | ✅ met | `tests/test_engine.py:133`, `tests/test_shell_hooks.py:151` |
| AC-6 | ✅ met | `tests/test_engine.py:120`, `tests/test_guards.py:79` |
| AC-7 | ⚠️ partial | `tests/test_guards.py:169` (listed forms). Allowed: `export -n`, `declare +x`, `env -`, `f(){ sdlc "$@"; }; f approve`, `sdlc $(echo approve)`, `x=approve; sdlc $x`, `xargs sdlc`, `cp bin/sdlc /tmp/s && /tmp/s approve`, a split `AIOps-Approval` trailer string |
| AC-8 | ✅ met | `tests/test_engine.py:154`, `:162` |
| AC-9 | ⚠️ partial | `tests/test_engine.py:253`, `:282`, `tests/test_cli.py:61` cover the negatives. **No positive test** (allow-listed signature passing with `--base`). An unresolvable base fails open (`approvals.py:126-132`) |
| AC-10 | ✅ met | `tests/test_shell_hooks.py:107` |
| AC-11 | ⚠️ partial | `tests/test_shell_hooks.py:66` (listed cases). Allowed: `cp .env /tmp/x; cat .env.example` (whole-command exemption), quoted names, globs (`.e?v`), symlinked secrets, `~/.ssh/id_ed25519`, nested `sub/secrets/` |
| AC-12 | ✅ met | `tests/test_cli.py:32`, `:14` |
| AC-13 | ✅ met | `tests/test_engine.py:87` |
| AC-14 | ✅ met | `tests/test_guards.py:37` |
| AC-15 | ✅ met | `tests/test_shell_hooks.py:86`, `:95`; validate by hand. This PR's own CI still runs main's v0.1.0 engine (residual until 0.2.0 is on main) |

## Security
- **[HIGH] An agent can forge a signed approval.** `guards.py:157-168`, `cli.py:340`.
  - How: `export -n CLAUDECODE CLAUDE_CODE_CHILD_SESSION; f(){ sdlc "$@"; }; f approve 0001 intent` passes the pre-bash hook.
    With an unprotected key the commit is signed, and `audit()` returns `[]`.
  - Fix: decide the key-protection policy (spec open question) and harden R-4 for the reproduced forms.
- **[MEDIUM] The trust anchor fails open on an unresolvable `--base`.** `approvals.py:126-132`.
  - A missing ref is treated like a missing file. An empty or missing `--base` value audits the working tree silently.
  - The scaffold doesn't verify `BASE_SHA`.
  - Fix: `git rev-parse --verify REF^{commit}`, and fail closed.
- **[MEDIUM] Signing through ssh-agent goes undetected.** A passphrase-protected key cached in `ssh-agent` without `-c`
  signs silently, and `doctor` doesn't see it.
  - The trailer check runs on the raw command, not the unquoted one.
  - `git apply` and `git am` can write into `.aiops/`.
- **[MEDIUM] Secret reads.** Quoted and globbed names, symlinks, and `~/.ssh/*` get through. `id_ed25519` isn't in
  `secret-paths`. `secrets/*` matches only at the root, and matching is case-sensitive.
- **[LOW] Legacy matching and recording.**
  - Legacy entries match by sha prefix; they should require a full sha.
  - `legacy-approvals --write` records any unsigned approval without the other audit checks.
- Spec flags: signing-key access is **partially** mitigated; self-trust **yes, but fails open**; legacy list **mostly**;
  secret reads **partially**; supply chain **yes**, with the mutable-tag residual.

## Plan conformance
- S1–S15 are ticked and present. The Deviation log has 4 rows, each with a commit ref.
- **Unlogged (MINOR):**
  - `templates/scaffold/.aiops/config/secret-paths` (S10)
  - `evals/_lib/repo.sh` signing (S6, only in the commit body)
  - `aiops_enabled` changed in S8, and the planned `secret_match` was implemented as `config_match … secret-paths`
  - reformatting churn in `plugin.json` and `hooks.json`
- **Stale text:** `hooks/hooks.json` still says every hook is a no-op without `.aiops/`. `CHANGELOG.md` claims "any
  change … blocked" for the env markers.
- **Outside 0002 in this branch:** 0001's `review.md` and `pr.md` (`5816707`), which precede the intent. Mention them in the PR.

## Test-first evidence
- Every step commit carries `Red:`/`Green:`. The code reviewer **re-ran each step's tests against the parent commit:
  red for 15/15** (S14's pin test declared, honestly, as having no red).
- Caveat: tests and code land in the same commit, so the history alone doesn't show red. A multi-case test only
  proves its first failing assertion.
- Missing tests:
  - the AC-9 positive base case
  - heredoc markers inside quotes and comments
  - the compound `.env.example` command
  - glob and `$PWD` deletes of `.aiops`

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 27 | AC-1, AC-4, AC-7, AC-9 and AC-11 partial; the central outcome isn't met with an unprotected key |
| Security | 25 | 14 | 1 HIGH reproduced end to end, 3 MEDIUM, 2 LOW |
| Test quality & test-first | 20 | 16 | red reproduced 15/15; behavioural tests; positive and negative gaps listed above |
| Plan conformance | 10 | 8 | all steps done; small unlogged deviations and churn |
| Maintainability | 5 | 4 | small helpers; the regex-heavy parser keeps growing; stale hooks.json description |
| **Total** | 100 | **69** | **CHANGES_REQUESTED**: one BLOCKER and one HIGH |

### Fixes requested, in order
1. **BLOCKER:** detect heredoc markers only outside quotes and comments. Add the reproduced negatives as tests.
2. **HIGH:** decide the key-protection policy, then harden R-4:
   - `export -n` / `declare +x` / `typeset +x` / `env -`
   - functions or aliases that wrap `sdlc`
   - a non-literal or dynamic first argument to `sdlc`
   - `xargs sdlc` and copied engine binaries
   - the trailer check on the unquoted command
3. **MAJOR:** fail closed on an unresolvable or empty `--base`. Verify `BASE_SHA` in the scaffold. Test the AC-9 positive path.
4. **MAJOR:** `.aiops` integrity against globs, `$PWD`/`$(pwd)`, `find` start paths, `tar -C` and `git apply/am`.
5. **MAJOR:** remove `.env.example` tokens instead of exempting the whole command. Unquote before matching shell secret
   reads. Resolve symlinks in guard-read. Extend `secret-paths` (`*id_ed25519*`, `*id_ecdsa*`, `*/.ssh/*`,
   `*/.aws/credentials`, `*/.netrc`, `*/.npmrc`, `*/secrets/*`). Add `~/.ssh` deny rules to the scaffold.
6. **LOW:** legacy entries need a full sha; `legacy-approvals --write` lists only commits that pass the other audit checks.
7. **MINOR:**
   - force-push through a `+` refspec
   - `git --work-tree`
   - `curl -o` / `wget -O` while locked
   - the stale hooks.json description and CHANGELOG wording
   - log the unlogged deviations
   - document the remaining regex residuals
