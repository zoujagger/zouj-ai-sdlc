---
id: 0003
verdict: CHANGES_REQUESTED
commit: 8323aa8b85e0eb0a6eed4f4e75ffda9a1475aa4e
score: 84/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-04
---

# Review: Guided setup and first-run onboarding (roadmap phase 1), round 4

<!-- State 5 PRE-REVIEW, round 4 (after S15, the sandbox removal). Compiled only from the three fresh-context persona
     reports (base main @ 429614a, head 8323aa8). Rounds 1 (76), 2 (80) and 3 (78) are in git history. The human
     decides what happens next. -->

## Summary
The sandbox is gone, and so are all the round-3 findings.
- **Verifier:** VERIFIED. All 15 ACs pass and their 25 proof tests pass. S15's `NoSandbox` is red on its parent
  (reproduced by two reviewers).
- **Checks:** `make check` (139 tests), `make build` / `claude plugin validate .` (2 unrelated warnings: root
  CLAUDE.md, no icon) and `sdlc validate --all --ci --base main` all pass.
- **Confirmed sound:** the `"sk"` CI audit, the refusal of unknown key policies and unknown options, preflight never
  printing tokens, and `sdlc feedback` making no network calls.

One HIGH finding remains. It isn't new in S15: it is in the scaffold writer that F2 changed.
- **[HIGH] Scaffold writes follow symlinks.** `apply_init` checks `HUMAN_OWNED_RE` against the scaffold path, then
  writes through whatever is at that path.
  - **Under the agent:** `ln -s .claude/settings.json REVIEW.md && sdlc init --force` overwrites the project's
    settings with REVIEW.md text. That defeats F2. Reproduced by the security reviewer, and independently while
    compiling this review.
  - **Outside the repo:** the same route reaches a file outside the repo (`~/.gitconfig`). A symlinked directory
    (`scripts -> ~/.local/bin`) makes setup create a file on PATH.
  - **Limit:** the content is always the fixed scaffold text, so the agent can destroy or plant files but not run
    code it chose.

