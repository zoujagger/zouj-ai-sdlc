<!-- PR description for intent 0003, generated in state 5. `gh pr create --body-file` it. -->
## feat: guided setup and first-run onboarding (0.2.0-alpha.2)

**Intent:** `.aiops/0003-guided-setup/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 86/100 at `60ed7a0` (round 11; verifier, code reviewer and security reviewer in fresh contexts)

### What and why
Roadmap Phase 1: get a newcomer from nothing to their first approved intent with one guided, rerunnable command,
with the AI-Native SDLC Playbook workflow unchanged in every profile.
- **`sdlc setup` / `/zouj-ai-sdlc:setup`:** preflight → inventory → plan → gate summary → one confirmation → apply →
  human steps → doctor. It has `--dry-run` and `--yes`, and refuses unknown options and values.
- **Profiles `solo`, `team` and `strict`** change only how a human approval is proven. The new `"sk"` key policy,
  with a CI audit, backs `strict`.
- **Human-owned files stay human.** Run by the agent, setup never changes an existing config or settings file, and
  `init --force` keeps every file the guards won't let the agent write. A new config gets init's defaults, and a
  non-team profile (a downgrade is labelled) is printed as the terminal command for the human.
- **Safer scaffold writes.** They never go through a symlink or a hard link. They happen only at the top of the git
  repo the command runs in, never in `$HOME`, `~/.claude` or a toolchain path, and the pre-bash guard keeps the
  agent's `init`/`setup` in its session's repo.
- **Unreviewed trust files** (an `allowed-signers` that no commit has, holding something setup doesn't write, or with
  staged content that isn't on disk) are shown as `!` with an escaped diff and left out of the commit step. The step
  commits exactly the scaffold paths (`git add -- … && git commit … -- …`), never `git add -A`.
- **The scaffold offers the plugin to collaborators** through a marketplace snippet pinned to the release.
- **Docs and support:** a task-first README with a throwaway-repo recipe, `COMMANDS-QUICK-REF.md`,
  `TROUBLESHOOTING.md`, issue forms, and `sdlc feedback`, which sends nothing.
- **Tests:** a playbook conformance test per profile, including a FAIL review staying at state 5. 172 tests pass.
- **No sandbox.** A `--sandbox` trial-repo builder was built, then removed after review round 3 (a human decision).

### Acceptance criteria
- [x] AC-1: dry run prints preflight, inventory, plan and gates, and writes nothing (`tests/test_setup.py:114`)
- [x] AC-2: `setup --profile solo --yes` initializes with the solo config (`tests/test_setup.py:190`)
- [x] AC-3: a rerun plans 0 writes (`tests/test_setup.py:218`)
- [x] AC-4: under the agent, existing owned files are untouched; changes become human steps (`tests/test_setup.py:244`)
- [x] AC-5: a human merge adds only the marketplace keys, after a shown diff (`tests/test_setup.py:383`, `:309`)
- [x] AC-6: no tty and no `--yes` → exit 2, nothing written (`tests/test_setup.py:128`)
- [x] AC-7: `strict` accepts only touch `sk-` keys (`tests/test_engine.py:530`, `:513`, `:392`)
- [x] AC-8: the playbook holds in every profile; a FAIL review stays at state 5 (`tests/test_playbook.py:135-141`)
- [x] AC-9: `init` writes the pinned marketplace snippet, deny list intact (`tests/test_cli.py:96`)
- [x] AC-10: unknown options (`--sandbox` included) refused; the README has the recipe (`tests/test_setup.py:765`, `:777`)
- [x] AC-11: preflight `!` rows with fixes, `✗` stops before writing (`tests/test_setup.py:80`)
- [x] AC-12: task-first README, troubleshooting, quick reference, issue forms (`tests/test_shell_hooks.py`)
- [x] AC-13: `sdlc feedback` prints links and a doctor summary, offline (`tests/test_setup.py:791`)
- [x] AC-14: version `0.2.0-alpha.2`, CHANGELOG, `make check` and `claude plugin validate .` (`tests/test_shell_hooks.py:349`)
- [x] AC-15: `strict` requires CODEOWNERS on `/.aiops/` (`tests/test_cli.py:190`)

### Deviations from plan
46 entries in [plan.md](plan.md)'s Deviation log. The main ones:
- **The sandbox (S9) was removed in S15** after three review rounds kept finding same-user routes into the caller's
  repo.
- **Review fixes, round by round:** F1–F6, G1–G2, H1–H4, J1–J6, K1–K3, L1–L4, M1–M5, then docs only (N1, N2).
- **Corrections recorded in later rows:** K1's protected-paths claim (corrected by L1), N1's workaround (by N2), and
  N2's wording (by the last decision row).
- **Pins:** S12 and J1 are declared pins with mutation checks.

### Known issues shipped (0.2.0-alpha.3)
All listed in the CHANGELOG. The ones that matter for **your first "adopt" commit**: an agent running as you controls
`.git`, so these still get through setup's checks:
- A `config.json` planted before `init` with one profile's keys passes as setup's own.
- A staged key is flagged, but the review shows the disk copy, not the staged content.
- A staged key hidden with skip-worktree/assume-unchanged isn't flagged.
- Repo-local filters, attributes or hooks planted before `init` can change what is committed, shown or pushed.

**Before merging any adoption PR, read its full "Files changed" on GitHub, every file, ideally with a second
person.** CODEOWNERS doesn't cover that PR (GitHub reads it from the base branch). The local checks in the CHANGELOG
and TROUBLESHOOTING are best-effort, and two of them have gaps this release ships with:
- **Step 2 is wrong as written:** `git update-index --no-skip-worktree --no-assume-unchanged -- <file>` in one call
  doesn't clear skip-worktree. Run `git update-index --no-skip-worktree -- <file>` and then
  `git update-index --no-assume-unchanged -- <file>` as two calls.
- **Steps 1 and 3 can still be blinded** by `include.path` or worktree config (use
  `git config --local --list --includes --show-origin`), `git replace` objects (add `--no-replace-objects`), a `-diff`
  attribute (add `--text`), `log.showSignature`/`gpg.program` and `color.*` (add `--no-show-signature --no-color`),
  and a locally moved `origin/main` (`git fetch origin` first).
- **The guard's false-positive list** also covers `popd` and `-okdir`.

### Risks and rollback
- **Rollout:** existing repos change nothing until someone runs `sdlc setup`; a config without `profile` reads as
  `team`.
- **Residuals** (docs/architecture.md): local guards are a deterrent against a same-user agent; the guarantee is the
  signed-approval CI audit reading config, signers and CODEOWNERS from the base ref. Guard text-parsing gaps
  (interpreters, dynamic command words, brace-expanded `cd`, unlisted wrappers) are listed there.
- **Rollback:** revert the merge. Scaffolds written by this version keep working with 0.2.0-alpha.1, which ignores
  the new keys.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
