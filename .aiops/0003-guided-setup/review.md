---
id: 0003
verdict: CHANGES_REQUESTED
commit: 29d9527b34cd887d778afeb756c5513093c5e445
score: 89/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-04
---

# Review: Guided setup and first-run onboarding (roadmap phase 1), round 5

<!-- State 5 PRE-REVIEW, round 5 (after H1–H4). Compiled only from the three fresh-context persona reports (base main
     @ 429614a, head 29d9527). Rounds 1 (76), 2 (80), 3 (78) and 4 (84) are in git history. The human decides what
     happens next. -->

## Summary
No reviewer found a BLOCKER, CRITICAL or HIGH finding.
- **Verifier:** VERIFIED. All 15 ACs have passing tests, and the H1–H4 proof tests are red on their parents.
- **Code reviewer:** no BLOCKER or HIGH, 1 MEDIUM. It asks for that MEDIUM to be fixed before a PASS.
- **Security reviewer:** PASS, 20/25, 1 MEDIUM and 3 LOW.
- **Round-4 fixes:** all hold.
  - H1: links are refused, a link swapped in mid-write fails, and a hard link is replaced (exploit attempts by two
    reviewers).
  - H2: under the agent, a new config gets init's defaults.
  - H3: one argument parser.
  - H4: the docs.
- **Checks:** `make check` (148 tests), `make build` and `claude plugin validate .` pass. The 2 validator warnings
  are unrelated: a root CLAUDE.md that isn't loaded, and no icon.

Verdict: **CHANGES_REQUESTED, 89/100.** The score clears 80 and there is no HIGH. But the verdict rule needs every
AC ✅, and AC-8 is still partial. The partial is the deferred FAIL-review case: no test shows that a FAIL review keeps
the intent at state 5. Two MEDIUMs are also open:
- **[MEDIUM, docs]** Since H2, setup run through the skill (`/zouj-ai-sdlc:setup solo`) creates a **team** config, and
  solo is only a human step. The README's "Just looking?" alternative, install path A and the quick reference still
  promise the skill route. A trial user would hit signing.
