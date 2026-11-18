<!-- PR description for intent 0009, generated in state 5. `gh pr create --body-file` it. -->
## Stack auto-detection for the Makefile contract

**Intent:** `.aiops/0009-stack-detection/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 98/100 at `5e671b4` (four rounds: verifier, code reviewer and security reviewer in fresh contexts)

### What and why
New adopters had to wire the Makefile contract by hand. The typed `/zouj-ai-sdlc:setup` wired nothing, so
`make check` passed while testing nothing.

**What detection reads.** Setup and init now detect the stack at the repo top:
- Java/Spring Boot: Maven or Gradle, the `mvnw`/`gradlew` wrapper first, and Checkstyle/Spotless only when configured;
- Node, React, Angular: `package.json` scripts through the lockfile's package manager, with tests run once, not in
  watch mode;
- Python and Go: the existing presets.

They print a Stack block with each target's command.

**Who wires** (decided by the human during review):
- A `setup` or `init` you run in your own terminal wires a Makefile it creates, or the untouched stub.
- Run by Claude, or as the typed `/zouj-ai-sdlc:setup`, they only list the commands and your terminal command
  (`… setup --stack auto --yes`). The repo's scripts never run in the Stop hook before you've read them.
- A Makefile you've edited is never changed; `sdlc doctor` suggests the commands instead.

**Safety and lifecycle:**
- Detection only reads:
  - an explicit marker list;
  - `O_NOFOLLOW`/`O_NONBLOCK` plus `S_ISREG`;
  - 1 MiB;
  - no DTD;
  - linear parsing.
- Only fixed script names reach recipes, never script bodies.
- `cli.wire` refuses unsafe lines.
- Install-state records the wired recipes, so `upgrade`/`repair` keep the Makefile. A recorded recipe must match the
  per-target grammar or a shipped preset.
- `--stack auto|none|python|node|go|java|react|angular`.

**Also:**
- the `/fix` test lock covers `src/test/`;
- `sdlc setup` without `--profile` reuses the configured profile (and then changes no human-owned file).

### Acceptance criteria
- [x] AC-1–3: Java Maven/Gradle, Spring Boot label, wrapper, lint/format only when configured (`tests/test_stacks.py::Java`)
- [x] AC-4–8: Node/React/Angular from the repo's scripts, no watch mode, no unsafe names or bodies (`tests/test_stacks.py::Node`)
- [x] AC-9: Python and Go presets (`tests/test_stacks.py::Presets`)
- [x] AC-10–11: ambiguous roots; links, size, parse errors, only marker files read (`tests/test_stacks.py::Family`, `::Robustness`, `::Round2`–`::Round4`)
- [x] AC-12 (amended): a human-run setup wires; the agent's never does (`tests/test_setup.py::Stack`)
- [x] AC-13–14, AC-17: preview block, existing Makefile untouched, `--stack none|<kind>|unknown` (`tests/test_setup.py::Stack`)
- [x] AC-15 (amended), AC-16: the typed command lists, escaped, through `hooks/engine.sh` (`tests/test_cli.py::SetupCommand`)
- [x] AC-18–20: lifecycle keeps detected Makefiles, refuses tampered recipes, beta.1 states unchanged (`tests/test_lifecycle.py::Detected`, `tests/test_cli.py::Init`)
- [x] AC-21: `src/test/` under the `/fix` lock (`tests/test_shell_hooks.py::ShellHooks::test_test_lock_covers_java`)
- [x] AC-22: detection changes only the Makefile and install-state (`tests/test_playbook.py::Playbook::test_detection_changes_only_the_makefile`)
- [x] AC-23: docs, `make check` (513 OK), `make validate`

### Deviations from plan
The plan's Deviation log has 20 rows. The main ones:
- **Only humans wire.**
  - The typed setup command lists the commands instead of wiring (r1, the human's choice).
  - The agent's `setup`/`init` never wire, which amends AC-12 (r2, the human's choice).
- **Setup wires the untouched stub Makefile**, extending R-11.
- **`setup` without `--profile`** reuses the configured profile. It applies human-owned changes only when the
  profile came from `--profile` or the question.
- **Recipe checks:** recorded recipes must match `stacks.emittable(target, cmd)`, and `KNOWN_PRESETS` is frozen.
- **Smaller changes:**
  - forced `--stack python|go` needs no marker file;
  - the 0008 release test allows an `unreleased` scaffold-history entry between releases;
  - an `id` split over lines in a Gradle file no longer marks Checkstyle as configured.
- **Accepted residual:** in a repo without `.aiops/`, the agent's env-stripped `sdlc init` wires as the human. It is
  documented in the threat model; the guard change belongs to intent 0006.

### Risks and rollback
- **Risk:** a wrong guess. The Stack block shows it before anything runs. Override with `--stack <name>`, or keep the
  stubs with `--stack none`. TROUBLESHOOTING has "The wrong stack was detected, or `make check` hangs".
- **Rollback:** `git revert <merge sha>`.
  - Wired repos keep their Makefile.
  - On the older plugin, install-state's extra `recipes` key is ignored, and the Makefile reads `modified`, never
    touched.
- **Watch:** feedback on wrong detection or a hanging `make check`, and the `profile-by-setup-command` eval (1.00
  with the plugin at 72ad55e).

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
