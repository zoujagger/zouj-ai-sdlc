---
id: 0002
title: Harden gates and guards (review 0001 findings)
status: Approved
spec: ./spec.md
created: 2026-10-30
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-02T08:24:42Z
approved-via: cli
approved-sha256: ff4d1d96e65daefe56c0b490ccb863739f557551aa6206832b324603217623a7
---

# Plan: Harden gates and guards (review 0001 findings)

<!-- State 3 PLAN, produced read-only. Each step is one TDD cycle. The commit body carries
     `Red: <failing test + reason>` and `Green: make check passed`. -->

## Approach
Close the BLOCKER first (heredoc parsing), then the rest of the shell parser, then `.aiops` integrity. All three live
in `lib/sdlc_engine/guards.py` and share one test pattern (`tests/test_guards.py` `BashGuard`).

Then the HIGH, in two steps: signing at approval time, then verification in the audit. Signing changes how every test
fixture approves, so S6 first gives `tests/helpers.py` a throwaway ed25519 key. ssh-keygen and git 2.53 are present,
and SSH signing needs git ≥ 2.34.

Then the hook-layer changes (always-on safety, the read guard). Then scaffold and pinning, the small fixes, docs and
hygiene, and last this repo's own migration and the release.

The existing pieces are reused, not rewritten:
- `tokenize/segments/_strip_prefix/write_targets` (`guards.py:148-224`)
- `_check_command` (`guards.py:269`)
- `approvals.audit` (`approvals.py:75`)
- `machine.gate` (`machine.py:114`)
- `hooks/lib.sh` `config_match`

**Bootstrap rule (from AC-9 and AC-15).** CI reads `allowed-signers` and `legacy-approvals` from `--base REF`. When
the base ref has no `allowed-signers` file at all, the audit falls back to the PR tree and prints a WARNING that a
signer list is being introduced and needs CODEOWNERS review. This only happens on the PR that first adds signing.

## Steps
- [x] **S1**: Heredoc stripping keeps the marker line
  - Files: `lib/sdlc_engine/guards.py` (modify: replace `HEREDOC_RE` at `:123` and its use at `:149` with a line-based `strip_heredocs()`)
  - Test first: `tests/test_guards.py::BashGuard::test_heredoc_redirect_after_marker` → `cat <<EOF > src/app.py` is allowed today
  - Covers: AC-1, AC-2
- [x] **S2**: More shell write forms
  - Files: `lib/sdlc_engine/guards.py` (modify):
    - `write_targets` `:206`: `cp/mv -t`, `--target-directory`, `find -delete/-exec/-execdir/-ok`, `awk -i inplace`
    - `_git_sub` `:227` returns `-C` dir
    - `_check_command`: git paths resolved against `-C`, and `git commit <pathspec>`
  - Test first: `tests/test_guards.py::BashGuard::test_more_write_forms_while_locked` → all six forms allowed today
  - Covers: AC-3
- [x] **S3**: `.aiops` integrity
  - Files:
    - `lib/sdlc_engine/guards.py` (modify: new `_aiops_protected(rel)`, covering `.aiops`, intent dirs and their contents, applied to shell targets and git rm/mv)
    - `lib/sdlc_engine/machine.py` (modify: `initialized()` `:47` also `git ls-files .aiops`)
    - `hooks/engine.sh` (modify: same tracked-in-git check)
  - Test first:
    - `tests/test_guards.py::BashGuard::test_aiops_tree_is_protected` → `rm -r .aiops` allowed in state 4 today
    - `tests/test_engine.py::States::test_initialized_when_tracked_but_missing`
  - Covers: AC-4, AC-5
- [x] **S4**: Bind gates to the folder id
  - Files:
    - `lib/sdlc_engine/machine.py` (modify: `gate()` `:114` requires front `id` == folder id)
    - `lib/sdlc_engine/guards.py` (modify: `check_artifact` `:88` blocks changing `id`)
  - Test first:
    - `tests/test_engine.py::States::test_copied_folder_does_not_open_gates`
    - `tests/test_guards.py::EditGuard::test_id_is_immutable`
  - Covers: AC-6
- [x] **S5**: Engine invocation can't be disguised
  - Files: `lib/sdlc_engine/guards.py` (modify):
    - replace the `ENGINE_RE` text match `:145` with token checks after unquoting
    - dynamic command words
    - `CLAUDECODE` / `CLAUDE_CODE_CHILD_SESSION` unset or override
  - Test first: `tests/test_guards.py::BashGuard::test_engine_cannot_be_disguised` → `sdl\c approve`, `s=sdlc; $s approve` and `env -u CLAUDECODE …` are allowed today
  - Covers: AC-7