- **[MEDIUM, security]** setup and init scaffold any directory, including one that isn't a git repo:
  `machine.project_root` falls back to the current directory. So `cd ~ && sdlc setup --profile team --yes` under the
  agent creates `~/.claude/settings.json`, which is a toolchain path "never written by agents". From `~/.claude` it
  creates `~/.claude/CLAUDE.md`, which loads in every session.
  - The content is the fixed scaffold, and no existing file is overwritten.
  - This was already the case for `init` on main.
  - It contradicts the spec's "setup only ever writes in the repo it runs in".

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:109`; checked by hand under a pty (1.23 s) |
| AC-2 | ✅ met | `tests/test_setup.py:185` (status reads "No intents yet") |
| AC-3 | ✅ met | `tests/test_setup.py:213` (human rerun; an agent rerun isn't idempotent, LOW below) |
| AC-4 | ✅ met | `tests/test_setup.py:239`, `:252` (missing config, initialized and fresh) |
| AC-5 | ✅ met | `tests/test_setup.py:327`, `:272` |
| AC-6 | ✅ met | `tests/test_setup.py:123` |
| AC-7 | ✅ met | `tests/test_engine.py:513`, `:392`; `tests/test_playbook.py:83-86` |
| AC-8 | ⚠️ partial | `tests/test_playbook.py:77-130` covers the PASS walk; no test that a FAIL review stays at state 5 (verifier: met; code reviewer: partial) |
| AC-9 | ✅ met | `tests/test_cli.py` `Init::test_scaffold_offers_the_plugin` |
| AC-10 | ✅ met | `tests/test_setup.py:422`, `:434` |
| AC-11 | ✅ met | `tests/test_setup.py:75` |
| AC-12 | ✅ met | `tests/test_shell_hooks.py` `test_onboarding_docs`, `test_setup_skill_follows_the_playbook` |
| AC-13 | ✅ met | `tests/test_setup.py:448` |
| AC-14 | ✅ met | `test_version_matches_changelog`; `make build` |
| AC-15 | ✅ met | `tests/test_cli.py` `Lifecycle::test_strict_requires_codeowners`; `tests/test_setup.py:202` |

## Security
- **[MEDIUM] setup and init write outside any repo** (`machine.py:47-51`, `setup.py:252`, `:324-336`).
  - Fix: refuse when `git rev-parse --show-toplevel` fails, when the root is `$HOME`, `~/.claude` or the plugin, or
    when any target matches the toolchain paths. Add tests for each.
- **[LOW] Preflight runs `git`/`gh`/`claude` from PATH** (`setup.py:23-33`). An agent-planted `.venv/bin/gh` runs when
  the human runs setup, with the human's terminal on stdin.
  - Fix: use `machine.GIT`; skip PATH directories inside the repo for `gh`/`claude`; use `stdin=DEVNULL`.
- **[LOW] Interpreter env-stripping.** It lets the agent run setup as a "human" and change the working-tree config.
  This residual risk is already documented (`docs/architecture.md:38`, `:51`), and CI reads the base ref.
  - Fix: state it in the skill and the spec.
- **[LOW] Case-sensitive `no-touch-required`** in the `"sk"` audit (approvals.py). OpenSSH may match the option
  case-insensitively; the reviewer didn't confirm this.
  - Fix: lowercase the option names before comparing.
  - Note: `allowed-signers` is human-owned, read from the base ref, and under CODEOWNERS.

Spec flags:

| Flag | Mitigated? |
|---|---|
| Solo approvals are unsigned | **yes**, stated |
| Setup writing `.claude/settings.json` | **yes in the repo; no for `$HOME`** (MEDIUM) |
| Profile changes through setup | **yes**, within the documented env-marker residual risk |
| `gh auth status` / `claude --version` | **yes** (binary resolution: LOW) |
| No sandbox; setup writes only in its repo | **partially**: a non-repo directory becomes the root (MEDIUM) |
| `sdlc feedback` | **yes** |

## Plan conformance
- S1–S15 are ticked and each maps to a commit.
- The fix rounds (F1–F6, G1–G2, H1–H4) and every human decision are in the Deviation log. The H1–H4 entries match
  their diffs.
- **Inaccurate claims:**
  - The README, the setup skill and the quick reference claim a solo setup through the skill (MEDIUM, docs).
  - The CHANGELOG says "nothing suggests `--force`", but `init` still tells the *human* to run `sdlc init --force`
    for owned files. Also, its "re-run with --stack" hint doesn't work on a rerun.

## Test-first evidence
- Every commit has `Red:` and `Green:` lines.
- Red on the parent, confirmed:
  - H1, H2, H3 and H4 (by both the verifier and the code reviewer)
  - S15, F2–F6 and G2 (verifier)
- **Gaps:**
  - AC-8's FAIL-review case
  - JSON that parses but isn't an object
  - an agent rerun
  - setup in a non-repo directory
  - the docs' skill route versus the profile result
  - the `/tmp` side-directory leak (a known issue)

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | AC-8 partial (the FAIL-review case) |
| Security | 25 | 20 | 1 MEDIUM (writes outside a repo), 3 LOW |
| Test quality & test-first | 20 | 18 | red confirmed for every fix; the gaps above |
| Plan conformance | 10 | 9 | docs claims after H2; the `--force` line |
| Maintainability | 5 | 4 | some error paths still end in tracebacks |
| **Total** | 100 | **89** | **CHANGES_REQUESTED** (AC-8 partial; two MEDIUMs open) |

### Fixes requested for a PASS
- **AC-8:** a playbook test where a FAIL `review.md` keeps the intent at state 5, in each profile.
- **MEDIUM, docs:** say that a profile other than team is applied by the human's own terminal run. Fix the README
  recipe, path A, the quick reference, the skill's step 1 and the agent-run human step. Add a docs test.
- **MEDIUM, security:** setup and init refuse a root that isn't a git work tree, and `$HOME`, `~/.claude` and the
  plugin directory. With tests.

### LOW and MINOR (the human decides: fix now or alpha.3 known issues)
- **Setup:**
  - JSON that isn't an object gets a `✗` row instead of a traceback.
  - An agent rerun says "nothing for the agent to write".
  - Write errors are caught, listing what was written.
  - Preflight's binary resolution, with `stdin=DEVNULL`.
- **Approvals:** compare `no-touch-required` case-insensitively.
- **Docs:**
  - The CHANGELOG `--force` wording and the `init --stack` hint.
  - The TROUBLESHOOTING "Setup says ✗" list.
  - The env-marker residual risk in the skill and the spec.
