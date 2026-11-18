---
id: 0009
title: Stack auto-detection for the Makefile contract
status: Approved
spec: ./spec.md
created: 2026-11-18
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-18T10:05:17Z
approved-via: cli
approved-sha256: ed2ea08812bf3c1d40818f969d7b0c47636bfe8507b30091e3dc199465e98de9
---

# Plan: Stack auto-detection for the Makefile contract

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
Bottom-up, so each layer is tested before anything calls it:
1. The pure detection module, then its safety cases.
2. The recipe plumbing in `cli` (`wire` takes a dict and validates it).
3. The setup and init surfaces.
4. The typed command.
5. Lifecycle (install-state and `expected`).
6. Docs and the regenerated scaffold history.

Existing code to reuse:
- `cli.wire` (`lib/sdlc_engine/cli.py:398`): its stub regex stays, so wiring a preset produces the same bytes as
  today (the `Makefile+<stack>` hashes in `defaults/scaffold-history.json` stay valid).
- `cli._wire_stack` (`cli.py:421`), `cli.symlink_on_path`, `cli.TEMPLATES`, `cli.STACKS` (`cli.py:435`).
- `setup.OPTIONS`/`parse` (`setup.py:407`), `setup.main`/`apply` (`setup.py:449`, `:559`), `scaffold_first`
  (`setup.py:769`), `set_first_profile` (`setup.py:795`), `setup.printable` (`setup.py:969`).
- `lifecycle.record` (`lifecycle.py:56`) and `expected` (`:212`), with its callers at `:252`, `:545`,
  `:655-668` and `:723`.
- `scripts/scaffold-history.py:31-45`, which wires each release's preset *text* read from git.
- Test helpers: `tests/helpers.py::RepoCase` (`run_sdlc`, `hook`) and `tests/test_cli.py::SetupCommand.prompt`
  (the typed command through the prompt hook).

`cli.STACKS` stays `("python", "node", "go")`, the presets that history hashes. The options use a new
`stacks.CHOICES`.

## Steps
- [x] **S1**: Create the detection module with its result type, the family choice and the reading rules.
  - Files: `lib/sdlc_engine/stacks.py` (create): `Detection` namedtuple, `KINDS`, `CHOICES`, `detect(root, force)`,
    `_read(root, name)` (top-level regular file, not via a link, ≤ 1 MiB, UTF-8 replace), `_json`/`_xml` helpers that
    return None on a parse error, and `_family(root)`. Plus `MARKERS`, the explicit list of the only files detection
    may open.
  - Test first: new `tests/test_stacks.py::Family`. Fails on import:
    - `pom.xml`+`go.mod` → `kind None`, with a note naming `java`, `go` and `--stack`;
    - a symlinked `package.json`, a 2 MiB `package.json`, invalid JSON, invalid XML → not used, no exception;
    - `test_reads_only_markers` patches `Path.read_bytes`/`open` and asserts that every opened path is in `MARKERS`
      and at the top (no `.env`, `.npmrc`, `settings.xml`).
  - Covers: AC-10, AC-11
- [x] **S2**: Detect the Node family (node, react, angular) from the repo's own scripts.
  - Files: `lib/sdlc_engine/stacks.py` (modify): `_node_family(root)`:
    - the package manager from the lockfile;
    - the per-target script order;
    - the `SCRIPT_NAME` regex, skipping npm's placeholder;
    - the `typecheck` fallback when `tsconfig.json` exists;
    - the watch-mode rules (`react-scripts test` → `CI=true`; `ng test` → `-- --watch=false`, plus
      `--browsers=ChromeHeadless` with a Karma builder in `angular.json`).
  - Test first: `tests/test_stacks.py::Node`:
    - pnpm with four scripts (AC-4);
    - CRA with yarn, and Vite with `test:ci` (AC-5);
    - Angular with Karma and without (AC-6);
    - the `tsconfig` fallback and the npm placeholder (AC-7);
    - names `lint;rm -rf ~`, `$(x)`, `a\nb`, `-x` never appear, and no body substring appears in any recipe (AC-8).
  - Covers: AC-4, AC-5, AC-6, AC-7, AC-8
