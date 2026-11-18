---
id: 0009
title: Stack auto-detection for the Makefile contract
status: Approved
owner: zoujagger
initiator: zoujagger
source: DX review of adoption friction (2026-11-18); docs/roadmap.md "Next: adoption, part 2" (PR #22)
created: 2026-11-18
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-18T09:59:29Z
approved-via: cli
approved-sha256: 41f09ba4da54a3766ba9204259f210d6336531228c112aa1e5cdbc0d44c5e547
---

# Intent: Stack auto-detection for the Makefile contract

<!-- State 1 BRAINSTORMING. Written from the adoption discussion with zoujagger on 2026-11-18, which answered most of
     the interview: the stacks to cover, reuse of existing scripts, and auto-wiring in both setup paths. Unknowns go
     in Open questions, never invented. approved-* fields are stamped by the human approval; agents never write
     them. -->

## Problem
The Makefile contract (`format`, `lint`, `typecheck`, `test`, `build`; `check` = lint + typecheck + test) is the
only build interface the hooks and CI call. The Stop hook requires `make check` green, and the post-edit hook runs
`make format` and `make lint`. A new adopter still wires it by hand:

- **The typed `/zouj-ai-sdlc:setup <profile>` wires nothing.** In a fresh repo it writes the scaffold Makefile with
  every target printing `not configured`. A target still printing `not configured` counts as a pass, so
  `make check` passes without testing anything. Most first-time users take this path.
- **`sdlc setup --stack` and `sdlc init --stack` need the user to know the flag.** They accept only
  `python|node|go`, and each is a static preset (`templates/stacks/*.recipes`).
- **The presets ignore what the repo already has:**
  - the node preset assumes `npm`, `npx prettier` and `npx tsc` whatever the lockfile, `package.json` scripts or
    `tsconfig.json` say;
  - a repo whose real commands live in `package.json` scripts (`lint`, `test:ci`, `build`) gets different commands
    from the ones its developers and CI run.
- **Some common stacks have no preset at all:**
  - Java / Spring Boot (Maven or Gradle, usually through a `mvnw` / `gradlew` wrapper);
  - React apps (Vite or Create React App, whose default `test` watches and never exits);
  - Angular apps (`ng test` opens a browser in watch mode).

  For these, wiring the contract is guesswork, and a wrong guess makes the Stop hook hang or fail on every turn.
- **The `/fix` test lock doesn't know Java's test layout.** `defaults/test-paths` has no `src/test/` (the
  Maven/Gradle default).

## Desired outcome
- **Setup detects the stack and wires the contract by itself:**
  - Detection looks at the repo top: Java/Spring Boot (Maven or Gradle), Node, React, Angular, and the existing
    Python and Go presets.
  - Wiring uses the repo's own commands where they exist: `package.json` scripts through the package manager its
    lockfile names, and the Maven/Gradle wrapper when the repo has one.
  - It works in **both** paths that create the Makefile: `sdlc setup` / `sdlc init`, and the human's typed
    `/zouj-ai-sdlc:setup <profile>` in a fresh repo.
- **The human sees what was detected before relying on it:**
  - setup's preview and `--dry-run` show it: the stack, the files it was read from, and each target's command or
    "not configured";
  - the typed command's reply lists the same.

  The Makefile stays uncommitted for the human's review, as today.
- **Wired commands don't hang:** test commands for React and Angular run once and exit, rather than starting watch
  mode.
- **No surprise rewrites:**
  - an existing Makefile is never changed; setup and `sdlc doctor` show the detected commands as a suggestion
    instead;
  - after wiring, `list-installed` reports the Makefile as current, and `upgrade` / `repair` never replace it with
    a generic preset.
- **A wrong guess is easy to override:**
  - `--stack <name>` forces a stack;
  - `--stack none` keeps the stubs;
  - a repo with several stacks at its top gets no guess, only a note naming the candidates.
- **Java tests are covered by the `/fix` test lock** (`src/test/`).
- **The playbook workflow (`docs/sdlc.md`) still holds, proven by tests:**
  - the profile, the gates, the approvals and what CI audits don't change;
  - only the Makefile's recipes, the setup output and the test paths do.

## Users & systems affected
- **Users:**
  - new adopters on Java/Spring Boot, Node, React and Angular projects (today: hand-wiring, or a contract that
    tests nothing);
  - existing Python and Go users (detection picks their presets without a flag);
  - maintainers upgrading a repo whose Makefile was wired by detection.
- **Systems:**
  - `lib/sdlc_engine/`:
    - a new detection module (stdlib only);
    - `cli.py`: `wire`, `init --stack`, the doctor's Makefile row;
    - `setup.py`: options, preview, apply, and the typed command's fresh-repo scaffold;
    - `lifecycle.py`: install-state and the expected Makefile;
  - `templates/stacks/`, the scaffold `Makefile` header, `defaults/scaffold-history.json`,
    `defaults/test-paths`;
  - `skills/setup`, `skills/init`, `skills/onboard`;
  - README, COMMANDS-QUICK-REF.md, TROUBLESHOOTING.md, CHANGELOG.md, `docs/architecture.md`.

## Constraints
- **Engine code stays stdlib only** (Python ≥ 3.9): `json` for `package.json`, `xml.etree` for `pom.xml`, plain
  text matching for Gradle scripts. No new tools or dependencies.
- **Detection only reads.** It never runs a command, a package manager or a build tool, and it doesn't install or
  download anything. It reads only regular files at the top of the repo (no symlinks), with a size cap. A file it
  can't parse yields no detection, not an error that stops setup.
- **No script body ever reaches the Makefile.** Only script *names* are used (`<pm> run <name>`), each checked
  against a strict character set. Every recipe is a single line.
- **The typed setup command keeps its guarantees (ADR 0003):**
  - same prompt matching, same preconditions, same single-file profile commit, missing files only;
  - the reply text derived from repo files is escaped like the rest of the reply.

  The change is reviewed with a security pass.
- **`sdlc init` never overwrites an existing file** (CLAUDE.md rule 5), and the agent's own setup still can't write
  human-owned files.
- **Test-first:** failing cases in `tests/` before `lib/` changes (CLAUDE.md rule 2).
- **Compatibility:**
  - `--stack python|node|go` keeps working;
  - repos already wired from a preset keep being recognised by `upgrade` / `repair` (`Makefile+<stack>` hashes in
    `defaults/scaffold-history.json`).

## Out of scope
- Rust, .NET, Ruby, PHP and other stacks not named above (later intents, if asked).
- Monorepos and sub-directories: only the repo top is looked at. A backend at the root with a frontend in
  `frontend/` gets the root's stack.
- Changing an existing Makefile, or wiring targets inside the repo's own Makefile.
- A configurable check command in place of `make check` (a separate idea, not scheduled).
- Running or validating the detected commands during setup (e.g. checking that `./mvnw` works).
- `deploy` and `rollback` recipes.
- Changes to the signing key policy.

## Open questions
- [ ] Java lint/format: wire Checkstyle/Spotless only when the build file already configures them, or leave `lint`
      and `format` as stubs for Java? The post-edit hook runs `make format` and `make lint` after every edit, and a
      Maven run takes seconds (zouj-ai-sdlc maintainer).
- [ ] Angular `test`: force `--watch=false --browsers=ChromeHeadless` (needs Chrome on the machine and in CI), or
      only `--watch=false` and document the browser? (zouj-ai-sdlc maintainer)
- [ ] Should the typed `/zouj-ai-sdlc:setup` reply show every wired command, or only the stack and target names
      with a pointer to the Makefile, to keep the reply short? (zouj-ai-sdlc maintainer)
- [ ] The roadmap's provisional "0009, one-pass approval" and "0010, evals in CI" labels: renumber them, now that
      this intent took 0009? (zouj-ai-sdlc maintainer)
