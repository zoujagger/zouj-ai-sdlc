---
id: 0003
verdict: CHANGES_REQUESTED
commit: d988c41d3db2b0995b5f601426cc3b12411023e3
score: 76/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-03
---

# Review: Guided setup and first-run onboarding (roadmap phase 1), round 1

<!-- State 5 PRE-REVIEW. Compiled only from the three fresh-context persona reports (base main @ 429614a, head
     d988c41). The human decides what happens next. -->

## Summary
The feature works as specified, and every AC has a passing test.
- **Checks:** `make check` passes (133 tests), `claude plugin validate .` passes with the known warnings, and
  `validate --all --ci --base main` is clean. ruff and shellcheck aren't installed locally, so only `compileall` and
  `bash -n` ran. The hooks did not change in this diff.
- **Verifier:** VERIFIED. All 15 ACs pass.
  - It ran the main flows by hand: dry run, apply and rerun, the agent path with sha256-identical files, the
    sandbox, and feedback.
- **Code reviewer:**
  - Confirmed red on the parent commit for 5 sampled proof tests.
  - Found no unused imports.
  - The agent can't flip `CLAUDECODE` to get around R-4.
- **Security reviewer:** the R-4 path holds, and token handling is clean. Two attacks *around* it were reproduced:

- **[HIGH] A sandbox race commits a downgrade into the calling repo.** `sandbox()` checks the path once, then keeps
  writing through it. An agent loop that swaps the new directory for a symlink to the repo got `solo` merged into
  `.aiops/config.json` and `git add -A` committed on main as the human, on the first try.
- **[HIGH] The agent can run `sdlc init --force`.** It silently rewrites `.aiops/config.json`, turning strict into team
  and resetting `main_branch`. It also resets `allowed-signers`, `.claude/settings.json`, CODEOWNERS and workflows.
  It isn't human-only, and doctor's own fix text suggests it.

