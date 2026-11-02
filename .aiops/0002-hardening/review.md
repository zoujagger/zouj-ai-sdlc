---
id: 0002
verdict: CHANGES_REQUESTED
commit: ecd8f704a3dce786796e93383a10d4084908809c
score: 79/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-02
---

# Review: Harden gates and guards (review 0001 findings), round 2

<!-- State 5 PRE-REVIEW, round 2 (after S16-S24). Compiled only from the three fresh-context persona reports
     (base main @ c26f691, head ecd8f70). Round 1 (69/100) is in git history (fbd1da2). The human decides what happens next. -->

## Summary
Round 1's BLOCKER and HIGH are fixed and independently confirmed.
- **Checks:** `make check` passes (91 tests), `claude plugin validate .` passes, and hooks run in 26-120 ms.
- **ACs:** 20 of 22 are fully met, each with real-git, real-signature tests. AC-16 was tested with a real ssh-agent.
- **Red-first:** reproduced independently for 13 steps.
- **Signatures:** the re-approvals and the migration commit verify `G` against the allow-list.

Two security HIGHs remain, and they are deeper than parser gaps:
- **[HIGH] The signing toolchain can be tampered with.** An agent running as the user can repoint `gpg.ssh.program`
  in the repo git config, plant `.git/hooks`, or edit the installed plugin. The human's next `bin/sdlc approve`
  then captures the passphrase or touch and signs normally. Separately, the README's signing key doubles as the SSH
  auth key, so `AddKeysToAgent` can load it into an agent unnoticed.
- **[HIGH] Shell secret reads stop at `.env`.** `cat ~/.aws/credentials`, `cat x.pem`, `cat secrets/x`, `paste .env`
  and a directory Grep of `~/.ssh` are allowed, while the Read tool blocks them. `docs/architecture.md` overstates
  the coverage.

Verdict: **CHANGES_REQUESTED, 79/100.**
- **Verifier:** NOT VERIFIED. The causes were the stale round-1 review.md and unlogged deviations. This file is the fix for the first.
- **Security reviewer:** FAIL (2 high).
- **Code reviewer:** CHANGES_REQUESTED, with 3 MAJOR findings.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ⚠️ partial | `tests/test_guards.py:137` (listed forms). `<<` inside arithmetic (`$((1<<EOF))`) or `$'…'` is still taken as a marker, hiding later lines (`guards.py:181`) |
| AC-2 | ✅ met | `tests/test_guards.py:137` (state 4) |
| AC-3 | ✅ met | `tests/test_guards.py:157` |
| AC-4 | ✅ met | `tests/test_guards.py:175` |
| AC-5 | ✅ met | `tests/test_engine.py:133`, `tests/test_shell_hooks.py:171` |
| AC-6 | ✅ met | `tests/test_engine.py:120`, `tests/test_guards.py:79` |
| AC-7 | ✅ met | `tests/test_guards.py:202` |
| AC-8 | ✅ met | `tests/test_engine.py:196`, `:204` |
| AC-9 | ✅ met | `tests/test_engine.py:272`, `:281`, `:295`; `tests/test_cli.py:84` |
| AC-10 | ✅ met | `tests/test_shell_hooks.py:127` |
| AC-11 | ✅ met | `tests/test_shell_hooks.py:86` (listed `.env` readers). Non-`.env` secrets via the shell: see Security |
| AC-12 | ✅ met | `tests/test_cli.py:32`, `:14` |
| AC-13 | ✅ met | `tests/test_engine.py:87` |
| AC-14 | ✅ met | `tests/test_guards.py:37` |
| AC-15 | ✅ met | `tests/test_shell_hooks.py:106`, `:115`. `validate --ci --base origin/main` passes once this review replaces round 1's |
| AC-16 | ✅ met | `tests/test_engine.py:154` (real ssh-agent), `tests/test_cli.py:104`. The signing commit has a 10 s timeout (`machine.py:35`), so a slow passphrase is rolled back with a misleading message |
| AC-17 | ⚠️ partial | `tests/test_guards.py:149` (quotes and comments). Arithmetic and ANSI-C contexts still bypass it, as in AC-1 |
| AC-18 | ✅ met | `tests/test_guards.py:214` |
| AC-19 | ✅ met | `tests/test_engine.py:350`, `:357`; `tests/test_cli.py:77` |
| AC-20 | ⚠️ partial | `tests/test_guards.py:186` (listed forms). Allowed: `diff -u` patches with timestamps, `git apply -p0/--directory`, a patch from stdin, `tar -C .aiops -xf`, `tar --directory=.aiops`, `unzip -d .aiops`, `find -iname` |
| AC-21 | ✅ met | `tests/test_shell_hooks.py:67` |
| AC-22 | ✅ met | `tests/test_engine.py:324`, `tests/test_guards.py:166`, `tests/test_shell_hooks.py:26` |

