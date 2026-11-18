---
id: 0009
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 211506d2d8ca9bbdba413e26dc69d00948659f09
score: 88/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-18
---

# Review: Stack auto-detection for the Makefile contract

<!-- State 5 PRE-REVIEW. Written by fresh-context reviewer personas that did not write the code. Round 1, at
     af7704c. Each persona got only the intent folder and the base branch `main`. -->

## Summary
**Round 2, at 211506d: CHANGES_REQUESTED (88).** The code reviewer and the security reviewer reported; the
verifier was stopped before it reported, because round 3 re-verifies.
- **Fixed from round 1:** the blocker, the typed path, every LOW, and the test debt.
- **Still open:**
  - **[MAJOR] A broken `pom.xml` next to a valid `build.gradle` still blocks detection.** `_java` takes the
    `pom.xml` branch.
  - **[MEDIUM, security] The agent's own `sdlc init` / `sdlc setup --yes` still wire a new Makefile**, so the Stop
    hook runs repo scripts before review (reproduced). The human chose (2026-11-18) that only a human-run
    setup/init wires, which amends AC-12.
  - **[LOW, security]** The wiring command, run with no `--profile`, re-applies the profile's keys to a hand-tuned
    config.
  - **Minors:**
    - the Gradle comment stripper eats string contents (`"**/*.gen.java"`);
    - `emittable` isn't keyed by target, allows `CI=true` anywhere, and accepts only the running plugin's presets;
    - the profile-from-config rule applies with a tty too, unlike its log entry;
    - stale docs ("never changes an existing Makefile", init "wires the stub");
    - the architecture residual overstates the guarantee;
    - doctor's hint under the agent;
    - `_stub_wirable` evaluated mid-apply.
- **Scores:** spec 36/40, security 21/25, tests 18/20, plan 9/10, maintainability 4/5.

Round 1, at af7704c.

**The verdict is CHANGES_REQUESTED**, for two findings:
- **A blocker in the lifecycle.** An empty recorded recipe set makes `upgrade` write the node preset into a Makefile
  that setup had left unwired.
- **A MEDIUM in security.** On the typed `/zouj-ai-sdlc:setup` path, the auto-wired Makefile runs the repo's own
  commands in the Stop hook at the end of that same turn, before the human has reviewed it. The spec's residual
  claims the human reviews first.

**What holds:**
- Every AC has a passing test, three of them weaker than the AC's wording.
- `make check` passes: 485 tests, 3 skipped.
- `make validate` passes; its only warning is ICON_MISSING.
- No injection or gate bypass was found.