- [x] **S3**: Detect Java (Maven and Gradle, Spring Boot label, wrapper, Checkstyle/Spotless only when configured),
  Python and Go.
  - Files: `lib/sdlc_engine/stacks.py` (modify):
    - `_java(root)`: `pom.xml` through `xml.etree`, Gradle files by text match; the wrapper is used when it is an
      executable regular file;
    - `_preset(name)`: python and go from `templates/stacks/*.recipes`.
  - Test first: `tests/test_stacks.py::Java`:
    - Spring Boot Maven with `mvnw` (AC-1);
    - without `mvnw`, with Checkstyle and Spotless (AC-2);
    - Gradle kts with `gradlew` (AC-3);
    - a non-executable `mvnw` falls back to `mvn`.

    `tests/test_stacks.py::Presets`: pyproject only, go.mod only (AC-9).
  - Covers: AC-1, AC-2, AC-3, AC-9
- [x] **S4**: Make `cli.wire` take a recipes dict, validate every value, and add `parse_recipes`/`preset_recipes`.
  - Files:
    - `lib/sdlc_engine/cli.py` (modify): `wire(src, recipes)`, `parse_recipes(text)`, `preset_recipes(stack)`,
      `_safe_recipe(cmd)` (one line, no control characters, no leading tab, `-` or `@`; `ValueError` otherwise).
      `_wire_stack` becomes `_wire(root, recipes)`.
    - `lib/sdlc_engine/lifecycle.py:216` and `scripts/scaffold-history.py:37` move to
      `wire(data, parse_recipes(text))` (modify).
  - Test first: `tests/test_cli.py::Init::test_wire_refuses_unsafe_recipes` (a multi-line, tab-led or `@`-led value
    raises) and `test_preset_wiring_bytes_unchanged`. The second wires each preset through the new API and compares
    its normalized hash with `defaults/scaffold-history.json`'s current `Makefile+<stack>`. It fails before the
    change because `wire` takes no dict.
  - Covers: AC-19 (the refusal), AC-20 (preset bytes unchanged)
- [x] **S5**: Wire detection into `sdlc setup` and `sdlc init`: the `--stack` choices, the default `auto`, the
  Stack block, and the suggestion for an existing Makefile.
  - Files:
    - `lib/sdlc_engine/setup.py` (modify):
      - `OPTIONS["--stack"] = stacks.CHOICES` and the `parse` message;
      - `main` computes the detection once and prints `stack_block(det)` before the confirmation (also in
        `--dry-run`);
      - `apply` wires the created Makefile with `det.recipes` (none for `--stack none`), records `stack` and
        `recipes`, and prints the suggestion when `Makefile` was kept.
    - `lib/sdlc_engine/cli.py` (modify): `cmd_init` gets the same option, block, suggestion and record, and its
      "Next" text loses "copy the recipes"; the doctor's Makefile row (`cli.py:836`) adds the `detected …`
      suggestion.
  - Test first: `tests/test_setup.py::Stack`:
    - a fresh repo with a Spring Boot `pom.xml` and `setup --yes` gives a wired Makefile, and install-state has
      `stack` and `recipes` (AC-12);
    - `--dry-run` prints the block and writes nothing (AC-13);
    - an existing Makefile is byte-identical, with the suggestion in the output and in `doctor` (AC-14);
    - `--stack none`, `--stack react` with no package.json, and `--stack rust` refused by both setup and init
      (AC-17).
  - Covers: AC-12, AC-13, AC-14, AC-17
- [x] **S6**: Wire detection into the typed `/zouj-ai-sdlc:setup <profile>` in a fresh repo and add the escaped
  `Makefile:` block to its reply.
  - Files: `lib/sdlc_engine/setup.py` (modify):
    - `scaffold_first` detects after its existing checks, wires the created Makefile, records `stack`/`recipes`,
      and attaches the detection to the `KeptList` it returns (`.detection`);
    - `set_first_profile` adds `makefile_block(det)`, every line through `printable`.

    Nothing else in either function changes.
  - Test first: `tests/test_cli.py::SetupCommand`:
    - `test_typed_setup_wires_detected_stack`: a fresh repo with a React CRA `package.json` and the prompt
      `/zouj-ai-sdlc:setup solo` gives the AC-5 recipes in the Makefile and `Makefile: detected` in the reply; HEAD
      is the single-file `Setup Profile` commit, and `Makefile` is untracked (AC-15);
    - `test_typed_setup_escapes_detected_text`: a script name and an `angular.json` value carrying `\x1b` → no raw
      control character in the reply or `systemMessage` (AC-16).
  - Covers: AC-15, AC-16
