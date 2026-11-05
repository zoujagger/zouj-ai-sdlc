# Roadmap: easier adoption, same playbook

> Approved by zoujagger on 2026-11-03. Each phase is delivered as its own intent through the plugin's own workflow.
> Phase 1 is intent `.aiops/0003-guided-setup/`.

## What ECC does well (and where we stand)
| ECC pattern | What it looks like | zouj-ai-sdlc today |
|---|---|---|
| **One pinned, guided setup command** | `npx ecc-universal@2.2.3 setup` checks prerequisites, inventories existing installs and plugin scopes, previews every change, asks once to confirm, and is **rerunnable** to update, change scope or change the hook profile. Supports `--dry-run` and `--yes` for CI | Two `/plugin` commands, then `/zouj-ai-sdlc:init` per repo, then manual signing setup (6 commands, 3 files) |
| **Native plugin path, documented as an equal option** | `/plugin marketplace add …` + `/plugin install ecc@ecc`, plus a **declarative `settings.json` snippet** (`extraKnownMarketplaces` + `enabledPlugins`) | Native path only; no declarative snippet. Teammates must each install by hand |
| **Install profiles and explicit hook consent** | `--profile minimal\|core\|full`, `--no-hooks` / `--enable-hooks`; the installer stops before writing hooks without an explicit choice | All or nothing: init turns every gate on. Only `SDLC_HOOK_PROFILE=spike` exists |
| **Lifecycle commands** | `list-installed`, `doctor`, `repair`, `uninstall --dry-run`, backed by **install-state** that records only the files ECC owns | `sdlc doctor` only. No upgrade, repair or uninstall, and init skips existing files without saying what changed |
| **Per-rule runtime controls** | `ECC_HOOK_PROFILE`, `ECC_DISABLED_HOOKS="pre:bash:…"` with stable hook ids | Blocks have no ids and can't be disabled one at a time (the source of the false-positive frustration) |
| **"Start using" table by task** | "Building a feature → /ecc:plan …", "Fixing a bug → …" | The README explains the state machine, but there's no task-first entry point |
| **Support surfaces** | TROUBLESHOOTING.md, COMMANDS-QUICK-REF.md, issue templates (`install-problem.yml`, `quick-feedback.yml`), `ecc feedback`, "never uploads diagnostics" | A threat model and architecture docs; no troubleshooting page, quick reference or issue templates |
| **Beginner path per OS** | A Windows walkthrough: check `node --version`, `git --version`, `claude --version`, then one command | Linux-only assumptions (`/usr/bin/git`, `realpath -m`), no prerequisite check |
| **Trust signals** | "Official sources only" warning, a short plugin id `ecc@ecc`, pinned versions in every command, rich marketplace metadata (version, category, tags, homepage) | Long namespace (`/zouj-ai-sdlc:intent`), sparse marketplace entry, no icon |
| **In-plugin reconfiguration** | `/ecc:configure-ecc` runs the same safe flow from inside Claude | None |