Verdict: **CHANGES_REQUESTED, 84/100.**
- Verifier: VERIFIED.
- Code reviewer: no BLOCKER/HIGH, 1 MEDIUM.
- Security reviewer: FAIL (1 HIGH, 2 LOW).

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:106`, `:20`; a manual dry run takes 1.26 s |
| AC-2 | ✅ met | `tests/test_setup.py:150` (status reads "No intents yet") |
| AC-3 | ✅ met | `tests/test_setup.py:178` |
| AC-4 | ⚠️ partial | `tests/test_setup.py:204` holds for existing files. A **missing** `config.json` in an initialized repo is created by the agent with the agent's profile (solo), not the scaffold's (MEDIUM below) |
| AC-5 | ✅ met | `tests/test_setup.py:272`, `:217`, `:245`, `:256` (values compared as parsed JSON, the plan's interpretation) |
| AC-6 | ✅ met | `tests/test_setup.py:120` |
| AC-7 | ✅ met | `tests/test_engine.py:513`, `:392`; `tests/test_playbook.py:83-86` |
| AC-8 | ⚠️ partial | `tests/test_playbook.py:123-129`; the FAIL-review case is a deferred alpha.3 known issue |
| AC-9 | ✅ met | `tests/test_cli.py:59` |
| AC-10 | ✅ met | `tests/test_setup.py:297`, `:309`; red on the parent; no sandbox code, template or offer left |
| AC-11 | ✅ met | `tests/test_setup.py:72` |
| AC-12 | ✅ met | `tests/test_shell_hooks.py:270`, `:255` |
| AC-13 | ✅ met | `tests/test_setup.py:323` |
| AC-14 | ✅ met | `tests/test_shell_hooks.py:302`; `make build` |
| AC-15 | ✅ met | `tests/test_cli.py:153`, `tests/test_setup.py:167` |

## Security
- **[HIGH] Scaffold writes follow symlinks** (`lib/sdlc_engine/cli.py:320-337` `apply_init`: `shutil.copy2` and the
  `.gitignore` write; `setup.py:318` the config write; `setup.py:328` the owned-file writes).
  - Fix:
    - Refuse to write when the destination, or any parent up to the repo root, is a symlink, or when it resolves
      outside the root.
    - Apply `HUMAN_OWNED_RE` to the resolved relative path.
    - Create files with `O_CREAT|O_EXCL|O_NOFOLLOW`; for `--force`, unlink and recreate.
    - Add tests for a symlinked file, a symlinked directory and a dangling link.
- **[MEDIUM] The agent can write a solo `config.json` into an initialized repo that has none** (`setup.py:313-318`,
  `:181-184`).
  - Such a repo runs on the team defaults, and `sdlc init` run by the agent would write the scaffold (team) config.
    Setup writes `PROFILE_CONFIG[profile]` instead, so R-4 ("only what init writes") is broken.
  - Local only: CI reads the base ref's config.
  - Fix: under the agent, a new config gets the scaffold default (team). Any other profile is printed as a human
    step. Add an `Owned::` test.
- **[LOW]**
  - `--stack` accepts any path (`--stack /tmp/x/evil` reads `/tmp/x/evil.recipes` into a new Makefile). Allow only
    `python`, `node` or `go`.
  - The MEDIUM above, seen from a fresh repo: there the agent's `--profile solo --yes` is the only consent. Same fix.

Spec flags:

| Flag | Mitigated? |
|---|---|
| Solo approvals are unsigned | **yes**, stated |
| Setup writing `.claude/settings.json` | **partially**: setup itself merges only the pinned marketplace keys and never writes it under the agent, but `init --force` through a symlink overwrites it (HIGH) |
| Profile changes through setup | **yes for an existing config; no for a missing one** (MEDIUM) |
| `gh auth status` / `claude --version` | **yes** |
| No sandbox; setup writes only in its repo | **partially**: the sandbox is gone and unknown options are refused, but symlinks lead outside the repo (HIGH) |
| `sdlc feedback` | **yes** |

## Plan conformance
- S1–S15 are all ticked, and each matches a commit. The S15 diff matches the plan, and its deviation entry is
  accurate.
- The human decisions are logged: the sandbox removal, the unapproved deferral (380ac27), and the re-approvals
  (1f5c938, 73f7add, 68bedf9).
- **Inaccurate claims:**
  - The CHANGELOG says "nothing suggests `--force` any more", but `templates/scaffold/Makefile:7` and `cli.py:360`
    still do.
  - The roadmap's Phase 1 lists a scope choice and an init confirmation that didn't ship.

## Test-first evidence
- Every step commit (S1–S15) and every fix commit (F1–F6, G1–G2) has `Red:` and `Green:` lines.
- S12 is a logged pin with a mutation check.
- Red on the parent, confirmed: S15 (two reviewers), plus S3, S4, S6, S8, S10, S13, S14, F2 and F3 (verifier spot
  checks).
- **Gaps:**
  - no test for symlinked scaffold destinations or for a missing config under the agent
  - the suite leaks side directories into `/tmp` (a known issue)
  - `ruff` and `shellcheck` aren't installed locally, so `make lint` skipped them. CI runs them. A manual scan found
    no unused imports from S15.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 36 | AC-4 partial (missing config); AC-8 partial (deferred) |
| Security | 25 | 17 | 1 HIGH (symlinked writes), 1 MEDIUM (agent's solo config), 2 LOW |
| Test quality & test-first | 20 | 18 | red confirmed throughout; the new routes are untested; temp leaks |
| Plan conformance | 10 | 9 | the CHANGELOG `--force` claim; roadmap lines |
| Maintainability | 5 | 4 | two argument parsers that can disagree; `KeyError` on an unknown stored profile |
| **Total** | 100 | **84** | **CHANGES_REQUESTED** (a HIGH finding; AC-4 partial) |

### Fixes requested
- **HIGH:** no scaffold or setup write follows a symlink or leaves the repo, with tests.
- **MEDIUM:** under the agent, a new `config.json` gets the scaffold (team) values; any other profile is a human
  step. With a test.

### Minor and low (the human decides: fix now or alpha.3 known issues)
- **Setup:**
  - `--stack` accepts only `python`, `node` or `go`.
  - An unknown stored profile gives a `✗` row instead of a `KeyError` traceback, and doctor flags it.
  - Parse the arguments once.
- **Docs:**
  - The recipe uses `<plugin>/bin/sdlc` (or `/zouj-ai-sdlc:setup solo`) and adds "commit the scaffold".
  - The `--force` hints and the CHANGELOG claim agree.
  - The CHANGELOG headings, the `--profile=x` known issue and the release date are fixed.
  - The roadmap's Phase 1 lines match what shipped.
