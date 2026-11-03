---
id: 0002
verdict: CHANGES_REQUESTED
commit: 44517a055289f7de88e81dc29651415ae158c7dc
score: 73/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-03
---

# Review: Harden gates and guards (review 0001 findings), round 3

<!-- State 5 PRE-REVIEW, round 3 (after S25-S32). Compiled only from the three fresh-context persona reports
     (base main @ c26f691, head 44517a0). Round 2 (79/100) is in git history. The human decides what happens next. -->

## Summary
Every round-2 fix is in place, and the step tests went red before the code.
- **Checks:** `make check` passes (102 tests). Locally the lint step ran only `bash -n`, because ruff and shellcheck aren't installed; CI installs both. `claude plugin validate .` passes with the existing warnings (CLAUDE.md, ICON_MISSING). Hooks run in 39-90 ms for typical commands.
- **ACs:** the verifier found a proving test for all 29 ACs and ran each one green. AC-15 also needs this file, because it references AC-23..AC-29.
- **Red-first:** the code reviewer reproduced red on the parent commit for all nine round-3 proof tests.

Two findings still block:
- **[BLOCKER] S30 reopened disguised engine calls (AC-7, R-4).** The new command-position rule (`guards.py:159`) misses
  `eval "$s approve …"`, `bash -c "$s approve …"`, `nice`/`timeout`/`xargs -I{}`/`!`/`{ …; }` prefixes. The code
  reviewer reproduced an end-to-end forged approval under `approval_key_policy: "any"`, which is this repo's setting.
- **[HIGH] Repo-local git config still runs code inside the human's approval.** `core.fsmonitor`, `filter.*.clean`,
  `core.attributesFile` and `include.path` are neither guarded nor refused. Confirmed: a planted fsmonitor ran during
  the pinned approval commit and could capture the passphrase or touch.