## Security
- **[HIGH] Signing-toolchain tampering defeats R-10.** `approvals.py:129-135` commits with repo-local git config and hooks.
  - Not blocked: `git config gpg.ssh.program …`, `cp … .git/hooks/post-commit`, edits to the installed plugin code.
  - Fix:
    - Commit approvals with pinned settings: `-c gpg.ssh.program=ssh-keygen -c core.hooksPath=/dev/null --no-verify`.
    - Read `user.signingkey` from global config only, and refuse repo-local `gpg.*`, `user.signingkey` or `core.hooksPath` (doctor flags them too).
    - Guard `git config` of those keys and shell writes under `.git/` and the plugin root.
    - Recommend a dedicated signing key that isn't an `IdentityFile` and isn't auto-added to an agent (doctor warns).
    - Document approving from a separate OS user or a clean clone as the strongest setup.
- **[HIGH] Shell secret reads cover only `.env`.** `hooks/guard-bash.sh:31-62`, `hooks/guard-read.sh:20-33`.
  - Fix:
    - Apply `secret-paths` to every unquoted, tilde-expanded word of reader commands (or of any command).
    - Block a Grep/Glob `path` that equals, or is an ancestor of, a secret directory.
    - Add `*/.aws/*`, `*/.config/gcloud/*`, `*/.docker/config.json` and `*/.kube/config`.
    - Correct `docs/architecture.md`.
- **[MEDIUM] A PR defines its own audit workflow.** It can neuter `aiops-gates.yml` or `.claude/settings.json`
  through the shell (protected-paths cover only Edit/Write). Fix: enforce shell writes against protected-paths,
  require CODEOWNER review on `/.github/` and `/.claude/`, and recommend a ruleset "required workflow" or
  `pull_request_target`.
- **[LOW]**
  - Brace expansion (`{.aiops,x}`), `D=.aiops; rm -rf $D` and `unset ${a}CODE` get through.
  - `legacy-approvals --write` could still grandfather an agent-forged commit that passes the other checks. Restrict
    it to ancestors of the base that predate signing, and confirm each entry.
  - This repo's `ci.yml` falls back to `HEAD~1` instead of failing closed.
- **Production gate and force-push variants:** `make deploy ENV="prod"` (quoted), `git push origin '+main'`,
  `git push -fu`, `git push --mirror`.

Spec flags:

| Flag | Mitigated? |
|---|---|
| Signing-key access | **partially**: the precheck is undermined by toolchain tampering and agent auto-add |
| Self-trust | **yes** for data; **no** for the workflow file |
| Legacy loophole | **mostly** |
| Secret reads | **partially** |
| Supply chain | **yes**, mutable-tag residual |

## Plan conformance
- All 24 steps are ticked, and the diff matches the file lists.
- R-9 is met.
- Nothing out of scope ships.
- **Unlogged (MINOR):**
  - S17 touched `evals/_lib/repo.sh` and `tests/test_cli.py`, but not the planned `cli.py`.
  - S19 added `test_scaffold_gate_verifies_base`.
  - S21 touched `hooks/lib.sh`.
  - S24 changed `approve()` behaviour, plus `skills/init` and `skills/using-zouj-ai-sdlc`.
  - Extra tests are missing from the test table.

## Test-first evidence
- Every step S1-S24 carries `Red:`/`Green:`, and the counts climb from 59 to 91.
- The code reviewer ran each step's proof test against the parent commit for 13 steps: all fail with assertions and
  pass at HEAD.
- S14's pinned test (logged) and S15's human step (by design) have no red.
- Not covered: the signing-timeout path and the `-iname` predicate.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 33 | AC-1, AC-17 and AC-20 partial |
| Security | 25 | 15 | 2 HIGH (toolchain tampering, shell secret reads), 1 MEDIUM, LOWs |
| Test quality & test-first | 20 | 18 | real behavioural tests; red independently confirmed for 13 steps; a few untested paths |
| Plan conformance | 10 | 9 | small unlogged deviations |
| Maintainability | 5 | 4 | the regex lists grow and show false positives (`echo $HOME close …`, `[ "$CLAUDECODE" = 1 ]`) |
| **Total** | 100 | **79** | **CHANGES_REQUESTED**: below 80 and two HIGH findings |

### Fixes requested
1. **HIGH:** pinned, hook-less approval commits; global-only signing config, with repo overrides refused; guard
   `git config`, `.git/` and the plugin root; a dedicated signing key; document the approval-isolation options.
2. **HIGH:** `secret-paths` on all shell words; directory Grep/Glob; more secret globs; correct the docs.
3. **MEDIUM:** protected-paths for shell writes; CODEOWNERS for `/.github/` and `/.claude/`; a required-workflow recommendation.
4. **MAJOR:**
   - heredoc arithmetic and ANSI-C contexts
   - the remaining AC-20 forms (timestamped patches, `-p0`/`--directory`, stdin, tar arg order, `unzip -d`, `-iname`)
   - no timeout on the signing commit, with an accurate message
5. **LOW/MINOR:**
   - brace expansion and variable targets
   - `--write` restricted to pre-signing ancestors
   - `ci.yml` fails closed
   - quoted `ENV="prod"`, `'+main'`, `-fu`, `--mirror`
   - false positives in the dynamic-word and trailer rules
   - `sk-` keys with `no-touch-required`
   - the Deviation log and test table
