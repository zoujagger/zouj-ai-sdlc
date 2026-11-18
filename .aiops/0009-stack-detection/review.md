---
id: 0009
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 5e671b46d34d2b1098024b97cba01298ced52e3a
score: 98/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-18
---

# Review: Stack auto-detection for the Makefile contract

<!-- State 5 PRE-REVIEW. Written by fresh-context reviewer personas that did not write the code. Four rounds; each
     persona got only the intent folder and the base branch `main`. -->

## Summary
**Final, round 4 at 5e671b4: PASS, 98/100.**
- **What changed.** Setup and init detect the stack at the repo top:
  - Java/Spring Boot (Maven, Gradle);
  - Node, React, Angular (package.json scripts through the lockfile's package manager);
  - Python and Go (the presets).

  A setup or init the human runs wires a Makefile it creates, or the untouched stub. Run by the agent, or as the
  typed `/zouj-ai-sdlc:setup`, they only list the commands and the human's terminal command, so no repo script runs
  in a hook before the human has read it.
- **The rounds.**
  - **Round 1 (74):** a lifecycle blocker and a security MEDIUM (the typed command auto-wired).
  - **Round 2 (88):** a MAJOR in Java marker choice and a security MEDIUM (the agent's init/setup auto-wired).
  - **Round 3 (88):** a MAJOR regression (an interactive profile was dropped) and a ReDoS LOW.
  - **Round 4:** a leftover quadratic pattern, fixed in 5e671b4 and confirmed.
- **The human decided twice** (2026-11-18) to tighten the design: the typed path is suggest-only, and only humans
  wire. AC-12 and AC-15 are amended in the Deviation log.
- **Results:**
  - `make check`: 513 tests OK, 3 skipped.
  - `make validate`: passed (ICON_MISSING only).
  - Eval `profile-by-setup-command` at 72ad55e: with the plugin 1.00, without 1.00, $0.86.

## Spec conformance
Verified in round 3 (all 23 ACs at ad0ab2b). The round-3 and round-4 fixes added tests and changed no AC's
behaviour.

| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_stacks.py::Java::test_spring_boot_maven_wrapper` |
| AC-2 | ✅ met | `tests/test_stacks.py::Java::test_maven_checkstyle_spotless_no_wrapper` |
| AC-3 | ✅ met | `tests/test_stacks.py::Java::test_gradle_kts_spring_boot` |
| AC-4 | ✅ met | `tests/test_stacks.py::Node::test_pnpm_scripts` |
| AC-5 | ✅ met | `tests/test_stacks.py::Node::test_react_cra_and_vite` |
| AC-6 | ✅ met | `tests/test_stacks.py::Node::test_angular_karma_and_not` |
| AC-7 | ✅ met | `tests/test_stacks.py::Node::test_tsc_fallback_and_npm_placeholder` |
| AC-8 | ✅ met | `tests/test_stacks.py::Node::test_unsafe_script_names` (names come only from `NODE_SCRIPTS`) |
| AC-9 | ✅ met | `tests/test_stacks.py::Presets::test_python_and_go` |
| AC-10 | ✅ met | `tests/test_stacks.py::Family::test_ambiguous_root` |
| AC-11 | ✅ met | `Family::test_unreadable_and_linked_files`, `::test_reads_only_markers`, `Robustness::*`, `Round2::test_broken_pom_next_to_a_valid_gradle_file`, `Round3::test_hostile_gradle_files_finish_fast` |
| AC-12 (amended) | ✅ met | human: `tests/test_setup.py::Stack::test_auto_wires_created_makefile`; agent: `Stack::test_agent_never_wires` (Deviation log r2) |
| AC-13 | ✅ met | `tests/test_setup.py::Stack::test_dry_run_shows_block` |
| AC-14 | ✅ met | `tests/test_setup.py::Stack::test_existing_makefile_untouched` (wording in setup and doctor) |
| AC-15 (amended) | ✅ met | `tests/test_cli.py::SetupCommand::test_typed_setup_suggests_detected_stack`, through `hooks/engine.sh` (Deviation log r1) |
| AC-16 | ✅ met | `SetupCommand::test_typed_setup_escapes_detected_text`, `::test_makefile_block_escapes` |
| AC-17 | ✅ met | `tests/test_setup.py::Stack::test_none_forced_and_unknown` |
| AC-18 | ✅ met | `tests/test_lifecycle.py::Detected::test_current_and_repair`, `::test_empty_recipes_stay_stubs`; `Stack::test_unwired_rewrite_drops_stale_recipes` |
| AC-19 | ✅ met | `Detected::test_tampered_recipes_not_written`, `tests/test_cli.py::Init::test_wire_refuses_unsafe_recipes`, `Robustness::test_emittable_grammar` |
| AC-20 | ✅ met | `Detected::test_beta1_state_unchanged`, `Init::test_preset_wiring_bytes_unchanged`, `Round2::test_every_shipped_preset_stays_emittable` |
| AC-21 | ✅ met | `tests/test_shell_hooks.py::ShellHooks::test_test_lock_covers_java` |
| AC-22 | ✅ met | `tests/test_playbook.py::Playbook::test_detection_changes_only_the_makefile` |
| AC-23 | ✅ met | `tests/test_cli.py::Docs::test_docs_name_stack_detection`; `make check` 513 OK; `make validate` passed |

## Security
None open.
- **Fixed across the rounds:**
  - typed-path auto-wiring (r1 MEDIUM);
  - the agent's init/setup auto-wiring (r2 MEDIUM);
  - RecursionError, check-then-open, and the loose recipe check (r1 LOWs);
  - DTD/ENTITY (hardening);
  - the hand-tuned config being rewritten (r2 LOW);
  - quadratic Gradle parsing (r3 LOW, completed in r4: about 0.1 s on 1 MiB hostile inputs).
- **Accepted residual, documented in `docs/architecture.md` and the Deviation log r3:** in a repo without
  `.aiops/`, the agent's env-stripped `sdlc init` wires as the human. The agent can already write a wired Makefile
  there. Extending G-ENV-02 to uninitialized repos belongs to intent 0006.

## Plan conformance
- S1–S10 are done.
- The Deviation log has 17 rows:
  - the S5, S6, S9 and S10 rows from execution;
  - rows r1–r4 from the review fixes, including the late-logged S1–S7 module-boundary changes and the r4
    correction of the r3 "linear" claim.
- Nothing out of scope shipped. The `setup` "profile from config" behaviour was added as a logged fix.

## Test-first evidence
- Red lines are in the commit bodies:
  - steps S1–S9 (S10 is a conformance guard, logged);
  - the fix commits 211506d (r1), ad0ab2b (r2), 72ad55e (r3) and 5e671b4 (r4).
- Tests and code share a commit, which REVIEW.md accepts.
- The r3 timing test missed the `id`+spaces vector; r4 added it.

## Backlog (not blocking)
- [NIT] `lib/sdlc_engine/stacks.py:328`: if `_java` ever runs with no regular Java marker (a file removed between
  `detect()`'s check and `_java`'s), its note reads "no Java build file can't be read". Branch on `present`.
- [NIT] An `id` split over lines (`id\n "checkstyle"`) in a Gradle file no longer marks Checkstyle as configured.
  Logged; rare.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 39 | every AC met as amended; the multi-line `id` narrowing is logged |
| Security | 25 | 25 | no open finding; one documented residual outside this intent's guards |
| Test quality & test-first | 20 | 19 | Red recorded throughout; the r3 timing test had missed a vector (fixed in r4) |
| Plan conformance | 10 | 10 | all deviations logged, incl. corrections |
| Maintainability | 5 | 5 | small module, one parser, linear scanner |
| **Total** | 100 | 98 | PASS: ≥ 80, no BLOCKER, no CRITICAL/HIGH, every AC met |
