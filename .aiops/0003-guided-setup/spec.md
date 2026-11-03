---
id: 0003
title: Guided setup and first-run onboarding (roadmap phase 1)
status: Draft          # Draft → Approved (human types `Spec Approved 0003`)
risk: medium           # touches init, approval policy and project settings; no gate semantics change
intent: ./intent.md
created: 2026-11-03
---

# Spec: Guided setup and first-run onboarding (roadmap phase 1)

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md (one rerunnable guided setup, profiles that
     only change how approvals are proven, team auto-offer, a local sandbox, task-first docs), translated into
     engineering requirements. -->

## Summary
A new `sdlc setup` command (also `/zouj-ai-sdlc:setup`) replaces the three manual install steps with one guided,
rerunnable flow:
- **Preflight:** checks the prerequisites.
- **Inventory:** shows what's already installed.
- **Profile:** you pick one of `solo`, `team` or `strict`.
- **Preview:** shows every change and what the playbook gates will enforce.
- **Confirmation:** you confirm once.
- **Writes:** only files the plugin owns. For human-owned material it prints the exact commands.
- **Doctor:** runs `sdlc doctor` at the end.

`init` writes a project marketplace snippet, so collaborators are offered the plugin. `sdlc setup --sandbox <dir>`
creates a throwaway repo with a sample intent to try the workflow. The README becomes task-first, with pinned
commands, and troubleshooting, quick-reference and feedback surfaces are added.

The playbook workflow is the same in every profile, and a conformance test proves it. Ships as **0.2.0-alpha.2**.

## Requirements
- **R-1 Guided setup.** `sdlc setup [--profile solo|team|strict] [--stack python|node|go] [--dry-run] [--yes]`, run in a
  repo root, does five things in order:
  1. **Preflight.** It reports ✓ / ✗ / ! for each of:
     - git, make, python ≥ 3.9
     - `claude` on PATH, version ≥ 2.1
     - optional `gh`: logged in, and whether the token has the `workflow` scope
     - a git credential helper, or `gh` as the helper
     - for `team` and `strict`: the signing checks from `doctor`
  2. **Inventory.** Is the repo initialized? What profile does it have now? Is the marketplace snippet present? Is
     the plugin enabled in `~/.claude/settings.json` or in the project's settings?
  3. **Plan.** The exact list of actions (create, merge or skip, file by file), plus the **gate summary**: what the
     read-only lock, the human gates, the merge and deploy guards and the Stop hook will enforce.
  4. **Confirm.** One `[y/N]` question. `--yes` skips it, and `--dry-run` stops before it with exit code 0.
  5. **Apply and hand over.** It writes, prints the **human steps** (the `/plugin` commands and, for `team`/`strict`,
     the signing commands), then runs `doctor`.

  Without `--yes` and without a tty, setup asks for nothing and writes nothing. It exits 2 and lists the choices that
  are still needed.
- **R-2 Rerunnable and idempotent.** Running setup again with the same choices plans 0 writes. Running it on a repo
  that 0.2.0-alpha.1 initialized changes no existing file without showing a diff and getting confirmation.