- [x] **S6**: Signed approvals at approval time
  - Files:
    - `lib/sdlc_engine/machine.py` (modify: `DEFAULT_CONFIG` `:28` `require_signed_approvals: True`)
    - `lib/sdlc_engine/approvals.py` (modify: `approve()` `:27` signing precheck before stamping, then `git commit -S`)
    - `tests/helpers.py` (modify: `RepoCase` generates an ed25519 key, sets `gpg.format=ssh` and `user.signingkey`, writes `.aiops/config/allowed-signers`)
  - Test first: `tests/test_engine.py::Approvals::test_refuses_without_signing_key_before_stamping` and `::test_approval_commit_is_signed`
  - Covers: AC-8
- [ ] **S7**: The audit verifies allow-listed signers, the base ref and the legacy list
  - Files:
    - `lib/sdlc_engine/approvals.py` (modify: `audit(root, d, kind, base=None)` `:75` with `%G?`/`%GF` through a temporary `gpg.ssh.allowedSignersFile` from the base ref, the legacy list, and the bootstrap rule)
    - `lib/sdlc_engine/cli.py` (modify: `cmd_validate` `:166` `--base`; new human-only `cmd_legacy_approvals`; `COMMANDS`, `USAGE`, `HUMAN_ONLY` list)
  - Test first: `tests/test_engine.py::Approvals::test_audit_requires_allow_listed_signer`, covering four cases:
    1. unsigned → fail
    2. unlisted key → fail
    3. key added by the PR with `--base` → fail
    4. listed key / legacy sha → pass

    Plus `tests/test_cli.py::Lifecycle::test_legacy_approvals_is_human_only`
  - Covers: AC-9
- [ ] **S8**: Safety guards always on
  - Files:
    - `defaults/secret-paths` (create: the secret globs moved out of `defaults/protected-paths`)
    - `hooks/lib.sh` (modify: `secret_match`)
    - `hooks/guard-bash.sh` `:10` (modify: safety rules unconditional, test-lock rules only when enabled)
    - `hooks/guard-deploy.sh` `:9` (modify: drop the dormancy exit)
    - `hooks/guard-files.sh` `:11` (modify: secret-paths and the credential scan unconditional, protected-paths only when enabled)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_safety_guards_always_on`, replacing `test_dormant_without_aiops`, which today asserts that a force push is allowed
  - Covers: AC-10
- [ ] **S9**: Secret reads
  - Files:
    - `hooks/guard-read.sh` (create)
    - `hooks/hooks.json` (modify: `Read|Grep|Glob` matcher)
    - `hooks/guard-bash.sh` `:31` (modify: extend the `re_read_env` readers)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_secret_reads_blocked` → Read of `.env` and `awk 1 .env` are allowed today
  - Covers: AC-11
- [ ] **S10**: Scaffold: deny list, pinning, signer stubs
  - Files:
    - `templates/scaffold/.claude/settings.json` (create)
    - `templates/scaffold/.aiops/config/{allowed-signers,legacy-approvals}` (create)
    - `templates/scaffold/.aiops/config.json` (modify: `true`)
    - `templates/scaffold/.github/workflows/{aiops-gates,claude,claude-pr-review,claude-issue-triage,claude-maintain,claude-scheduled-scan,claude-release-notes}.yml` (modify: `ZOUJ_SDLC_REF: __ZOUJ_SDLC_REF__`, a pinned fetch, `--plugin-dir`)
    - `templates/scaffold/.github/CODEOWNERS` (modify: put config.json and config/ on the guard line)
    - `lib/sdlc_engine/cli.py` (modify: `cmd_init` `:245` replaces `__ZOUJ_SDLC_REF__` with `v<plugin.json version>`)
  - Test first: `tests/test_cli.py::Init::test_scaffold_pins_and_protects`
  - Covers: AC-12
- [ ] **S11**: State 6 on any branch
  - Files: `lib/sdlc_engine/machine.py` (modify: `_review_state` `:219` drops `current_branch(root) == main`)
  - Test first: `tests/test_engine.py::States::test_done_reported_on_feature_branch_after_merge`
  - Covers: AC-13
- [ ] **S12**: Narrow the read-only exemption
  - Files: `defaults/readonly-exempt` (modify: `docs/*`, `README.md`, `*/README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`)
  - Test first: `tests/test_guards.py::EditGuard::test_policy_files_not_exempt` → `CLAUDE.md` is writable in state 1 today
  - Covers: AC-14
