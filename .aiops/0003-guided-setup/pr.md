<!-- PR description for intent 0003, generated in state 5. `gh pr create --body-file` it. -->
## feat: guided setup and first-run onboarding (0.2.0-alpha.2)

**Intent:** `.aiops/0003-guided-setup/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 90/100 at `a619041`

### What and why
Roadmap Phase 1: get a newcomer from nothing to their first approved intent with one guided, rerunnable command,
with the AI-Native SDLC Playbook workflow unchanged in every profile.
- **`sdlc setup` / `/zouj-ai-sdlc:setup`:** preflight → inventory → plan → gate summary → one confirmation → apply →
  human steps → doctor. It has `--dry-run` and `--yes`, and refuses unknown options and values.
- **Profiles `solo`, `team` and `strict`.** They change only how a human approval is proven. The new `"sk"` key policy,
  with a CI audit, backs `strict`.
- **Human-owned files stay human.** Run by the agent, setup never changes an existing config or settings file. A
  new config gets init's defaults, and a non-team profile is printed as the terminal command for the human.
- **The scaffold offers the plugin to collaborators** through a marketplace snippet pinned to the release.
- **Scaffold writes are safer.** They never go through a symlink or a hard link, only at the top of a git repo, and
  never in `$HOME`, `~/.claude` or a toolchain path.
- **Docs and support:**
  - a task-first README with a throwaway-repo recipe
  - `COMMANDS-QUICK-REF.md` and `TROUBLESHOOTING.md`
  - issue forms
  - `sdlc feedback`, which sends nothing
- **Tests:** a playbook conformance test per profile, including a FAIL review staying at state 5.
- **No sandbox.** A `--sandbox` trial-repo builder was built, then removed after review round 3 (a human decision).

### Acceptance criteria
- [x] AC-1: dry run prints preflight, inventory, plan and gates, and writes nothing (`tests/test_setup.py:110`)
- [x] AC-2: `setup --profile solo --yes` initializes with the solo config (`tests/test_setup.py:186`)
- [x] AC-3: a rerun plans 0 writes (`tests/test_setup.py:214`)
- [x] AC-4: under the agent, existing owned files are untouched; changes become human steps (`tests/test_setup.py:240`, `:253`)
- [x] AC-5: a human merge adds only the marketplace keys, after a shown diff (`tests/test_setup.py:362`, `:288`)
- [x] AC-6: no tty and no `--yes` → exit 2, nothing written (`tests/test_setup.py:124`)
- [x] AC-7: `strict` accepts only touch `sk-` keys (`tests/test_engine.py:530`, `:513`, `:392`)
- [x] AC-8: the playbook holds in every profile; a FAIL review stays at state 5 (`tests/test_playbook.py`)
- [x] AC-9: `init` writes the pinned marketplace snippet, deny list intact (`tests/test_cli.py:59`)
- [x] AC-10: unknown options (`--sandbox` included) refused; the README has the recipe (`tests/test_setup.py:564`, `:576`)
- [x] AC-11: preflight `!` rows with fixes, `✗` stops before writing (`tests/test_setup.py:76`, `:492`)
- [x] AC-12: task-first README, troubleshooting, quick reference, issue forms (`tests/test_shell_hooks.py:304`)
- [x] AC-13: `sdlc feedback` prints links and a doctor summary, offline (`tests/test_setup.py:590`)
- [x] AC-14: version `0.2.0-alpha.2`, CHANGELOG, `make check` and `claude plugin validate .` (`tests/test_shell_hooks.py:336`)
- [x] AC-15: `strict` requires CODEOWNERS on `/.aiops/` (`tests/test_cli.py:153`)

### Deviations from plan
28 entries in [plan.md](plan.md)'s Deviation log. The main ones:
- **The sandbox (S9) was removed in S15.** That was the human's decision after three review rounds kept finding
  same-user routes into the caller's repo. The README shows a throwaway-repo recipe instead.
- **Review fixes:**
  - F1–F6 (round 1)
  - G1–G2 (round 2)
  - H1–H4 (round 4): symlink-safe writes, the agent's new config, one argument parser, docs
  - J1–J6 (round 5): the FAIL-review test, the agent's profile hand-off, the root checks, error reporting and
    preflight tool resolution, `no-touch-required` in any case, docs
- **Pins:** S12 and J1 are declared pins with mutation checks.

### Risks and rollback
- **Open findings from review round 6** (the human decides: fix first, or ship as alpha.3 known issues):
  - [MEDIUM] Agent `init --force` resets scaffold files that are protected paths outside the human-owned list (for
    example `governance/`, or a repo-protected Makefile).
  - [MEDIUM] The root check can be redirected (`GIT_DIR`/`GIT_WORK_TREE`, or another repo), so the agent can scaffold
    another repo or a parent folder.
  - **`strict`, unverified:** OpenSSH may not accept `no-touch-required` in `allowed_signers`. Whether
    `ssh-keygen -Y verify` enforces the touch needs a FIDO device to test.
  - LOW and MINOR items are listed in [review.md](review.md).
- **Rollout:** existing repos change nothing until someone runs `sdlc setup`; a config without `profile` reads as
  `team`.
- **Rollback:** revert the merge. Scaffolds written by this version keep working with 0.2.0-alpha.1, which ignores
  the new keys.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
