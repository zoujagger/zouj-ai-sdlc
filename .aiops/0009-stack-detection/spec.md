---
id: 0009
title: Stack auto-detection for the Makefile contract
status: Approved
risk: medium           # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: 2026-11-18
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-18T10:02:59Z
approved-via: cli
approved-sha256: a8a1803427db45332f38afd7df94f31e70c9b02e065ed3a5e339de0d1432bef8
---

# Spec: Stack auto-detection for the Makefile contract

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md (approved 2026-11-18), translated into
     engineering requirements and contracts. policy-security and policy-compliance applied. Risk is medium, not
     low: the typed setup command's path (prompt hook, ADR 0003) changes, and repo-derived text lands in a file
     `make` executes. -->

## Summary
When setup creates the scaffold Makefile, it detects the repo's stack from files at the repo top and wires the
contract targets (`format`, `lint`, `typecheck`, `test`, `build`) with the repo's own commands. It covers:
- Java/Spring Boot (Maven, Gradle);
- Node, React and Angular (package.json scripts through the lockfile's package manager);
- the existing Python and Go presets.

It works in `sdlc setup`, `sdlc init` and the human's typed `/zouj-ai-sdlc:setup <profile>`. The preview, `--dry-run`
and the typed command's reply show what was detected. An existing Makefile is never changed: the detection becomes a
suggestion. Install-state records the wired recipes, so `upgrade`/`repair` treat that Makefile as current. This
delivers the intent's desired outcome: a contract that tests something, with no flag and no hand-wiring, for the
stacks named. The gates, approvals, profiles and CI audit don't change.

The intent's open questions are settled here:
- **Java lint/format:** wired only when the build file configures Checkstyle/Spotless; otherwise the stubs stay
  (R-6).
- **Angular test:** headless only with a Karma builder (R-4).
- **The typed reply:** lists every wired command, as the approved intent's outcome says (R-12).
- **The roadmap's provisional 0009/0010 labels:** become unnumbered "next" items in this intent's docs step (R-16).

## Requirements
**Detection (`lib/sdlc_engine/stacks.py`, new, stdlib only)**
- **R-1 `detect(root, force=None)`.** Returns a `Detection(kind, label, recipes, evidence, note)`, or one with
  `kind=None` and a `note` saying why nothing was detected (no marker file, ambiguous, unreadable).
  - `recipes` is an ordered `{target: command}` over the five contract targets only.
  - `evidence` lists the repo-relative files read.
  - `force` (a kind name) skips the family choice but still reads the repo for scripts and wrappers.
- **R-2 Reading rules.**
  - Only regular files directly at the repo top are read, never through a symlink (`cli.symlink_on_path`), each at
    most 1 MiB.
  - Decoding is UTF-8 with `errors="replace"`.
  - A file that fails to parse (`json`, `xml.etree.ElementTree`) is treated as absent, and its name is noted in
    `note`.
  - No subprocess, no network, no write.
- **R-3 Family choice.**
  - Markers:
    - Java: `pom.xml`, `build.gradle`, `build.gradle.kts`;
    - Node family: `package.json`;
    - Python: `pyproject.toml`, `setup.cfg`, `setup.py`, `requirements.txt`;
    - Go: `go.mod`.
  - Exactly one family present → that family.
  - Two or more → `kind=None`, with `note` naming the candidates and `--stack <name>`.
  - Within the Node family: `angular.json` → `angular`; else a `react` key in `dependencies`/`devDependencies` →
    `react`; else `node`.
- **R-4 Node family recipes.**
  - Package manager from the lockfile: `pnpm-lock.yaml` → `pnpm`; `yarn.lock` → `yarn`; `bun.lockb`/`bun.lock` →
    `bun`; otherwise `npm`.
  - Each target takes the first script that exists:

    | Target | Scripts, in order | Fallback |
    |---|---|---|
    | `format` | `format`, `prettier` | none |
    | `lint` | `lint` | none |
    | `typecheck` | `typecheck`, `type-check`, `tsc` | `npx tsc --noEmit` when `tsconfig.json` exists |
    | `test` | `test:ci`, `test` | none |
    | `build` | `build` | none |
  - A recipe is `<pm> run <name>`.
  - Skipped scripts:
    - a name not matching `^[A-Za-z0-9][A-Za-z0-9:._-]{0,63}$`;
    - npm's placeholder (a body containing `no test specified`).
  - Watch mode, only when the chosen script is `test` and its body matches:
    - `react-scripts test`: the recipe becomes `CI=true <pm> run test`;
    - `ng test` (Angular): the recipe appends `-- --watch=false`, plus `--browsers=ChromeHeadless` when the
      `angular.json` test builder is Karma (`…:karma`).
  - The body is read only to choose. It is never copied.
- **R-5 Java recipes.**
  - Runner:
    - Maven: `./mvnw` when an executable regular `mvnw` is at the top, else `mvn`; always `-B -q`;
    - Gradle: `./gradlew` under the same rule, else `gradle`; always `-q`.
  - Targets:

    | Target | Maven | Gradle |
    |---|---|---|
    | `typecheck` | `compile` | `classes` |
    | `test` | `test` | `test` |
    | `build` | `package -DskipTests` | `assemble` |
  - Label: `Java · Spring Boot · Maven|Gradle` when the build file names `spring-boot-starter-parent`,
    `spring-boot-maven-plugin` or `org.springframework.boot`; else `Java · Maven|Gradle`.
- **R-6 Java lint/format.**
  - `lint` is wired only when the build file configures Checkstyle: `maven-checkstyle-plugin` →
    `checkstyle:check`; Gradle `checkstyle` plugin → `checkstyleMain`.
  - `format` is wired only when it configures Spotless: `spotless-maven-plugin` → `spotless:apply`; Gradle
    `com.diffplug.spotless` → `spotlessApply`.
  - Otherwise both keep their stubs. (The post-edit hook runs them after every edit; an unconfigured tool would fail
    every time.)
- **R-7 Python and Go.** The recipes of `templates/stacks/python.recipes` and `go.recipes`, unchanged. Labels:
  `Python`, `Go`.
- **R-8 Recipe safety.**
  - Every recipe is one line, with no control characters and not starting with a tab, `-` or `@`.
  - Recipes come only from fixed templates plus an R-4 script name.
  - `cli.wire` refuses any other value (`ValueError`), whatever its source (R-10), as a second line of defence.

**Wiring and options**
- **R-9 `--stack`.** `sdlc setup` and `sdlc init` take `--stack auto|none|python|node|go|java|react|angular`.
  - Omitted means `auto`.
  - `none` keeps every stub.
  - A named kind forces it (R-1 `force`). The forced kind's recipes still need the repo's own files: forcing `react`
    on a repo with no `package.json` wires nothing and says so.
  - `python|node|go` keep their meaning: `node` now reads the repo's scripts.
  - An unknown value is refused with the list, and nothing is written.
- **R-10 `cli.wire(src, recipes)`** takes a `{target: command}` dict. `cli.preset_recipes(stack)` parses a
  `templates/stacks/*.recipes` file into one, for the presets and `scripts/scaffold-history.py`. Only stubs (lines
  printing `not configured`) are replaced, as today.
- **R-11 Only a Makefile setup creates is wired.**
  - When the plan creates `Makefile`, the detection is applied right after it is written.
  - When `Makefile` already exists (kept), nothing in it changes. Setup's output and `sdlc doctor`'s
    "Makefile contract wired" row then show the detected recipes as a suggestion: "detected <label>: <target>:
    <command> …; copy what you want into your Makefile".
- **R-12 Typed setup command.**
  - In a fresh repo, `scaffold_first` applies `detect(root)` (`auto`) to the Makefile it creates.
  - The reply adds a block:
    ```
    Makefile: detected <label> (from <evidence>)
      lint: <command>
      typecheck: not configured
      …
    ```
    or `Makefile: no stack detected (<note>); wire it by hand or ask Claude to run sdlc setup --stack <name>`.
  - Every line is passed through `setup.printable`.
  - No other behaviour of the command changes: prompt matching, preconditions, missing files only, the single-file
    unsigned profile commit, the Makefile left uncommitted.
- **R-13 Preview.**
  - `sdlc setup` (also `--dry-run`) prints a `Stack` block before the confirmation: the label, the evidence, each of
    the five targets with its command or `not configured`, and the `note`.
  - `sdlc init` prints the same block after writing.

**Lifecycle**
- **R-14 Install-state.**
  - `lifecycle.record(…, recipes=…)` stores the wired recipes as `"recipes": {target: command}` next to `"stack"`
    (the detected kind, or `null`).
  - `SCHEMA` stays 1: the key is optional, and older states without it behave as today.
- **R-15 Expected Makefile.**
  - `lifecycle.expected(rel, ref, stack, recipes=None)` wires `recipes` when given (validated per R-8; an invalid
    entry makes the Makefile `modified`, never rewritten), else the static preset for `stack in cli.STACKS`, as
    today.
  - `classify`, `upgrade` and `repair` pass the recorded `recipes`.
  - Adoption without install-state is unchanged.

**Other**
- **R-16 Docs.**
  - `defaults/test-paths` gains `src/test/*`.
  - Updated: the scaffold `Makefile` header comment (detection, `--stack`), `skills/setup`, `skills/init`
    (`argument-hint`) and `skills/onboard`, README (install note), COMMANDS-QUICK-REF.md, TROUBLESHOOTING.md ("the
    wrong stack was detected"), CHANGELOG `[Unreleased]`, and `docs/architecture.md` (module list; the threat-model
    row for setup gains "detection reads only").
  - `docs/roadmap.md`: the provisional "0009/0010" labels become unnumbered.
  - `defaults/scaffold-history.json` is regenerated with `scripts/scaffold-history.py`.
- **Non-functional:**
  - Detection takes < 50 ms on a repo top with typical files (one directory listing, at most five small file reads).
  - Stdlib only, Python ≥ 3.9.
  - No new runtime dependency for consumers: wired commands use tools the repo already declares.

## Acceptance criteria
- **AC-1**: Given a repo top with `pom.xml` naming `spring-boot-starter-parent` and an executable `mvnw`, when
  `stacks.detect` runs, then the label is `Java · Spring Boot · Maven`, `typecheck`/`test`/`build` are
  `./mvnw -B -q compile` / `./mvnw -B -q test` / `./mvnw -B -q package -DskipTests`, and `lint`/`format` are absent.
- **AC-2**: Given the same `pom.xml` without `mvnw` but with `maven-checkstyle-plugin` and `spotless-maven-plugin`,
  when detect runs, then the runner is `mvn -B -q` and `lint` is `mvn -B -q checkstyle:check`, `format`
  `mvn -B -q spotless:apply`.
- **AC-3**: Given `build.gradle.kts` applying `org.springframework.boot`, an executable `gradlew`, and no
  Checkstyle/Spotless, when detect runs, then the label is `Java · Spring Boot · Gradle` and the recipes are
  `./gradlew -q classes|test|assemble`.
- **AC-4**: Given `package.json` with scripts `lint`, `test`, `build`, `typecheck`, a `pnpm-lock.yaml`, and no
  `react`/`angular.json`, when detect runs, then the kind is `node` and the recipes are `pnpm run lint|test|build|typecheck`.
- **AC-5**: Given a React app whose `test` script is `react-scripts test` with `yarn.lock`, when detect runs, then
  `test` is `CI=true yarn run test`. Given a Vite React app with `test:ci` and `test`, `test` is `npm run test:ci`.
- **AC-6**: Given `angular.json` with a Karma test builder and `"test": "ng test"`, when detect runs, then the kind
  is `angular` and `test` is `npm run test -- --watch=false --browsers=ChromeHeadless`. With a non-Karma builder,
  `test` is `npm run test -- --watch=false`.
- **AC-7**: Given `package.json` with `tsconfig.json` and no type-check script, when detect runs, then `typecheck` is
  `npx tsc --noEmit`. Given npm's default `"test": "echo \"Error: no test specified\" && exit 1"`, `test` is absent.
- **AC-8**: Given scripts named `lint;rm -rf ~`, `$(x)`, `a\nb` and `-x`, when detect runs, then none of them
  becomes a recipe, and no script body appears in any recipe.
- **AC-9**: Given `pyproject.toml` only, or `go.mod` only, when detect runs, then the recipes equal the python or go
  preset.
- **AC-10**: Given `pom.xml` and `go.mod` both at the top, when detect runs, then `kind` is `None` and `note` names
  `java` and `go` and `--stack`.
- **AC-11**: Given `package.json` that is a symlink, over 1 MiB, or invalid JSON (or a `pom.xml` that is invalid
  XML), when detect runs, then that file isn't used, no exception escapes, and nothing outside the repo top is read.
- **AC-12**: Given a fresh git repo with a Spring Boot `pom.xml`, when the agent runs `sdlc setup --yes` (no
  `--stack`), then the created Makefile has the AC-1 recipes in place of those stubs, and install-state holds
  `"stack": "java"` and the same `"recipes"`.
- **AC-13**: Given the same repo, when `sdlc setup --dry-run` runs, then the output has a `Stack` block with the
  label, `pom.xml`, each target's command or `not configured`, and nothing is written.
- **AC-14**: Given a repo with an existing Makefile and an Angular `package.json`, when `sdlc setup --yes` runs, then
  the Makefile is byte-identical afterwards, and the output and `sdlc doctor` show the detected recipes as a
  suggestion.
- **AC-15**: Given a fresh repo with a React `package.json`, when the human's whole prompt is
  `/zouj-ai-sdlc:setup solo` (through `hooks/engine.sh`), then the created Makefile is wired per AC-5. The reply
  lists `Makefile: detected` with each target. HEAD is still the single-file `chore(aiops): Setup Profile solo`
  commit, and the Makefile is uncommitted.
- **AC-16**: Given a `package.json` whose script name or `angular.json` content holds an ESC or other control
  character, when the typed setup command replies, then the reply holds no raw control character (printable
  escapes only).
- **AC-17**: Given `--stack none`, the Makefile keeps all five stubs. Given `--stack react` on a repo without
  `package.json`, nothing is wired and the output says why. Given `--stack rust`, setup and init refuse with the
  list of valid values and write nothing.
- **AC-18**: Given a repo wired by detection (AC-12), when `sdlc list-installed`, `sdlc upgrade --dry-run` and
  `sdlc repair --dry-run` run, then the Makefile is `current`, and neither command plans to replace it. Given the
  Makefile deleted, `repair` restores it with the recorded recipes.
- **AC-19**: Given install-state whose `recipes` holds a multi-line value or one starting with a tab, when `upgrade`
  or `repair` runs, then the Makefile isn't rewritten with that value (`cli.wire` refuses it), and the file is
  treated as modified.
- **AC-20**: Given a repo wired with `--stack python|node|go` by 0.2.0-beta.1 (`Makefile+<stack>` hash) and no
  `recipes` key, when `upgrade` runs, then it behaves as today.
- **AC-21**: Given the `/fix` test lock is on, when the agent edits `src/test/java/AppTest.java`, then the edit is
  blocked.
- **AC-22**: The playbook conformance tests (`tests/test_playbook.py`) pass unchanged for every profile, core and
  full scaffold. No gate, approval, profile key or CI-audited file differs from a run with `--stack none`, except the
  Makefile recipes, `install-state.json` and the setup output.
- **AC-23**: The docs named in R-16 mention detection and `--stack auto|none|…`, TROUBLESHOOTING.md has the "wrong
  stack detected" entry, and `make check` and `make validate` pass.

## Data model
No database. One file format changes:

| File | Change | Owner / protection | Classification |
|---|---|---|---|
| `.aiops/install-state.json` | optional `"recipes": {"format"…"build": "<one-line command>"}`; `"stack"` may now be `java`, `react`, `angular` too. `"schema": 1` unchanged | engine-written; protected path (`defaults/protected-paths`, `guards.GUARDED_RE`), CODEOWNERS | internal (commands, no secrets) |
| `Makefile` (consumer, created by setup) | the five contract stubs replaced by detected recipes | not human-owned (as today); left uncommitted for review | internal |
| `defaults/test-paths` | `+ src/test/*` | plugin default | public |
| `defaults/scaffold-history.json` | regenerated: the Makefile template hash changes (header comment) | plugin release data | public |

Migration: none. Older install-state lacks `recipes` and keeps today's behaviour (AC-20). Reverting the plugin
ignores the extra key: `load` keeps unknown keys, and `expected` without `recipes` falls back to the preset or the
template, so a detected Makefile then reads as `modified` and is never touched.

## API contracts
CLI, the only interface:

| Command | Change | Exit codes |
|---|---|---|
| `sdlc setup [--stack auto\|none\|python\|node\|go\|java\|react\|angular] …` | default `auto`; `Stack` block in the preview, `--dry-run` and the result | 0 ok · 1 refused (unknown value, nothing written) · 2 unconfirmed (as today) |
| `sdlc init [--stack …]` | same values and default; the block after writing; the "Next" text stops pointing at copying presets | 0 · 1 |
| `sdlc doctor` | the Makefile row adds `detected <label>: …` when targets are unwired | unchanged |
| typed `/zouj-ai-sdlc:setup <profile>` (prompt hook) | the reply gains the `Makefile:` block (R-12); `systemMessage` carries it, escaped | unchanged |

Module API (internal):
- `stacks.detect(root, force=None) -> Detection`, with `Detection = namedtuple("Detection", "kind label recipes evidence note")`;
- `stacks.KINDS`;
- `cli.wire(src, recipes) -> (src, wired)`;
- `cli.preset_recipes(stack) -> dict`;
- `lifecycle.record(..., recipes=None)`;
- `lifecycle.expected(rel, ref, stack=None, recipes=None)`.

The single caller that passes a recipes *text* today, `scripts/scaffold-history.py`, moves to `preset_recipes`.

## Security & data-leak flags
- ⚠️ **Command injection into the Makefile.** Repo files (possibly from an untrusted clone) choose text that `make`
  later executes on every Stop and edit.
  - Mitigation:
    - only fixed templates plus a validated script *name* are emitted (R-4, R-8), never a script body;
    - single-line and no-leading-tab checks in `cli.wire`;
    - AC-8 and AC-19 test it.
  - Residual: a script *named* `lint` runs whatever its body says. That is the repo's own command, the same as
    `npm run lint` by hand, and the Makefile is left uncommitted for the human's review. (owner: zoujagger)
- ⚠️ **The prompt-hook path changes** (ADR 0003: the typed setup command in a repo without `.aiops/`).
  - Mitigation:
    - detection reads only and is called inside `scaffold_first` after its existing checks (scaffold root,
      preflight, symlink refusal);
    - no new prompt is matched, and no new file is committed;
    - reply text is escaped (AC-16).
  - The review includes a security pass. (owner: zoujagger)
- ⚠️ **Reads outside the repo or through links.**
  - Mitigation: top-level regular files only, `symlink_on_path`, a 1 MiB cap, no recursion (R-2, AC-11).
  - Secrets: none of the marker files are in `defaults/secret-paths`. Detection never opens `.env*`, `.npmrc` or
    `settings.xml` (which can hold registry tokens). Detection names its files explicitly, and a test asserts the
    list. (owner: zoujagger)
- ⚠️ **Install-state as a command source.** `upgrade`/`repair` write recorded recipes into the Makefile, so a tampered
  install-state could inject a command.
  - Mitigation:
    - install-state is a protected path that the agent can't write (Edit/Write and shell);
    - CODEOWNERS covers it;
    - recipes are re-validated on read (R-15, AC-19).

  (owner: zoujagger)
- ⚠️ **Denial of service of the Stop hook** (a wired command that hangs, such as watch mode).
  - Mitigation: R-4's watch-mode rules (AC-5, AC-6). The Stop hook's existing behaviour is unchanged.
  - Residual: a repo's own `test` script that watches by design. TROUBLESHOOTING.md explains `--stack none` and
    editing the recipe. (owner: zoujagger)
- No personal data, no network, no telemetry: detection output stays in the local terminal, the hook reply and the
  repo's own files.

## Architecture
- **New `lib/sdlc_engine/stacks.py`.**
  - Pure functions over `Path`.
  - One detector per family (`_java`, `_node_family`, `_python`, `_go`), each returning recipes and evidence.
  - `detect` does the family choice (R-3).
  - No imports beyond `json`, `re`, `xml.etree.ElementTree`, `collections`, `pathlib`, `os`, and `cli` for
    `symlink_on_path` and `TEMPLATES`.
- **`cli.py`:**
  - `wire` takes a dict, plus R-8 validation (`cli.py:398`);
  - `preset_recipes`;
  - `STACKS` stays the static-preset tuple that `scaffold-history` hashes (`cli.py:435`), and a new `STACK_CHOICES`
    for options;
  - `cmd_init` (`cli.py:622`): option, block, "Next" text;
  - `_wire_stack` → `_wire_detected(root, detection)`;
  - the doctor row (`cli.py:836`).
- **`setup.py`:**
  - `OPTIONS["--stack"]` (`setup.py:407`);
  - `main` prints the block before confirmation;
  - `apply` (`setup.py:559`) wires and records recipes;
  - `scaffold_first` (`setup.py:769`) detects, wires and records;
  - `set_first_profile` (`setup.py:795`) adds the reply block.
- **`lifecycle.py`:** `record` (`:56`), `expected` (`:212`) and its callers (`:252`, `:545`, `:655-668`, `:723`) pass
  `st.get("recipes")`.
- **`scripts/scaffold-history.py`** uses `preset_recipes`.
- **Alternatives considered:**
  - *Static presets per new stack* (`java.recipes` etc.): rejected. They ignore the repo's scripts and wrappers,
    which is the intent's main point.
  - *Running the tools to probe* (`npm pkg get`, `mvn help:effective-pom`): rejected. It executes repo code during
    setup, including in the prompt hook, and needs the toolchain installed.
  - *Recording only `stack` and re-detecting at upgrade*: rejected. The Makefile would change when repo files
    change, and upgrade would rewrite it unasked.
  - *Wiring an existing Makefile's stubs*: out of scope (intent). Rule 5 says never overwrite.
- **ADR:** none. The decisions extend ADR 0003's command without changing what it decides. The flags above record
  the trade-offs.

## Rollout & rollback
- Ships in the next pre-release (0.2.0-beta.2) with a CHANGELOG entry. No feature flag: `--stack none` is the
  opt-out.
- **Rollback (one command):** `git revert <merge sha>`.
  - Repos already wired keep their Makefile.
  - On the older plugin, their install-state's extra `recipes` key is ignored, and the Makefile reads as `modified`,
    never touched.
- **What to watch:** TROUBLESHOOTING/feedback issues about wrong detection or a hanging `make check`, and
  `make evals` (`profile-by-setup-command`) staying green.

## Open questions
- [ ] Should `typecheck` for Node fall back to `npx tsc --noEmit` when only a dependency on `typescript` (no
      `tsconfig.json`) exists? This spec says no (needs `tsconfig.json`). (zoujagger)
- [ ] Should `sdlc setup --stack <kind>` on a repo whose Makefile already exists offer to wire its stubs in a later
      intent? Out of scope here; record it in the roadmap if wanted. (zoujagger)