- **R-3 Profiles change only how a human approval is proven.**
  - **`solo`:** `require_signed_approvals: false`, `commit_approvals: true` (unsigned single-file approval commits),
    `approval_key_policy: "any"`.
  - **`team`:** `require_signed_approvals: true`, `approval_key_policy: "human"` (today's default).
  - **`strict`:** `require_signed_approvals: true`, `approval_key_policy: "sk"`. The new `"sk"` value accepts only an
    `sk-` key without `no-touch-required`.
  - Every profile keeps the state machine, the human approval phrases, the read-only lock, the Stop hook, the
    merge, push and deploy guards, the review requirement and the `aiops-gates` CI audit.
  - The chosen profile is recorded as `"profile"` in `.aiops/config.json`.
- **R-4 Human-owned material is never written by the agent.**
  - **Under the agent** (`CLAUDECODE` / `CLAUDE_CODE_CHILD_SESSION` set), setup writes only what `init` already
    writes for a new repo. It doesn't change an existing `.aiops/config.json`, merge into an existing
    `.claude/settings.json`, or write keys, `allowed-signers` or global git config. For those it prints the exact
    change and the command for the human.
  - **Run by a human,** setup may also:
    - merge the marketplace keys into an existing project `.claude/settings.json`
    - change the profile in an existing `config.json`

    Each one is shown as a diff and confirmed. It never touches `permissions` or `hooks` keys.
- **R-5 Team auto-offer.** The scaffold's `.claude/settings.json` gains:
  - `extraKnownMarketplaces.zouj` = `{"source": {"source": "github", "repo": "zoujagger/zouj-ai-sdlc"}}`
  - `enabledPlugins["zouj-ai-sdlc@zouj"] = true`

  The existing `permissions.deny` rules are kept.
- **R-6 Sandbox.** `sdlc setup --sandbox <dir>` refuses a `<dir>` that exists and isn't empty. Otherwise it creates
  the directory with:
  - a git repo on `main`
  - a tiny python app with a test, and a wired Makefile
  - the `solo` scaffold and profile
  - the marketplace snippet
  - a sample intent `0001` in Draft

  It commits all of that, then prints how to walk the five states there, starting with `Intent Approved 0001`. It
  never touches the current repo.
- **R-7 Task-first documentation.**
  - The README opens with a "Start using" table that maps tasks to commands and playbook stages, followed by pinned
    install paths:
    - A: `sdlc setup`
    - B: the native `/plugin` commands
    - C: the declarative snippet
  - Then the "official sources only" note. The state machine and threat model move below.
  - New `TROUBLESHOOTING.md`, `COMMANDS-QUICK-REF.md`, and `.github/ISSUE_TEMPLATE/{install-problem.yml,
    quick-feedback.yml, config.yml}`.
- **R-8 `sdlc feedback`.** It prints the issue links and the local `doctor` summary to paste. It makes no network
  calls.
- **R-9 Skill.** `skills/setup/SKILL.md` (`/zouj-ai-sdlc:setup`) runs preflight and `--dry-run`, relays the plan,
  and applies only after the human confirms in chat. Human-owned steps go to the human's terminal. `skills/init`
  points to setup.
- **R-10 Playbook conformance test.** New `tests/test_playbook.py`, for each profile:
  - a fresh repo moves through states 1 → 6 only through the human approvals
  - code is read-only in states 1-3
  - the agent can't approve, merge, push to main or deploy
  - state 6 needs a PASS `review.md` on main
  - Stop needs `make check`
- **R-11 Release.** `0.2.0-alpha.2`: plugin.json, the CHANGELOG section and its links, and the alpha notice.
- **Non-functional:**
  - stdlib only, no new dependencies
  - setup with `--dry-run` finishes in under 3 s, excluding the `claude`/`gh` subprocess time
  - no hook latency change (setup isn't a hook)
  - every message gives the reason and the procedure (house style)

## Acceptance criteria
- **AC-1:** Given a fresh git repo and a tty, when the human runs `sdlc setup --profile team --dry-run`, then it
  prints the preflight table, the inventory, the action plan and the gate summary, and exits 0 with **no file
  changed** (`git status` clean, no new files).
- **AC-2:** Given a fresh repo, when `sdlc setup --profile solo --yes` runs, then the repo is initialized,
  `.aiops/config.json` has `profile: solo`, `require_signed_approvals: false`, `commit_approvals: true`, and
  `sdlc status` shows "no active intent" with code read-only.
- **AC-3:** Given AC-2's repo, when the same command runs again, then the plan shows 0 writes and no file changes.
- **AC-4:** Given a repo initialized by 0.2.0-alpha.1 with a custom `.claude/settings.json`, when setup runs
  **under the agent**, then that file and `.aiops/config.json` are unchanged. Setup prints the JSON keys to add and
  the profile change as human steps, and exits 0.
- **AC-5:** Given the same repo, when a **human** runs setup and confirms, then only `extraKnownMarketplaces` and
  `enabledPlugins` are added to `.claude/settings.json` (`permissions` and `hooks` byte-identical), and the profile
  change is applied after a shown diff.
- **AC-6:** Given no tty and no `--yes`, when setup runs, then it writes nothing and exits 2 listing the missing
  choices.
- **AC-7:** Given the `strict` profile, when the signing key is a passphrase (non-`sk-`) key or an `sk-` key
  allow-listed with `no-touch-required`, then `approve` and `doctor` refuse with the reason. An `sk-` key with
  touch passes.
- **AC-8:** Given each profile (`solo`, `team`, `strict`), when the playbook conformance test runs, then every check
  holds:
  - states advance only through the human phrases
  - writes in states 1-3 are blocked
  - agent `approve`, `merge`, push to main and prod deploy are blocked
  - state 6 requires a PASS review on main
  - the Stop hook requires `make check`
- **AC-9:** Given `sdlc init` in a fresh repo, then `.claude/settings.json` contains the marketplace snippet and the
  unchanged `permissions.deny` list.
- **AC-10:** Given `sdlc setup --sandbox <dir>` with a missing `<dir>`, then `<dir>` is a committed git repo on
  `main`, with the solo scaffold and a Draft intent `0001` that validates, and `make check` is green there. The
  current repo is unchanged. Given a non-empty `<dir>`, it refuses with exit 1.
- **AC-11:** Given preflight on a machine where `gh` lacks the `workflow` scope or there is no credential helper,
  then those rows are `!` with the exact fix command, and setup still proceeds. Given `python3` older than 3.9 or a
  missing `git`, they are `✗` and setup stops before writing.
- **AC-12:** The README begins with the "Start using" table, followed by the three pinned install paths. Static
  tests check that `TROUBLESHOOTING.md`, `COMMANDS-QUICK-REF.md` and the three issue templates exist, and that
  every slash command in the quick reference is a real skill.
- **AC-13:** `sdlc feedback` prints the issue-template links and the doctor summary, opens no network connection,
  and exits 0.
- **AC-14:** `plugin.json` is `0.2.0-alpha.2`, the CHANGELOG has the matching section and links, and `make check`
  and `claude plugin validate .` pass.
- **AC-15:** Given the `strict` profile and a `.github/CODEOWNERS` that doesn't cover `/.aiops/`, when `doctor` runs,
  then that row is ✗ (exit 1) and setup lists the CODEOWNERS line as a human step. Under `solo` or `team`, the same
  repo shows only `!`.

## Data model
No database. File contracts:

| File | Change | Owner | Classification |
|---|---|---|---|
| `.aiops/config.json` | new key `profile` (`solo` \| `team` \| `strict`); `approval_key_policy` gains the value `"sk"` | human (written by init or setup only on creation, or by a human run) | internal |
| `.claude/settings.json` (scaffold) | adds `extraKnownMarketplaces.zouj` and `enabledPlugins["zouj-ai-sdlc@zouj"]` | human | internal |
| `.github/ISSUE_TEMPLATE/*.yml` | new (this repo only) | maintainer | public |

Migration: none needed. A missing `profile` reads as `team`, which matches 0.2.0-alpha.1 behaviour.
`approval_key_policy` values other than `human` / `any` / `sk` are refused by doctor.

## API contracts
CLI (exit codes: 0 ok · 1 error or refusal · 2 nothing written because input is missing):
- `sdlc setup [--profile solo|team|strict] [--stack python|node|go] [--dry-run] [--yes]`
- `sdlc setup --sandbox <dir> [--stack python]`
- `sdlc feedback`
- `sdlc doctor`: unchanged, plus a profile row and the `"sk"` policy.

Output sections, in order: `Preflight`, `Inventory`, `Plan`, `Gates`, `Human steps`, `Doctor`. Each line is
`✓|✗|!|+|~|=` followed by a message. `+` means create, `~` means merge or change with a diff, `=` means unchanged.

Skill: `/zouj-ai-sdlc:setup [profile]`.

## Security & data-leak flags
- ⚠️ **The `solo` profile proves approvals by the typed phrase and an unsigned commit only.**
  - **Risk:** anything running as the user can forge an approval that CI accepts.
  - **Mitigation:** setup's gate summary and the README state it plainly. CI still requires single-file,
    non-Claude-co-authored approval commits. Teams are steered to `team`.
  - **Decides:** zoujagger.
- ⚠️ **Setup writing `.claude/settings.json`.**
  - **Risk:** an agent could use setup to change permissions or hooks, or to point the marketplace elsewhere.
  - **Mitigation:**
    - Setup merges only the two marketplace keys, with a constant source (`github zoujagger/zouj-ai-sdlc`).
    - It never writes under the agent when the file already exists (R-4).
    - `permissions` and `hooks` stay byte-identical (AC-5).
    - The file stays in protected-paths and CODEOWNERS.
  - **Decides:** zoujagger.
- ⚠️ **Profile changes through setup.**
  - **Risk:** an agent could downgrade `team` to `solo`.
  - **Mitigation:**
    - Under the agent, an existing `config.json` is never changed (AC-4). The change is printed for the human.
    - The `config.json` guards stay as they are.
    - CI reads the config from the base ref.
  - **Decides:** zoujagger.
- ⚠️ **Preflight runs `gh auth status` and `claude --version`.**
  - **Risk:** a token printed into the session.
  - **Mitigation:** setup never passes `-t`/`--show-token`, and parses only the scopes line. Outputs are filtered
    before printing.
  - **Decides:** zoujagger.
- ⚠️ **The sandbox path.**
  - **Risk:** writing into an existing directory or outside the intended place.
  - **Mitigation:** setup refuses an existing non-empty directory, resolves the path, and never follows a symlink out
    of it.
  - **Decides:** zoujagger.
- ⚠️ **`sdlc feedback`.**
  - **Risk:** leaking local data.
  - **Mitigation:** it prints only. No network calls, and no paths beyond the repo name.
  - **Decides:** zoujagger.

## Architecture
- **`lib/sdlc_engine/setup.py` (new):**
  - `preflight()`, `inventory(root)`, `plan(root, choices)`, `apply(plan)`, `sandbox(dir, stack)`
  - It reuses:
    - `cmd_init`'s scaffold copy, refactored into `machine`/`cli`: `init_actions(root, stack)` returns actions and
      `cmd_init` applies them, so `init` and `setup` share one source of truth
    - `approvals.signing_problem` / `key_protection` for the signing rows
    - `approvals.running_under_agent` for R-4
    - `_doctor_signing` / `cmd_doctor`
- **`lib/sdlc_engine/cli.py`:** adds `cmd_setup` and `cmd_feedback` to `COMMANDS`, and a profile row in
  `cmd_doctor`.
- **`approvals.key_protection`:** gains the `"sk"` policy, reusing `_signer_options`.
- **Profiles:** a constant mapping in `setup.py`, `PROFILES = {"solo": {...}, "team": {...}, "strict": {...}}`, merged
  into the scaffold config at creation.
- **Templates:**
  - `templates/scaffold/.claude/settings.json` gains the snippet.
  - `templates/sandbox/` (new): app, test, Makefile and the sample intent.
- **Docs:**
  - `README.md` (restructured)
  - `TROUBLESHOOTING.md`, `COMMANDS-QUICK-REF.md`
  - `docs/roadmap.md` (Phase 1 marked in progress)
  - `.github/ISSUE_TEMPLATE/`
- **Skills:** `skills/setup/SKILL.md` (new); `skills/init/SKILL.md` points to setup.
- **Tests:** `tests/test_setup.py` (AC-1..AC-7, AC-9..AC-11, AC-13), `tests/test_playbook.py` (AC-8), and additions to
  `tests/test_shell_hooks.py` (AC-12, AC-14).
- **Alternatives considered:**
  - **Driving `/plugin` from setup:** impossible, because Claude Code owns those commands. The declarative snippet
    gets the same result for collaborators.
  - **An npm or PyPI installer:** out of scope this phase (stdlib only).
  - **An advisory "trial" profile:** rejected because it would leave the playbook. The sandbox gives the same
    low-risk trial.
- **ADR:** none needed. Profiles don't change gate semantics.

## Rollout & rollback
- **Release:** `0.2.0-alpha.2`.
  - Existing repos: nothing changes until someone runs `sdlc setup`. A missing `profile` means `team`.
  - New repos: `init` writes the marketplace snippet.
- **Rollback:** pin consumers to `v0.2.0-alpha.1` (`ZOUJ_SDLC_REF`) and remove the two snippet keys if they're
  unwanted.
- **Watch:** issues filed with `install-problem.yml`, and the doctor rows people paste through `sdlc feedback`.

## Open questions
- [x] Does `strict` require CODEOWNERS on `.aiops/`? → **Yes.** Under `strict`, doctor shows ✗ and setup lists it as
  a human step when `.github/CODEOWNERS` doesn't cover `/.aiops/`. `solo` and `team` only get a warning
  (zoujagger, 2026-11-03). Covered by AC-15.