**Don't copy:**
- ECC's breadth (7 harnesses, 300+ skills, sponsor banners, a very long README).
- An npm dependency. The engine stays stdlib-only Python (the user's standing rule: keep dependencies).
- ECC's "no-hooks / minimal" install. For us, hooks *are* the workflow. A profile without them would leave the
  playbook.

## Non-negotiable: the AI-Native SDLC Playbook workflow (`docs/sdlc.md`)
Every install path, profile, scope and convenience command below must keep all of these. They are tested, not just
documented:
1. **The stages run in order, each with its artifact:**
   - Intent → `intent.md`
   - Design → `spec.md`
   - Build (Plan mode, read-only) → `plan.md`
   - Build (execution) → code with TDD `Red:` evidence
   - Test
   - AI review → `review.md` and `pr.md`
   - Deploy and release
   - Maintain → a **new** `intent.md`
2. **Humans make the gate decisions:** `Intent Approved`, `Spec Approved`, `Plan Approved`, the merge, and the
   production approval. The agent can never make them.
3. **The read-only lock in states 1-3.** The Stop hook requires `make check` green. The merge and push-to-main
   guards and the deploy guard stay on.
4. **Fresh-context review before the merge.**

Profiles and setup may change only *how strongly* a human decision is proven: the typed phrase alone, a signed
commit, or a signed commit with a passphrase or `sk-` touch, plus the CI audit. They also change how much
ceremony comes with it. They never change *whether* a gate exists or *who* decides.

## Roadmap

### Phase 1: 0.2.0-alpha.2, "first approved plan in 10 minutes"
**Status:** built as intent `.aiops/0003-guided-setup/` (in review); ships as 0.2.0-alpha.2. Not shipped from this
list: an install-scope choice, and a confirmation inside `init` (setup has it; `init` stays a direct command).
1. **Guided setup: `sdlc setup`.** Stdlib Python, shipped in the plugin, rerunnable, with `--dry-run` and `--yes`.
   - **Preflight:** git, make, python ≥ 3.9, `claude` ≥ 2.1, optional `gh` (auth plus `workflow` scope), and a git
     credential helper.
   - **Inventory:** is the plugin enabled for this user, or offered by the project? Is the repo initialized?
   - **Choose:**
     - a **profile**, which only sets how a human approval is proven. All profiles run the full playbook
       workflow:
       - `solo`: the typed phrase plus a single-file approval commit, no signing
       - `team`: signed approvals with a passphrase key, plus the CI audit
       - `strict`: an `sk-` key only, plus the CI audit
   - **Preview, then one confirmation.** After that, run `sdlc init` and the guided signing steps the human must
     run themselves, then `sdlc doctor`.
   - Reuse `cmd_init` / `cmd_doctor` (`lib/sdlc_engine/cli.py`) and `approve_command()` / `SIGNING_HELP`
     (`lib/sdlc_engine/approvals.py`).
2. **Team auto-install.** `init` writes the declarative snippet into the scaffolded `.claude/settings.json`
   (`templates/scaffold/.claude/settings.json`): `extraKnownMarketplaces.zouj` (github `zoujagger/zouj-ai-sdlc`) and
   `enabledPlugins["zouj-ai-sdlc@zouj"]`. Teammates who open the repo are offered the plugin. The README documents
   it as ECC does.
3. **Explicit consent, ECC-style, without a gateless mode.**
   - Before writing anything, `setup` shows what the gates will enforce: the lock in states 1-3, the human
     approvals, the merge and deploy guards.
   - It asks once to confirm. There is no "advisory" or "no-hooks" profile, because the hooks *are* the playbook
     gates.
   - To try it out, the README shows a throwaway-repo recipe (`git init`, then `sdlc setup --profile solo --yes`).
     There is no sandbox command: building a repo as the human, next to a same-user agent, proved unsafe in review.
4. **A task-first README that follows the playbook.** Put a "Start using" table first:

   | Task | Route |
   |---|---|
   | New feature | `/zouj-ai-sdlc:intent` |
   | Bug or alert | `/zouj-ai-sdlc:triage` → a **new intent** |
   | Failing test | `/zouj-ai-sdlc:fix` (test lock) |
   | Ready for review | `/zouj-ai-sdlc:review` |
   | Where am I? | `/zouj-ai-sdlc:status` |

   Each row names the playbook stage it belongs to. Install comes next, with **pinned** commands. The state machine
   and threat model move to docs.
5. **Support surfaces:**
   - `TROUBLESHOOTING.md`: approval refused, signing, push scope, false-positive blocks
   - `COMMANDS-QUICK-REF.md`
   - `.github/ISSUE_TEMPLATE/install-problem.yml` and `quick-feedback.yml`
   - `sdlc feedback`, which prints the links and sends nothing

### Phase 2: 0.2.0-alpha.3, a safe lifecycle
6. **Install state.** `.aiops/install-state.json` records the plugin version, profile, `ZOUJ_SDLC_REF` and a hash of
   every scaffold file `init` wrote.
7. **`sdlc list-installed | repair | upgrade | uninstall --dry-run`.**
   - `upgrade` diffs the scaffold against the new version, bumps `ZOUJ_SDLC_REF` to a full sha, and runs migrations
     such as `legacy-approvals`.
   - `uninstall` removes only the files that install-state records, never `.aiops/NNNN-*` artifacts.
8. **Rule ids, explanations, and false-positive allowances that can't touch a gate.**
   - Every block message carries an id (`G-ENV-03`), and `sdlc why <id>` explains the reason, the playbook stage it
     protects, and the safe alternative.
   - False positives are handled by a human-owned **exact-command allowance**: `.aiops/config/allowed-commands`,
     under CODEOWNERS. An allowance is refused for any rule that protects a playbook gate: engine calls, approval
     trailers, artifacts and `.aiops/`, the read-only lock, merge and push-to-main, deploy, the test lock, the Stop
     hook.
   - There is no per-rule disable switch.
9. **`/zouj-ai-sdlc:configure`.** An in-plugin skill that runs `sdlc setup` again to change the profile, scope or
   key policy.

### Phase 3: beta, reach
10. **Pinned distribution without npm.**
    - Publish `zouj-ai-sdlc` to PyPI, so `uvx zouj-ai-sdlc@0.2.0b1 setup` or `pipx run …` works.
    - Keep the native `/plugin` path as an equal option.
    - Add an "official sources only" note.
11. **Cross-platform.**
    - macOS: Apple's python3 stub, bash 3.2, BSD `realpath`.
    - Windows: a WSL walkthrough with prerequisite checks.
    - A CI matrix of ubuntu and macos.
12. **A shorter identity.** Add a short alias plugin id or command namespace (for example `/sdlc:intent`) and a
    naming note listing the repo, plugin id and package name, as ECC does. Fill in the marketplace metadata
    (version, category `workflow`, tags, homepage) and add an icon.

### Phase 4: 1.0, optional
13. **Other harnesses**, only if users ask (Codex via `AGENTS.md`). ECC's lesson: give each harness one guided path
    and never stack install methods.

## Verification (per phase)
- **Playbook conformance, in every phase:** a new `tests/test_playbook.py` runs for each profile × scope (`solo`,
  `team`, `strict`) and checks that:
  - a fresh repo walks states 1 → 6 only through the human phrases
  - code is read-only in states 1-3
  - the agent can't approve, merge, push to main or deploy
  - `review.md` is required before state 6
  - an `allowed-commands` entry for a gate rule is rejected

  The `docs/sdlc.md` table is the checklist.
- **Phase 1:**
  - In a clean container, `sdlc setup --dry-run` lists every change and writes nothing.
  - `sdlc setup --profile solo --yes` reaches state 1 in a fresh repo.
  - A second user cloning the repo gets the plugin prompt from `.claude/settings.json`.
- **Phase 2:**
  - `init` → `upgrade` → `uninstall --dry-run` round-trips with only managed files touched.
  - Tests in `tests/test_cli.py` follow the `Init::test_scaffold_pins_and_protects` pattern.
- **Phase 3:** the CI matrix is green on ubuntu and macos, and `uvx zouj-ai-sdlc@<pin> setup --dry-run` works from
  a machine with no clone.
