---
id: 0002
title: Harden gates and guards (review 0001 findings)
status: Draft
spec: ./spec.md
created: 2026-10-30
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-02T09:07:57Z
approved-via: cli
approved-sha256: 7f9279f1447f166093db23cc0640f5977838ed7a61b2aed73f0f6a98a7f65f92
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
- [x] **S7**: The audit verifies allow-listed signers, the base ref and the legacy list
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
- [x] **S8**: Safety guards always on
  - Files:
    - `defaults/secret-paths` (create: the secret globs moved out of `defaults/protected-paths`)
    - `hooks/lib.sh` (modify: `secret_match`)
    - `hooks/guard-bash.sh` `:10` (modify: safety rules unconditional, test-lock rules only when enabled)
    - `hooks/guard-deploy.sh` `:9` (modify: drop the dormancy exit)
    - `hooks/guard-files.sh` `:11` (modify: secret-paths and the credential scan unconditional, protected-paths only when enabled)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_safety_guards_always_on`, replacing `test_dormant_without_aiops`, which today asserts that a force push is allowed
  - Covers: AC-10
- [x] **S9**: Secret reads
  - Files:
    - `hooks/guard-read.sh` (create)
    - `hooks/hooks.json` (modify: `Read|Grep|Glob` matcher)
    - `hooks/guard-bash.sh` `:31` (modify: extend the `re_read_env` readers)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_secret_reads_blocked` → Read of `.env` and `awk 1 .env` are allowed today
  - Covers: AC-11
- [x] **S10**: Scaffold: deny list, pinning, signer stubs
  - Files:
    - `templates/scaffold/.claude/settings.json` (create)
    - `templates/scaffold/.aiops/config/{allowed-signers,legacy-approvals}` (create)
    - `templates/scaffold/.aiops/config.json` (modify: `true`)
    - `templates/scaffold/.github/workflows/{aiops-gates,claude,claude-pr-review,claude-issue-triage,claude-maintain,claude-scheduled-scan,claude-release-notes}.yml` (modify: `ZOUJ_SDLC_REF: __ZOUJ_SDLC_REF__`, a pinned fetch, `--plugin-dir`)
    - `templates/scaffold/.github/CODEOWNERS` (modify: put config.json and config/ on the guard line)
    - `lib/sdlc_engine/cli.py` (modify: `cmd_init` `:245` replaces `__ZOUJ_SDLC_REF__` with `v<plugin.json version>`)
  - Test first: `tests/test_cli.py::Init::test_scaffold_pins_and_protects`
  - Covers: AC-12
- [x] **S11**: State 6 on any branch
  - Files: `lib/sdlc_engine/machine.py` (modify: `_review_state` `:219` drops `current_branch(root) == main`)
  - Test first: `tests/test_engine.py::States::test_done_reported_on_feature_branch_after_merge`
  - Covers: AC-13
- [x] **S12**: Narrow the read-only exemption
  - Files: `defaults/readonly-exempt` (modify: `docs/*`, `README.md`, `*/README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`)
  - Test first: `tests/test_guards.py::EditGuard::test_policy_files_not_exempt` → `CLAUDE.md` is writable in state 1 today
  - Covers: AC-14
- [x] **S13**: Plugin CI: base-engine audit and pinned tools
  - Files:
    - `.github/workflows/ci.yml` (modify: `aiops-gates` runs the `origin/<base>` engine with `--base`; `ruff==0.6.9`; `@anthropic-ai/claude-code@2.1.314`)
    - `.github/CODEOWNERS` (modify)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_ci_pins_tools`, a static check of ci.yml
  - Covers: AC-15
- [x] **S14**: Docs, isolated audit test, 0001 hygiene
  - Files:
    - `SECURITY.md` `:9`
    - `docs/architecture.md` (threat model), `docs/state-machine.md`, `README.md` (signing setup), `templates/scaffold/.aiops/README.md`
    - `tests/test_engine.py` `:177` (isolate the single-file rule)
    - `.aiops/0001-zouj-ai-sdlc-plugin/plan.md` (Deviation log only: the bootstrap exception, the S7 deviation, commit refs)
  - Test first: `tests/test_engine.py::Approvals::test_audit_rejects_multi_file_approval_commit` → the current assertion accepts either message
  - Covers: AC-9, AC-15
- [x] **S15**: This repo's migration and the v0.2.0 release
  - Files: `.claude-plugin/plugin.json` (0.2.0), `CHANGELOG.md` (`[0.2.0]`)
  - **Human**: write `.aiops/config/allowed-signers` with your key, configure SSH signing, and run `sdlc legacy-approvals --write`. These are human-owned guardrail files, so the agent can't write them.
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_version_matches_changelog`
  - Covers: AC-15