- [x] **S7**: Make the lifecycle honour recorded recipes.
  - Files: `lib/sdlc_engine/lifecycle.py` (modify):
    - `record(..., recipes=None)` stores `"recipes"`;
    - `expected(rel, ref, stack=None, recipes=None)` wires the recorded recipes when present; an invalid one
      (`ValueError`) means no wiring, so the file stays `modified`;
    - every caller passes `st.get("recipes")`.
  - Test first: `tests/test_lifecycle.py::Detected`:
    - after a detection setup, `list-installed` says `current`, and `upgrade --dry-run`/`repair --dry-run` plan
      nothing for the Makefile; a deleted Makefile is restored with the recorded recipes (AC-18);
    - install-state edited (by the test, as a human) to hold a two-line recipe: `upgrade --yes` leaves the Makefile
      as it is, reported as modified (AC-19);
    - a beta.1-style state with `stack: python` and no `recipes` → today's result (AC-20).
  - Covers: AC-18, AC-19, AC-20
- [x] **S8**: Add Java's test layout to the `/fix` test lock.
  - Files: `defaults/test-paths` (modify: `src/test/*`)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_test_lock_covers_java`: with the test lock on, Edit of
    `src/test/java/AppTest.java` → exit 2. Fails today.
  - Covers: AC-21
- [x] **S9**: Update the docs and skills, renumber the roadmap labels, and regenerate the scaffold history.
  - Files (modify):
    - `templates/scaffold/Makefile` (the header: detection, `--stack auto|none|…`);
    - `skills/setup/SKILL.md`, `skills/init/SKILL.md` (`argument-hint`), `skills/onboard/SKILL.md`;
    - `README.md` (the install note), `COMMANDS-QUICK-REF.md`, `TROUBLESHOOTING.md` ("the wrong stack was
      detected" / "make check hangs");
    - `CHANGELOG.md` `[Unreleased]`, `docs/architecture.md` (the module list; the setup threat-model row: detection
      reads only), `docs/roadmap.md` (no 0009/0010 numbers);
    - `defaults/scaffold-history.json`, via `python3 scripts/scaffold-history.py`.
  - Test first: `tests/test_cli.py::Docs::test_docs_name_stack_detection`:
    - the files above mention `--stack auto`;
    - TROUBLESHOOTING has the entry;
    - the init skill's hint lists the eight choices.

    `tests/test_rules.py::History::test_current_scaffold_in_history` fails once the Makefile template changes, until
    the history is regenerated.
  - Covers: AC-23
- [ ] **S10**: Prove the playbook is unchanged and run the full gate: `make check`, `make validate`, and the
  `profile-by-setup-command` eval.
  - Files: `tests/test_playbook.py` (modify): the walk also runs with `--stack auto` on a Node fixture and asserts
    the same gates, approvals, profile keys and CI files as with `--stack none`.
  - Test first: the new playbook case fails if detection touches anything but the Makefile, install-state and the
    output.
  - Covers: AC-22, AC-23

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The new `wire` changes the bytes of a preset-wired Makefile, so every beta.1 repo reads `stale` and `upgrade` rewrites it | medium | high | S4's hash test against the current `Makefile+<stack>` entries; same stub regex and replacement |
| Detection reads a secret-bearing file (`.npmrc`, `settings.xml`, `.env`) | low | high | An explicit `MARKERS` list; S1's test asserts every opened path |
| A repo-derived string breaks out of a recipe line (injection) or out of the hook reply (terminal escape) | low | high | Only names matching the regex; `_safe_recipe` in `wire`; `printable` on the reply; AC-8, AC-16, AC-19 |
| The typed command's reply grows long or changes its existing lines (evals and tests compare them) | medium | medium | The block is appended after the created-files list; existing `SetupCommand` tests and the eval run in S10 |
| A wired Angular/React test hangs the Stop hook on machines without Chrome | medium | medium | Headless only with Karma; TROUBLESHOOTING entry; `--stack none` opt-out |
| `scaffold-history.py` reads old releases' recipe *text*, and the API change breaks it | medium | medium | S4 moves it to `parse_recipes`; S9 regenerates and diffs the history (only the current release's entries may change) |
| PR #22 (docs) also edits README, CHANGELOG and roadmap | high | low | Merge main into this branch before S9 (never rebase: the approval commits are signed) |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_stacks.py::Java::test_spring_boot_maven_wrapper` | unit | the Spring Boot Maven label, wrapper recipes, no lint/format |
| AC-2 | `tests/test_stacks.py::Java::test_maven_checkstyle_spotless_no_wrapper` | unit | `mvn` fallback; lint/format only when configured |
| AC-3 | `tests/test_stacks.py::Java::test_gradle_kts_spring_boot` | unit | Gradle recipes and label |
| AC-4 | `tests/test_stacks.py::Node::test_pnpm_scripts` | unit | lockfile package manager, script mapping |
| AC-5 | `tests/test_stacks.py::Node::test_react_cra_and_vite` | unit | `CI=true` for CRA; `test:ci` preferred |
| AC-6 | `tests/test_stacks.py::Node::test_angular_karma_and_not` | unit | no watch; headless only with Karma |
| AC-7 | `tests/test_stacks.py::Node::test_tsc_fallback_and_npm_placeholder` | unit | the typecheck fallback; placeholder skipped |
| AC-8 | `tests/test_stacks.py::Node::test_unsafe_script_names` | unit | no unsafe name, no body in recipes |
| AC-9 | `tests/test_stacks.py::Presets::test_python_and_go` | unit | presets unchanged |
| AC-10 | `tests/test_stacks.py::Family::test_ambiguous_root` | unit | no guess; candidates named |
| AC-11 | `tests/test_stacks.py::Family::test_unreadable_and_linked_files`, `::test_reads_only_markers` | unit | links, size, parse errors; only marker files at the top |
| AC-12 | `tests/test_setup.py::Stack::test_auto_wires_created_makefile` | integration | the Makefile wired; install-state records stack and recipes |
| AC-13 | `tests/test_setup.py::Stack::test_dry_run_shows_block` | integration | the preview block; nothing written |
| AC-14 | `tests/test_setup.py::Stack::test_existing_makefile_untouched` | integration | byte-identical; suggestion in setup and doctor |
| AC-15 | `tests/test_cli.py::SetupCommand::test_typed_setup_wires_detected_stack` | hook | the typed command wires and reports; commit unchanged |
| AC-16 | `tests/test_cli.py::SetupCommand::test_typed_setup_escapes_detected_text` | hook | no raw control characters in the reply |
| AC-17 | `tests/test_setup.py::Stack::test_none_forced_and_unknown` | integration | `none`, a forced kind without files, an unknown value refused |
| AC-18 | `tests/test_lifecycle.py::Detected::test_current_and_repair` | integration | `current`; repair restores the recorded recipes |
| AC-19 | `tests/test_lifecycle.py::Detected::test_tampered_recipes_not_written`, `tests/test_cli.py::Init::test_wire_refuses_unsafe_recipes` | integration, unit | recipes re-validated on read |
| AC-20 | `tests/test_lifecycle.py::Detected::test_beta1_state_unchanged`, `tests/test_cli.py::Init::test_preset_wiring_bytes_unchanged` | integration, unit | backward compatibility |
| AC-21 | `tests/test_shell_hooks.py::ShellHooks::test_test_lock_covers_java` | hook | `src/test/` under the test lock |
| AC-22 | `tests/test_playbook.py::Playbook::test_detection_changes_only_the_makefile` | conformance | gates, approvals, profile and CI files unchanged |
| AC-23 | `tests/test_cli.py::Docs::test_docs_name_stack_detection`, `make check`, `make validate` | docs, gate | docs updated; the suite and the plugin manifest pass |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-11-18 | S5 | A forced `--stack python` or `--stack go` wires its preset with no marker file at the top (R-9 reads as "the forced kind's recipes still need the repo's own files") | Those presets read no repo file, and `--stack python\|go` always worked on any repo; existing tests and beta.1 users rely on it | S5 commit |
| 2026-11-18 | S6 | With no stack detected, the typed reply says to wire the stubs by hand (`sdlc doctor` lists them), not to run `sdlc setup --stack <name>` (R-12) | The Makefile already exists by then, and setup never changes an existing Makefile (R-11), so that advice would do nothing | S6 commit |
| 2026-11-18 | S9 | `Docs::test_changelog_has_the_release` (0008) allows an `unreleased` scaffold-history entry while the CHANGELOG's `[Unreleased]` section has entries; at a release it still requires none | The Makefile template's header changed after 0.2.0-beta.1 was tagged, so `scripts/scaffold-history.py` records the tree as `unreleased` (its documented behaviour); `test_current_scaffold_in_history` and `--check` still pin the file | S9 commit |