Verdict: **CHANGES_REQUESTED, 73/100.**
- **Verifier:** VERIFIED, on the condition that this round-3 file references AC-23..AC-29. It does.
- **Security reviewer:** FAIL (1 HIGH, 1 MEDIUM).
- **Code reviewer:** CHANGES_REQUESTED (1 BLOCKER, 5 MAJOR).

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_guards.py:137` |
| AC-2 | ✅ met | `tests/test_guards.py:137` (state 4) |
| AC-3 | ✅ met | `tests/test_guards.py:166` |
| AC-4 | ✅ met | `tests/test_guards.py:184` |
| AC-5 | ✅ met | `tests/test_engine.py:133`, `tests/test_shell_hooks.py:215` |
| AC-6 | ✅ met | `tests/test_engine.py:120`, `tests/test_guards.py:79` |
| AC-7 | ⚠️ partial | `tests/test_guards.py:234` (listed forms pass). **Regressed:** `eval`/`bash -c`/`nice`/`timeout`/`xargs -I{}`/`!`/`{` with a dynamic command word are allowed (`guards.py:159`) |
| AC-8 | ✅ met | `tests/test_engine.py:228`, `:236` |
| AC-9 | ✅ met | `tests/test_engine.py:313`, `:327`; `tests/test_cli.py:87` |
| AC-10 | ✅ met | `tests/test_shell_hooks.py:171` |
| AC-11 | ✅ met | `tests/test_shell_hooks.py:104` |
| AC-12 | ✅ met | `tests/test_cli.py:32` |
| AC-13 | ✅ met | `tests/test_engine.py:87` |
| AC-14 | ✅ met | `tests/test_guards.py:37` |
| AC-15 | ✅ met | `tests/test_shell_hooks.py:148`, `:157`. `validate --all --ci --base origin/main` exits 0 once this round-3 review is in place (checked in a scratch clone) |
| AC-16 | ✅ met | `tests/test_engine.py:185`, `tests/test_cli.py:108` |
| AC-17 | ✅ met | `tests/test_guards.py:158` |
| AC-18 | ⚠️ partial | `tests/test_guards.py:270` (listed forms). `m=AIOps-Approval; git commit -m "$m: plan"` was blocked at ecd8f70 and is allowed now (`guards.py:428`) |
| AC-19 | ✅ met | `tests/test_engine.py:424`, `:431`, `:442`; `tests/test_cli.py:80` |
| AC-20 | ✅ met | `tests/test_guards.py:195` |
| AC-21 | ✅ met | `tests/test_shell_hooks.py:85` |
| AC-22 | ✅ met | `tests/test_engine.py:356`, `tests/test_guards.py:175`, `tests/test_shell_hooks.py:26` |
| AC-23 | ⚠️ partial | `tests/test_engine.py:154`, `tests/test_guards.py:257`. Not covered: `core.fsmonitor`, `filter.*`, `include.path`, and the `git config --file .git/config …` / `git config set …` write forms. There's no doctor ✗ test, and the 15 s signer is checked only by a `timeout=None` spy |
| AC-24 | ⚠️ partial | `tests/test_shell_hooks.py:67` (listed cases). Still allowed: glob words (`cat ~/.aws/cred*`), `echo $(cat …)`, `cat<file`, and Grep with an ancestor `path` (R-12 "ancestor" isn't implemented) |
| AC-25 | ✅ met | `tests/test_guards.py:246`, `tests/test_cli.py:32`. Minor: `git checkout <rev> -- <protected path>` isn't checked |
| AC-26 | ✅ met | `tests/test_guards.py:149` |
| AC-27 | ✅ met | `tests/test_guards.py:211`. Residuals: `tar -C.aiops`, C-quoted patch paths, `for`/`read`/`printf -v` targets |
| AC-28 | ✅ met | `tests/test_shell_hooks.py:124`, `tests/test_guards.py:285` |
| AC-29 | ✅ met | `tests/test_engine.py:383`, `:411`; `tests/test_shell_hooks.py:157` |

## Security
- **[BLOCKER] Disguised engine calls through wrappers** (`guards.py:159`). Reproduced: `a=CLAUDE; eval "unset ${a}CODE ${a}_CODE_CHILD_SESSION"; s=sdlc; nice $s approve 0001 plan` passes pre-bash and creates a plan approval that `validate --all --ci` accepts under `"any"`.
  - Fix: treat the word after wrappers (`eval`, `nice`, `timeout N`, `stdbuf`, `setsid`, `ionice`, `!`, `{`, `xargs [opts]`) as a command position. Recurse ENGINE_RES and ENV_RES into `eval` and `-c` strings. Add these forms to the tests.
- **[HIGH] Code-running repo-local git config inside the approval** (`approvals.py:51-52, 106, 161-162`; `guards.py` `SIGNING_CONFIG_RE`). Allowed: `git config core.fsmonitor`, `core.attributesFile`, `filter.x.clean` and `include.path`. A planted fsmonitor ran 8 times during the pinned commit.
  - Fix: allow-list repo-local keys (read with `--show-scope --includes`). Pin `core.fsmonitor=false core.attributesFile=/dev/null` for `git add` and `commit`, or stage with `hash-object --no-filters`. Call git by absolute path. Guard `git config set|unset` and `-f/--file` under `.git/`. Document that approval must happen in the approver's own clean clone.
- **[MEDIUM] Shell secret reads skip glob words and substitutions** (`hooks/guard-bash.sh:70`, `:78`). Allowed: `cat ~/.aws/cred*`, `cat *.pem`, `echo $(cat ~/.aws/credentials)`, `cd ~/.aws && cat credentials`. Fix: expand globs (`compgen -G`), don't exempt segments that contain substitutions, and track `cd`.
- **[LOW]**
  - The per-word secret scan has false positives in every repo (`git commit -m "fix: load .env"`, `grep -rn id_rsa src`) and costs about 835 ms on a 60-line heredoc, against a 150 ms target.
  - Writes outside the repo aren't checked against `secret-paths` (`cp x ~/.gitconfig`).
  - This repo runs `"approval_key_policy": "any"`, and `origin/main` has no signer list (bootstrap). The merge needs explicit CODEOWNERS review of `.aiops/config/`.

Spec flags:

| Flag | Mitigated? |
|---|---|
| Signing-key access | **partially**: defeated by repo-local fsmonitor/filter code (HIGH); this repo uses `any` |
| Self-trust | **yes**: base-ref trust, fail-closed CI; the PR's own workflow is the documented residual |
| Legacy loophole | **yes**: main ancestors predating signing, full shas, confirmed per entry |
| Secret reads | **partially**: Read/Grep/Glob and literal shell words are covered; globs and substitutions aren't |
| Supply chain | **yes**, mutable-tag residual |

## Plan conformance
- S25-S32 are ticked, and the code matches the file lists. The S29, S31 and S32 deviations are logged.
- **Unlogged (MINOR):**
  - S26 implements "equals" for Grep/Glob, not R-12's "or is an ancestor of".
  - S25 also touched `tests/helpers.py`, `tests/test_cli.py` and `evals/_lib/repo.sh`.
  - S27 also applies `secret-paths` to shell writes.
  - S28 changed the tokenizer fallback.
- **MAJOR:** the setup help still says `git config gpg.format ssh` and `git config user.signingkey …` without `--global`, which S25 now refuses. Affected: `approvals.py:34-35`, `cli.py:348`, `README.md:76-77`, `templates/scaffold/.aiops/README.md:10`, `CHANGELOG.md:76`.
- **MINOR:** `evals/_lib/repo.sh:13` runs `git config --global` without isolating `GIT_CONFIG_GLOBAL`.
- Nothing out of scope ships.

## Test-first evidence
- Every S25-S32 commit carries `Red:`/`Green:`, and the test count climbs from 93 to 102.
- The code reviewer ran each round-3 proof test against its step's parent commit. All nine fail with assertions there and pass at the step.
- The S25 recorded red text differs slightly from the parent's real message (same assertion). The S27 CODEOWNERS part was a pin, as its commit says.
- Not covered: doctor ✗ for repo-local overrides, a real slow signer, regressions for the forms S30 reopened.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 30 | AC-7 regressed; AC-18, AC-23 and AC-24 partial |
| Security | 25 | 14 | 1 BLOCKER (wrapper engine calls), 1 HIGH (fsmonitor/filter/include), 1 MEDIUM |
| Test quality & test-first | 20 | 17 | red reproduced for all 9 round-3 tests; a few untested paths |
| Plan conformance | 10 | 8 | small unlogged extras; S26 narrowing |
| Maintainability | 5 | 4 | command-position allow-list is brittle; the secret scan adds false positives and latency |
| **Total** | 100 | **73** | **CHANGES_REQUESTED**: a BLOCKER, a HIGH, and below 80 |

### Fixes requested
1. **BLOCKER:** command position after wrappers; recurse engine/env checks into `eval` and `-c`; regression tests.
2. **HIGH:** an allow-list for repo-local git config (with includes); pin fsmonitor and attributes for `add` and `commit`; absolute git; guard `git config set|unset` and `--file`.
3. **MAJOR:** `--global` and a dedicated key in every setup hint (with a test).
4. **MEDIUM/MAJOR:** secret reads through globs, substitutions and `cd`; Grep ancestor paths (or amend R-12); fewer false positives and less latency in the per-word scan.
5. **MINOR:** the variable-built trailer; `git checkout/restore` against protected-paths; AC-27 residuals in the docs; `GIT_CONFIG_GLOBAL` in the evals; the Deviation log extras.