<!-- Amendment after review 0002 (CHANGES_REQUESTED 69/100): S16-S24, written in state 3 and needing `Plan Approved 0002` again.
     Order: the BLOCKER first, then the HIGH (key policy, then shell hardening), the MAJORs, LOW, MINOR, and docs last. -->
- [x] **S16**: Heredoc markers only outside quotes and comments
  - Files: `lib/sdlc_engine/guards.py` (modify: `strip_heredocs()` finds markers with a quote- and comment-aware scan of each line)
  - Test first: `tests/test_guards.py::BashGuard::test_heredoc_marker_in_quotes_or_comment` → `echo '<<EOF'` / `# <<EOF`, then `echo 1 > src/app.py`, is allowed today
  - Covers: AC-17
- [x] **S17**: A human for each signature (key policy)
  - Files:
    - `lib/sdlc_engine/approvals.py` (modify: `key_protection(root)` checks for an `sk-` key, an encrypted private key (`ssh-keygen -y -P ""` fails), and that the key isn't in `ssh-add -l`; `signing_problem()` applies it under `approval_key_policy: "human"`)
    - `lib/sdlc_engine/machine.py` (`DEFAULT_CONFIG` `approval_key_policy: "human"`)
    - `lib/sdlc_engine/cli.py` (doctor ✗; the prompt hook's message says "approve in your terminal")
    - `tests/helpers.py` (fixtures opt into `"any"`, since unprotected test keys can't prompt)
  - Test first: `tests/test_engine.py::Approvals::test_key_policy_requires_a_human_per_signature` → an unprotected key passes `signing_problem()` today
  - Covers: AC-16
- [x] **S18**: Engine invocation, the remaining shell forms
  - Files: `lib/sdlc_engine/guards.py` (modify):
    - `ENV_RES`: `export -n`, `declare|typeset +x`, `env -`
    - `ENGINE_RES`: a function or alias whose body calls `sdlc`, `sdlc` followed by a non-literal word, `xargs … sdlc`, copying `bin/sdlc` or `sdlc_engine`
    - the trailer check on `plain` (also `AIOps-` with `Approval` assembled separately)
  - Test first: `tests/test_guards.py::BashGuard::test_engine_cannot_be_disguised_further` → `export -n CLAUDECODE; f(){ sdlc "$@"; }; f approve …` is allowed today
  - Covers: AC-18
- [x] **S19**: The audit fails closed on a bad base; positive test
  - Files:
    - `lib/sdlc_engine/approvals.py` (modify: `trust()` verifies `REF^{commit}`, raising `BaseRefError`; bootstrap only for a resolvable ref with no file)
    - `lib/sdlc_engine/cli.py` (`cmd_validate`: an empty `--base`, or a `BaseRefError`, exits 1)
    - `templates/scaffold/.github/workflows/aiops-gates.yml` (verify `BASE_SHA` like `ci.yml`, fail if absent)
  - Test first: `tests/test_engine.py::Approvals::test_audit_fails_closed_on_unresolvable_base` and `::test_audit_accepts_allow_listed_signer_against_base`, plus `tests/test_cli.py::Lifecycle::test_validate_rejects_empty_base`
  - Covers: AC-19
- [x] **S20**: `.aiops` integrity, the remaining forms
  - Files: `lib/sdlc_engine/guards.py` (modify):
    - expand `$PWD`, `${PWD}`, `$(pwd)` and `~+` in targets
    - glob targets are expanded against the tree
    - `find` start paths that are `.aiops` or an ancestor, with an action and a `-name`/`-path` that can match a `.aiops` entry (or no name filter)
    - `tar -C <dir>` on extract
    - `git apply/am` patches touching `.aiops/`
  - Test first: `tests/test_guards.py::BashGuard::test_aiops_tree_is_protected_from_globs_and_find` → `rm -rf .ai*` etc. are allowed today
  - Covers: AC-20
- [x] **S21**: Secret reads, the remaining forms
  - Files:
    - `hooks/guard-bash.sh` (modify: unquote before matching; drop `.env.(example|sample|template)` tokens instead of exempting the command; glob tokens that match `.env`)
    - `hooks/guard-read.sh` (modify: match the given and the resolved (`realpath -m`) path)
    - `defaults/secret-paths` (add `*id_ed25519*`, `*id_ecdsa*`, `*/.ssh/*`, `*/.aws/credentials`, `*/.netrc`, `*/.npmrc`, `*/secrets/*`)
    - `templates/scaffold/.claude/settings.json` (`Read(~/.ssh/**)`, `Read(~/.aws/**)`)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_secret_reads_blocked_further` → `cp .env /tmp/x; cat .env.example` and a symlink Read are allowed today
  - Covers: AC-21
- [x] **S22**: Legacy list hardening
  - Files:
    - `lib/sdlc_engine/approvals.py` (modify: full 40/64-char exact match; split `audit()` into `commit_problems()` plus the signature check; `unsigned_approvals()` lists only commits with no other problem)
    - `lib/sdlc_engine/cli.py` (`legacy-approvals` prints author and date)
  - Test first: `tests/test_engine.py::Approvals::test_legacy_needs_full_sha_and_clean_commit` → a 7-char prefix passes today
  - Covers: AC-22
- [x] **S23**: Minor bypasses and stale text
  - Files:
    - `hooks/guard-bash.sh` (`git push … +ref` force push)
    - `lib/sdlc_engine/guards.py` (`git --work-tree=DIR` as a git cwd; `curl -o/--output`, `wget -O/--output-document` write targets)
    - `hooks/hooks.json` (the description)
    - `CHANGELOG.md` (env-marker wording)
  - Test first: `tests/test_guards.py::BashGuard::test_minor_write_forms` and `tests/test_shell_hooks.py::ShellHooks::test_guard_bash` (adding `+main`) → allowed today
  - Covers: AC-22
- [x] **S24**: Docs for the key policy and residuals
  - Files: `SECURITY.md`, `docs/architecture.md` (threat model: key policy, regex residuals), `README.md` (approver setup: passphrase, terminal approvals), `templates/scaffold/.aiops/README.md`, `skills/intent|spec|plan/SKILL.md` (the approval phrase falls back to the terminal command), `CHANGELOG.md` `[0.2.0]`
  - Test first: `tests/test_cli.py::Lifecycle::test_prompt_approval_explains_terminal_fallback` → the prompt hook doesn't mention the terminal fallback today
  - Covers: AC-16

<!-- Amendment after review 0002 round 2 (CHANGES_REQUESTED 79/100): S25-S32. HIGHs first, then MEDIUM, MAJORs, LOW/MINOR, docs. -->
- [ ] **S25**: The signing toolchain can't be redirected
  - Files:
    - `lib/sdlc_engine/approvals.py`: the approval commit runs `git -c gpg.format=ssh -c gpg.ssh.program=ssh-keygen -c core.hooksPath=/dev/null commit --no-verify -S` with **no timeout**. `signing_problem()` refuses repo-local `user.signingkey`/`gpg.*`/`core.hooksPath`.
    - `lib/sdlc_engine/machine.py`: `git()` gets an optional timeout.
    - `lib/sdlc_engine/guards.py`: `git config` of those keys, and shell writes under `.git/` or the plugin root, are blocked.
    - `lib/sdlc_engine/cli.py`: doctor flags repo-local overrides, warns when the signing key is also an SSH identity, and its passphrase hint no longer suggests `ssh-add -c`.
  - Test first: `tests/test_engine.py::Approvals::test_signing_toolchain_is_pinned` (a repo-local `gpg.ssh.program` is refused, and a 15 s signer still succeeds) and `tests/test_guards.py::BashGuard::test_signing_toolchain_is_guarded` → allowed today
  - Covers: AC-23
- [ ] **S26**: Shell secret reads beyond `.env`
  - Files:
    - `hooks/guard-bash.sh`: every unquoted, tilde-expanded word is checked against `secret-paths` (templates and `.pub` excepted).
    - `hooks/guard-read.sh`: a Grep/Glob `path` that is a secret directory (`<path>/x` matches `secret-paths`) is blocked.
    - `defaults/secret-paths`: adds `*/.aws/*`, `*/.config/gcloud/*`, `*/.docker/config.json`, `*/.kube/config`.
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_secret_reads_beyond_env` → `cat ~/.aws/credentials` and Grep `path: ~/.ssh` are allowed today
  - Covers: AC-24
- [ ] **S27**: Protected paths apply to shell writes; workflow ownership
  - Files:
    - `lib/sdlc_engine/guards.py`: in initialized repos, shell write targets are checked against `protected-paths`.
    - `templates/scaffold/.github/CODEOWNERS`: adds `/.github/` and `/.claude/`.
  - Test first: `tests/test_guards.py::BashGuard::test_shell_writes_respect_protected_paths` → `sed -i … .github/workflows/aiops-gates.yml` is allowed today
  - Covers: AC-25
- [ ] **S28**: Heredoc scanner skips arithmetic and ANSI-C strings
  - Files: `lib/sdlc_engine/guards.py` (`_heredoc_marks`: skip `$((…))`/`((…))` and `$'…'`)
  - Test first: `tests/test_guards.py::BashGuard::test_heredoc_marker_in_arithmetic_or_ansi_c` → `echo $((1<<EOF))` followed by a write is allowed today
  - Covers: AC-26
- [ ] **S29**: The remaining `.aiops` integrity forms
  - Files: `lib/sdlc_engine/guards.py`:
    - patch headers up to tab or space; `-p0`/`--directory`
    - `git apply`/`am` from stdin is refused in initialized repos
    - tar `-C`/`--directory` in any position; `unzip -d`
    - `find -i*` predicates are case-insensitive
    - brace expansion of targets; `VAR=value` assignments earlier in the same command are substituted
  - Test first: `tests/test_guards.py::BashGuard::test_aiops_integrity_remaining_forms` → `tar -C .aiops -xf x` and `rm -rf {.aiops,x}` are allowed today
  - Covers: AC-27
- [ ] **S30**: Safety variants and false positives
  - Files:
    - `hooks/guard-deploy.sh`: quotes are stripped before matching.
    - `hooks/guard-bash.sh`: force-push checks run on the unquoted copy; also `-[a-z]*f`, and `--mirror`.
    - `lib/sdlc_engine/guards.py`: the dynamic-word rule applies only in command position; a marker in `X=` assignments only; the trailer check matches `AIOps-Approval:` or a `%s`-assembled `AIOps-…:` together with `Approval`.
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_safety_variants` and `tests/test_guards.py::BashGuard::test_no_false_positives` → allowed (or blocked) wrongly today
  - Covers: AC-28
- [ ] **S31**: Legacy recording, `sk-` keys without a touch, CI fails closed
  - Files:
    - `lib/sdlc_engine/approvals.py`: `unsigned_approvals()` lists only commits that are reachable from main and predate the commit introducing `allowed-signers`; `key_protection()` rejects an `sk-` key whose allowed-signers entry has `no-touch-required`.
    - `lib/sdlc_engine/cli.py`: `legacy-approvals --write` confirms each entry; `--yes` skips this.
    - `.github/workflows/ci.yml`: fail closed on an unresolvable base.
  - Test first: `tests/test_engine.py::Approvals::test_legacy_write_only_pre_signing_on_main` and `::test_sk_key_without_touch_rejected`, plus `tests/test_shell_hooks.py::ShellHooks::test_ci_pins_tools` (adding fail-closed) → red today
  - Covers: AC-29
- [ ] **S32**: Docs and plan hygiene
  - Files: `docs/architecture.md` (toolchain row, approval isolation, required workflow, residuals), `README.md` and `SECURITY.md` (signing-key options incl. the `"any"` escape hatch and its cost), `CHANGELOG.md` `[0.2.0]`, `tests/test_engine.py` (blank-line nit), plan Test definitions (the extra round-2 tests)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_docs_state_the_residuals`, a static check that architecture.md lists the toolchain row and the approval-isolation advice → missing today
  - Covers: AC-23

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Signing in the hook fails with no TTY (passphrase key, no agent) | medium | medium | the precheck refuses before stamping and prints the procedure; doctor warns; works with ssh-agent |
| S6 changes every fixture approval, causing broad test churn | high | low | one helper change (key generated per `RepoCase`); old assertions keep their meaning |
| Always-on guards annoy unrelated repos | medium | medium | only deploy, secret, force-push and history rules; lockfile and protected-paths rules stay gated |
| Bootstrap fallback misused to self-trust | low | high | only when the base has **no** signer file, with a loud warning; CODEOWNERS on `.aiops/config/` |
| A mutable tag pin is retagged | low | high | the docs recommend a full sha; tags are never moved |
| The parser gets more complex (`_check_command` is dense) | medium | low | small helpers per write form, each with a test |
| The key policy locks the human out (passphrase key, no TTY in the prompt hook) | high | medium | the refusal says exactly what to do; `bin/sdlc approve` in a terminal prompts for the passphrase; `approval_key_policy: "any"` is the human-owned escape hatch |
| Static shell parsing can never be complete | high | medium | R-10 makes forgery need the human's passphrase or touch, whatever the parser misses. Remaining regex limits are documented as residuals |
| The `find`/glob expansion misjudges | medium | low | it only blocks when `.aiops` entries could match; negative tests for ordinary `find . -name '*.pyc' -delete` |

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

| AC-16 | `tests/test_engine.py::Approvals::test_key_policy_requires_a_human_per_signature`, `tests/test_cli.py::Lifecycle::test_doctor_checks_signing`, `::test_prompt_approval_explains_terminal_fallback` | unit, cli | unprotected or agent-loaded keys refused; an encrypted key not in the agent, or `sk-`, accepted |
| AC-17 | `tests/test_guards.py::BashGuard::test_heredoc_marker_in_quotes_or_comment` | hook | markers inside quotes or comments don't hide later lines |
| AC-18 | `tests/test_guards.py::BashGuard::test_engine_cannot_be_disguised_further` | hook | export -n, declare +x, env -, wrappers, dynamic args, xargs, copies, split trailer |
| AC-19 | `tests/test_engine.py::Approvals::test_audit_fails_closed_on_unresolvable_base`, `::test_audit_accepts_allow_listed_signer_against_base`, `tests/test_cli.py::Lifecycle::test_validate_rejects_empty_base` | unit, cli | fail closed; positive base path |
| AC-20 | `tests/test_guards.py::BashGuard::test_aiops_tree_is_protected_from_globs_and_find` | hook | globs, $PWD, find, tar -C, git apply |
| AC-21 | `tests/test_shell_hooks.py::ShellHooks::test_secret_reads_blocked_further` | hook | compound .env.example, quotes, globs, symlinks, ~/.ssh, nested secrets |
| AC-23 | `tests/test_engine.py::Approvals::test_signing_toolchain_is_pinned`, `tests/test_guards.py::BashGuard::test_signing_toolchain_is_guarded`, `tests/test_shell_hooks.py::ShellHooks::test_docs_state_the_residuals` | unit, hook, static | pinned and hook-less signing without a timeout; repo-local overrides refused; toolchain writes blocked |
| AC-24 | `tests/test_shell_hooks.py::ShellHooks::test_secret_reads_beyond_env` | hook | any secret-paths word in the shell; directory Grep/Glob |
| AC-25 | `tests/test_guards.py::BashGuard::test_shell_writes_respect_protected_paths`, `tests/test_cli.py::Init::test_scaffold_pins_and_protects` | hook, cli | protected paths for shell writes; CODEOWNERS for /.github/ and /.claude/ |
| AC-26 | `tests/test_guards.py::BashGuard::test_heredoc_marker_in_arithmetic_or_ansi_c` | hook | arithmetic and ANSI-C `<<` aren't markers |
| AC-27 | `tests/test_guards.py::BashGuard::test_aiops_integrity_remaining_forms` | hook | patches, tar, unzip, -iname, braces, variables |
| AC-28 | `tests/test_shell_hooks.py::ShellHooks::test_safety_variants`, `tests/test_guards.py::BashGuard::test_no_false_positives` | hook | quoted prod, '+main', -fu, --mirror; no false positives |
| AC-29 | `tests/test_engine.py::Approvals::test_legacy_write_only_pre_signing_on_main`, `::test_sk_key_without_touch_rejected`, `tests/test_shell_hooks.py::ShellHooks::test_ci_pins_tools` | unit, static | legacy recording limits; sk no-touch; CI fails closed |
| AC-22 | `tests/test_engine.py::Approvals::test_legacy_needs_full_sha_and_clean_commit`, `tests/test_guards.py::BashGuard::test_minor_write_forms`, `tests/test_shell_hooks.py::ShellHooks::test_guard_bash` | unit, hook | full-sha legacy, vetted --write, +refspec, --work-tree, curl -o |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-11-02 | S6 | The existing audit signature check got the working-tree signer list early, so `make check` stayed green | signing became the default before S7 rewrote the audit | `f3e558f` |
| 2026-11-02 | S7 | A test that picked a base predating `allowed-signers` was corrected to use a base that has one | the bootstrap rule (by design) trusts the PR's list when the base has none | `6d77010` |
| 2026-11-02 | S12 | Two tests that used a root `NOTES.md` as their docs example now use `docs/notes.md` | the narrowed exemption no longer covers arbitrary root `*.md` | `783a908` |
| 2026-11-02 | S14 | `sdlc doctor` signing checks (in the spec's API contracts, not listed as a plan step) were added in S14. The isolated audit test pinned existing behaviour, so it had no red | complete the spec's contract; be honest about test-first evidence | `8524464` |
| 2026-11-02 | S6 | Eval fixtures (`evals/_lib/repo.sh`) got throwaway signing keys too | the evals approve gates and signing became the default | `f3e558f` |
| 2026-11-02 | S8 | `aiops_enabled` gained the git-tracked check in S8 (planned for S3 only in the engine). The planned `secret_match` became `config_match … secret-paths` + `secret_template` | reuse the existing helper | `940c7e1` |
| 2026-11-02 | S10 | Also created `templates/scaffold/.aiops/config/secret-paths` (not in S10's file list) | consumers need the extension point for the new list | `5710883` |
| 2026-11-02 | S9, S15 | `hooks/hooks.json` and `.claude-plugin/plugin.json` were rewritten by `json.dump` (reformatting churn; plugin.json now uses `\u2192` escapes) | edited programmatically; S23 restores readable formatting | `98e696c`, `f5ec258` |
| 2026-11-02 | — | Review 0002 returned CHANGES_REQUESTED (69/100). The spec was amended (R-10, R-11, AC-16..AC-22) and re-approved; the plan was amended with S16-S24 | fix all findings, as the human asked | `fbd1da2`, `3210a8e` |
| 2026-11-02 | S17, S19, S21, S24 | Unlogged in round 1: S17 touched `evals/_lib/repo.sh` and `tests/test_cli.py` (not `cli.py`); S19 added `test_scaffold_gate_verifies_base`; S21 touched `hooks/lib.sh`; S24 changed `approve()`'s refusal text and edited `skills/init`, `skills/using-zouj-ai-sdlc` | found by review round 2 | `de58a62`, `f1e5c0e`, `d35068d`, `ecd8f70` |
| 2026-11-02 | — | **Human decision:** this repo uses `approval_key_policy: "any"` with the existing passphrase-less key instead of a dedicated or protected signing key ("keep commit simple"). Approvals go through `!` again. Residual: anything running as the user can sign approvals here | human-owned config, set by zoujagger in a signed commit | `c74a836` |
| 2026-11-02 | — | Review round 2 returned CHANGES_REQUESTED (79/100). The spec was amended (R-12, AC-23..AC-29) and re-approved; the plan was amended with S25-S32 | the human chose to fix round 2 inside 0002 | `0ee464b`, `d8f1f54`, `8185ac6` |