**The human chose** (2026-11-18) to make the typed path suggest-only. The typed command lists the detected recipes,
and `sdlc setup --stack auto` wires the untouched stub Makefile.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_stacks.py::Java::test_spring_boot_maven_wrapper` |
| AC-2 | ✅ met | `tests/test_stacks.py::Java::test_maven_checkstyle_spotless_no_wrapper` |
| AC-3 | ✅ met | `tests/test_stacks.py::Java::test_gradle_kts_spring_boot` |
| AC-4 | ✅ met | `tests/test_stacks.py::Node::test_pnpm_scripts` |
| AC-5 | ✅ met | `tests/test_stacks.py::Node::test_react_cra_and_vite` |
| AC-6 | ✅ met | `tests/test_stacks.py::Node::test_angular_karma_and_not` |
| AC-7 | ✅ met | `tests/test_stacks.py::Node::test_tsc_fallback_and_npm_placeholder` |
| AC-8 | ✅ met | `tests/test_stacks.py::Node::test_unsafe_script_names` (names come from constants; `SCRIPT_NAME` is dead) |
| AC-9 | ✅ met | `tests/test_stacks.py::Presets::test_python_and_go` |
| AC-10 | ✅ met | `tests/test_stacks.py::Family::test_ambiguous_root` |
| AC-11 | ⚠️ partial | `Family::test_unreadable_and_linked_files`, `::test_reads_only_markers`. Deeply nested JSON raises `RecursionError` (`stacks.py:73`) |
| AC-12 | ⚠️ partial | `tests/test_setup.py::Stack::test_auto_wires_created_makefile` runs as the human, not the agent |
| AC-13 | ✅ met | `tests/test_setup.py::Stack::test_dry_run_shows_block` |
| AC-14 | ⚠️ partial | `Stack::test_existing_makefile_untouched` doesn't check R-11's "copy what you want" wording |
| AC-15 | ⚠️ partial | `SetupCommand::test_typed_setup_wires_detected_stack` drives `sdlc hook prompt`, not `hooks/engine.sh` |
| AC-16 | ✅ met | `SetupCommand::test_typed_setup_escapes_detected_text` (no surviving value exercises `printable`) |
| AC-17 | ✅ met | `tests/test_setup.py::Stack::test_none_forced_and_unknown` |
| AC-18 | ❌ not met | `Detected::test_current_and_repair` passes, but recorded `recipes: {}` makes `expected()` wire the preset (`lifecycle.py:218`) |
| AC-19 | ✅ met | `Detected::test_tampered_recipes_not_written`, `Init::test_wire_refuses_unsafe_recipes` |
| AC-20 | ✅ met | `Detected::test_beta1_state_unchanged`, `Init::test_preset_wiring_bytes_unchanged` |
| AC-21 | ✅ met | `tests/test_shell_hooks.py::ShellHooks::test_test_lock_covers_java` |
| AC-22 | ✅ met | `tests/test_playbook.py::Playbook::test_detection_changes_only_the_makefile` |
| AC-23 | ✅ met | `Docs::test_docs_name_stack_detection`; `make check` 485 OK; `make validate` passed |

## Security
- **[MEDIUM] `lib/sdlc_engine/setup.py:800-806`: the typed command auto-wires, so the Stop hook runs repo code
  before review.**
  - Exploit path: in an untrusted clone, `/zouj-ai-sdlc:setup solo` writes `npm run lint` / `./gradlew` /
    `./mvnw`. The Stop hook runs `make check` at the end of the turn, and so runs the repo's script bodies and
    build scripts. This happens outside Claude Code's permission prompts and before the "uncommitted for review"
    Makefile is read.
  - Fix (the human's choice): suggest-only on the typed path.
- **[LOW] `stacks.py:73-76`: `RecursionError` from deeply nested JSON escapes detection.**
  - Effect: `sdlc init` has already written the scaffold when it crashes, so it skips `lifecycle.record`. Setup
    and doctor crash.
  - Fix: catch `RecursionError` in `_json`/`_xml`, and detect before `apply_init` in `cmd_init`.
- **[LOW] `stacks.py:56-63`: check-then-open.** A FIFO or symlink swapped in after `_regular()` can hang or redirect
  the read.
  - Fix: `os.open(O_NOFOLLOW|O_NONBLOCK)`, then `fstat` and require `S_ISREG`.
- **[LOW] `cli.py` `safe_recipe` / `lifecycle.recipes_ok`: the install-state path accepts `$(shell …)`, `;` and
  backticks.**
  - Exposure: only a tampered, protected install-state can carry them.
  - Fix: `recipes_ok` accepts only the recipe grammar the engine emits.
- **Hardening:** reject `<!DOCTYPE`/`<!ENTITY` before `xml.etree` (old expat doesn't limit entity expansion).

## Plan conformance
- S1–S10 are done, and main was merged before S9 as the Risks table planned.
- Four deviations are logged (S5, S6, S9, S10).
- These are **unlogged**:
  - `stacks.py` doesn't use `cli.symlink_on_path`/`cli.TEMPLATES` and has its own `preset()` parser;
  - `_safe_recipe(cmd)` became `safe_recipe(target, cmd)`;
  - `expected_for` and `recipes_ok` are new helpers;
  - the spec's `_wire_detected` became `_wire`.

## Test-first evidence
- Red is recorded in the commit bodies of S1 10ba2bb, S2 0c41d3b, S3 80e9932, S4 37fb3e3, S5 4d51367, S6 d7916c9,
  S7 ed3218b, S8 bef5f9d and S9 4ce48f7.
- S10 af7704c has no red: it is a conformance guard, green on its first run, and logged.
- Each step's test and code share one commit, which REVIEW.md accepts.

## Fixes requested
1. **BLOCKER:** `lifecycle.expected` uses `recipes is not None`. Add a test: a script-less `package.json`, then
   `upgrade --yes`, leaves the stubs.
2. **MEDIUM (the human's choice):** the typed command writes the stub Makefile and lists the detected recipes as a
   suggestion. `sdlc setup [--stack auto]` wires a Makefile that is still the plugin's untouched stub template.
   Correct the docs, and log the deviation from R-12/AC-15.
3. **Detection robustness:**
   - catch `RecursionError` in `_json`/`_xml`;
   - detect before `apply_init` in `cmd_init`;
   - read with `O_NOFOLLOW|O_NONBLOCK` and `S_ISREG`;
   - decode with `utf-8-sig` (BOM);
   - reject DTD/ENTITY in XML;
   - treat a marker that fails its parser as absent in the family choice, and name it in the note;
   - name an unreadable `angular.json` in the note.
4. **Recipe checks:** `recipes_ok` accepts only the grammar the engine emits.
5. **Code cleanup:**
   - one recipe parser;
   - drop the dead `SCRIPT_NAME`, and fix the architecture row's wording;
   - Gradle matching ignores comments and takes a one-line `plugins { … checkstyle }`;
   - Maven Checkstyle/Spotless only under `build/plugins`.
6. **Tests:**
   - `Detected` built on `RepoCase`, without the inherited-test hack and the output scraping;
   - an AC-12 run as the agent;
   - AC-14's suggestion wording;
   - AC-15 through `hooks/engine.sh`;
   - a `printable` unit test with a value that survives.
7. Log the unlogged deviations.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 33 | AC-18 broken for empty recipes; AC-11 RecursionError; R-2 "absent/noted" partial |
| Security | 25 | 21 | MEDIUM pre-review execution; three LOWs |
| Test quality & test-first | 20 | 17 | 9/10 steps red; empty-recipes and deep-JSON cases missing; fragile `Detected` |
| Plan conformance | 10 | 8 | four deviations unlogged |
| Maintainability | 5 | 4 | duplicated parser, dead regex |
| **Total** | 100 | 74 | CHANGES_REQUESTED: below 80, a BLOCKER, AC-18 not met |