Verdict: **CHANGES_REQUESTED, 76/100.**
- Verifier: VERIFIED.
- Security reviewer: FAIL (2 HIGH, 2 MEDIUM).
- Code reviewer: 2 MAJOR.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:105` (`Plan::test_dry_run_writes_nothing`), `:19`. The plan list leaves out `.gitignore` (MINOR) |
| AC-2 | ✅ met | `tests/test_setup.py:149` (`Apply::test_fresh_repo_each_profile`), including the read-only lock through the real pre-edit hook |
| AC-3 | ✅ met | `tests/test_setup.py:177` |
| AC-4 | ✅ met | `tests/test_setup.py:203`: byte-identical under `CLAUDECODE=1`. Bypassed from the side by `init --force` and the sandbox race (Security) |
| AC-5 | ⚠️ partial | `tests/test_setup.py:216`. Keys and values are right, but the diff is printed only *after* the `[y/N]` (and never in `--dry-run`), so the human confirms without seeing it (R-4: "shown as a diff and confirmed") |
| AC-6 | ✅ met | `tests/test_setup.py:119` |
| AC-7 | ⚠️ partial | `tests/test_engine.py:489` (all three key cases through `signing_problem`, doctor refuses `"bogus"`). Doctor refusing a passphrase key under `"sk"` isn't tested, and CI verification doesn't enforce `sk` (Security MEDIUM) |
| AC-8 | ⚠️ partial | `tests/test_playbook.py:77-130`, a real walk in each profile (a pin with a mutation check). "State 6 requires a PASS review" is only tested positively |
| AC-9 | ✅ met | `tests/test_cli.py:33` |
| AC-10 | ⚠️ partial | `tests/test_setup.py:239` (all listed checks). The TOCTOU race is not covered (Security HIGH) |
| AC-11 | ✅ met | `tests/test_setup.py:71` |
| AC-12 | ✅ met | `tests/test_shell_hooks.py:255`, `:270` |
| AC-13 | ✅ met | `tests/test_setup.py:275` |
| AC-14 | ✅ met | `tests/test_shell_hooks.py:302`; `make build` |
| AC-15 | ✅ met | `tests/test_cli.py:120`, `tests/test_setup.py:166` |

## Security
- **[HIGH] Sandbox TOCTOU** (`setup.py` `sandbox()`).
  - Fix:
    - Build the sandbox in `tempfile.mkdtemp()` and `os.rename` it onto a missing or empty target.
    - Before the commit, check `git rev-parse --show-toplevel` equals the sandbox, and commit an explicit file list.
    - Add a test that swaps in a symlink mid-run.
- **[HIGH] Agent-run `sdlc init --force`** (`cli.cmd_init`/`apply_init`).
  - Fix:
    - Under the agent, `--force` skips human-owned paths (`.aiops/config*`, `.claude/`, CODEOWNERS,
      `.github/workflows/`) and prints them as human steps.
    - Or refuse `--force` under the agent and block it in pre-bash.
    - Doctor's fix must not suggest `--force`.
- **[MEDIUM] `"sk"` is enforced only at signing time.** CI accepts a non-`sk` signature under strict.
  - Fix: when the base policy is `"sk"`, the verifier requires an `sk-` signer key type, and doctor flags non-`sk`
    allowed-signers entries.
- **[MEDIUM] The marketplace snippet is unpinned.**
  - Fix: pin a `ref` to the release tag (filled in at init, like `ZOUJ_SDLC_REF`).
  - Document that enabling the plugin trusts that repo at that ref, and that the hooks run as the user.
- **[LOW]**
  - Inventory checks only that the marketplace keys exist, not their values (a fork counts as "✓").
  - Preflight runs `git`, `gh` and `claude` through PATH. Use `GIT`, and `stdin=DEVNULL`.

Spec flags:

| Flag | Mitigated? |
|---|---|
| Solo approvals are unsigned | **partially**: stated in the gates text and the README; the sandbox race can commit a solo downgrade |
| Setup writing `.claude/settings.json` | **yes for setup**, **no overall** (`init --force`, unpinned marketplace) |
| Profile changes through setup | **setup path yes**, **no overall** (`init --force`, the sandbox race) |
| `gh auth status` / `claude --version` | **yes** |
| Sandbox path | **no**: TOCTOU |

## Plan conformance
- S1–S14 are ticked, and the commits map one-to-one to the steps. The S7, S9, S12 and S13 deviations are logged.
- **Unlogged (MINOR):**
  - `init_actions(root, force)`, where the plan says `(root, stack)`.
  - The sandbox app is `greet.py`, where the plan says `app.py`.
  - The `out()` stream change.
  - An extra `Applied` section, and the "Already set up" path printing no `Doctor` section.
- Nothing out of scope ships.

## Test-first evidence
- Every step commit carries `Red:`/`Green:`, and the test count climbs from 116 to 133. S12 is a declared pin backed by
  a mutation check.
- The code reviewer reproduced red on the parent commit for d621759, b761455, fb132a2, 4bb54c0 and 467918b.
- **Not covered:**
  - the confirm order (AC-5)
  - doctor under `"sk"` with a passphrase key (AC-7)
  - a FAIL or missing review staying at state 5 (AC-8)
  - an invalid-JSON config or settings file
  - the sandbox race

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 33 | AC-5, AC-7, AC-8 and AC-10 partial |
| Security | 25 | 13 | 2 HIGH (sandbox race, agent `init --force`), 2 MEDIUM, 2 LOW |
| Test quality & test-first | 20 | 17 | red confirmed; the gaps listed above |
| Plan conformance | 10 | 9 | small unlogged deviations |
| Maintainability | 5 | 4 | loose argument parsing |
| **Total** | 100 | **76** | **CHANGES_REQUESTED**: two HIGH, below 80 |

### Fixes requested
1. **HIGH:**
   - A race-free sandbox: temp dir plus rename, a toplevel check, an explicit commit list, and a race test.
   - Agent-safe `init --force`: skip human-owned paths under the agent, and doctor never suggests `--force`.
2. **MAJOR:**
   - Show the human-owned diffs in the Plan (dry run included) *before* the confirmation, with a test.
   - Setup on an invalid-JSON `config.json`/`settings.json` shows ✗/! and never claims "Already set up".
3. **MEDIUM:**
   - `"sk"` enforced at CI verification.
   - Pin the marketplace `ref`, and document the trust model.
4. **MINOR/LOW:**
   - Usability:
     - the stack after setup (doctor's ✗ Makefile, with no safe fix)
     - the sandbox outside a repo
     - `.gitignore` missing from the plan
   - Checks:
     - marketplace values
     - a doctor profile row that contradicts the settings
     - signing steps for the *requested* profile
   - Engine:
     - argument parsing (`--profile=`, `--sandbox --yes`, `--stack` in dry runs)
     - preflight's PATH tools
     - feedback path reduction
   - Docs and tests:
     - doc drift ("final gate", the README command and config lists)
     - an AC-8 FAIL-review test
     - an AC-7 doctor `sk` test
   - Process: the unlogged deviations.