- [ ] **S13**: Plugin CI: base-engine audit and pinned tools
  - Files:
    - `.github/workflows/ci.yml` (modify: `aiops-gates` runs the `origin/<base>` engine with `--base`; `ruff==0.6.9`; `@anthropic-ai/claude-code@2.1.314`)
    - `.github/CODEOWNERS` (modify)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_ci_pins_tools`, a static check of ci.yml
  - Covers: AC-15
- [ ] **S14**: Docs, isolated audit test, 0001 hygiene
  - Files:
    - `SECURITY.md` `:9`
    - `docs/architecture.md` (threat model), `docs/state-machine.md`, `README.md` (signing setup), `templates/scaffold/.aiops/README.md`
    - `tests/test_engine.py` `:177` (isolate the single-file rule)
    - `.aiops/0001-zouj-ai-sdlc-plugin/plan.md` (Deviation log only: the bootstrap exception, the S7 deviation, commit refs)
  - Test first: `tests/test_engine.py::Approvals::test_audit_rejects_multi_file_approval_commit` → the current assertion accepts either message
  - Covers: AC-9, AC-15
- [ ] **S15**: This repo's migration and the v0.2.0 release
  - Files: `.claude-plugin/plugin.json` (0.2.0), `CHANGELOG.md` (`[0.2.0]`)
  - **Human**: write `.aiops/config/allowed-signers` with your key, configure SSH signing, and run `sdlc legacy-approvals --write`. These are human-owned guardrail files, so the agent can't write them.
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_version_matches_changelog`
  - Covers: AC-15

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Signing in the hook fails with no TTY (passphrase key, no agent) | medium | medium | the precheck refuses before stamping and prints the procedure; doctor warns; works with ssh-agent |
| S6 changes every fixture approval, causing broad test churn | high | low | one helper change (key generated per `RepoCase`); old assertions keep their meaning |
| Always-on guards annoy unrelated repos | medium | medium | only deploy, secret, force-push and history rules; lockfile and protected-paths rules stay gated |
| Bootstrap fallback misused to self-trust | low | high | only when the base has **no** signer file, with a loud warning; CODEOWNERS on `.aiops/config/` |
| A mutable tag pin is retagged | low | high | the docs recommend a full sha; tags are never moved |
| The parser gets more complex (`_check_command` is dense) | medium | low | small helpers per write form, each with a test |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_guards.py::BashGuard::test_heredoc_redirect_after_marker` | hook | redirect after the heredoc marker is blocked while locked, body `>` ignored |
| AC-2 | `tests/test_guards.py::BashGuard::test_heredoc_redirect_after_marker` | hook | heredoc writes to artifacts/state/config are blocked in state 4 |
| AC-3 | `tests/test_guards.py::BashGuard::test_more_write_forms_while_locked` | hook | the six write forms are blocked |
| AC-4 | `tests/test_guards.py::BashGuard::test_aiops_tree_is_protected` | hook | rm/mv/cp/rmdir on the `.aiops` tree are blocked in every state |
| AC-5 | `tests/test_engine.py::States::test_initialized_when_tracked_but_missing` | unit | tracked-but-missing `.aiops` still counts as initialized and locked |
| AC-6 | `tests/test_engine.py::States::test_copied_folder_does_not_open_gates`, `tests/test_guards.py::EditGuard::test_id_is_immutable` | unit, hook | id binding |
| AC-7 | `tests/test_guards.py::BashGuard::test_engine_cannot_be_disguised` | hook | quoted, escaped, dynamic and env-cleared engine calls are blocked |
| AC-8 | `tests/test_engine.py::Approvals::test_refuses_without_signing_key_before_stamping`, `::test_approval_commit_is_signed` | unit | precheck before stamping; signed commit |
| AC-9 | `tests/test_engine.py::Approvals::test_audit_requires_allow_listed_signer`, `::test_audit_rejects_multi_file_approval_commit`, `tests/test_cli.py::Lifecycle::test_legacy_approvals_is_human_only` | unit, cli | allow-listed signer from the base ref; legacy list; human-only |
| AC-10 | `tests/test_shell_hooks.py::ShellHooks::test_safety_guards_always_on` | hook | safety guards on without `.aiops/`; gates still dormant |
| AC-11 | `tests/test_shell_hooks.py::ShellHooks::test_secret_reads_blocked` | hook | Read/Grep/Glob and shell readers of secrets are blocked; `.env.example` allowed |
| AC-12 | `tests/test_cli.py::Init::test_scaffold_pins_and_protects` | cli | deny list, `ZOUJ_SDLC_REF: v<version>`, signer stubs, signed default, no overwrite |
| AC-13 | `tests/test_engine.py::States::test_done_reported_on_feature_branch_after_merge` | unit | state 6 on any branch |
| AC-14 | `tests/test_guards.py::EditGuard::test_policy_files_not_exempt` | hook | CLAUDE.md, REVIEW.md, skills and agents locked; docs and README writable |
| AC-15 | `tests/test_shell_hooks.py::ShellHooks::test_ci_pins_tools`, `::test_version_matches_changelog`, plus CI `sdlc validate --all --ci --base origin/main` | static, CI | this repo passes the strict audit at 0.2.0 |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
