---
id: 0002
verdict: PASS
commit: 49a8d7b48613dfe5d3d8dceda10b9fbd56f8eca9
score: 90/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-03
---

# Review: Harden gates and guards (review 0001 findings), final (rounds 4-7)

<!-- State 5 PRE-REVIEW. Compiled only from the fresh-context persona reports of rounds 4-7 (base main @ c26f691):
     verifier round 6 (VERIFIED at 927fcab), code reviewer round 6 (at 68ee504), security reviewer round 7 (at 68ee504).
     Round 3 (73/100, CHANGES_REQUESTED) is in git history. Two commits landed after the reports: 5bfec52 (the
     $HOME write-target MEDIUM both reviewers raised, with its proof test red on the parent) and 49a8d7b (CHANGELOG
     known issues and the Deviation log). The human decides the merge. -->

## Summary
The hardening release ships as **0.2.0-alpha.1** (experimental), as the human asked. Every round-3 and later BLOCKER,
HIGH and MAJOR is fixed and was confirmed independently.
- **Checks:** `make check` passes (115 tests), and `make build` (`claude plugin validate .`) passes with the known
  warnings: CLAUDE.md at the root, no icon.
  - `validate --all --ci --base origin/main` exits 0. It prints the bootstrap warning: `origin/main` has no
    `allowed-signers`, so this PR's signer list needs CODEOWNERS review.
  - Hooks run in about 60 ms (guard-bash) and about 97 ms (engine pre-bash).
- **ACs:** all 29 are met with passing tests. AC-15 is met through the logged alpha decision.
- **Red-first:** every review-fix commit carries `Red:`/`Green:` lines. The reviewers reproduced red on the parent
  commit for each proof test.
- **Security:** PASS, 0 critical/high.
  - The approval commit is built with plumbing, by absolute git, ssh-keygen and python, and no hook, fsmonitor or
    filter runs inside it.
  - Repo-local config is limited to an allow-list.
  - The agent can't write the toolchain: global git config, shell startup files, PATH directories, installed plugins.
  - Shell secret reads are checked word by word in one Python pass.
- **Accepted residuals (human decisions, Deviation log):**
  - This repo keeps `"approval_key_policy": "any"`, so a shell-parser bypass can forge an approval *here*. Under the
    plugin default `"human"`, a forgery still needs the human's passphrase or touch.
  - The remaining MINOR and LOW forms are listed as known issues in CHANGELOG for 0.2.0-alpha.2.

Verdict: **PASS, 90/100.**
- Verifier: VERIFIED.
- Security reviewer: PASS (21/25).
- Code reviewer: no BLOCKER or MAJOR (36 + 19 + 10 + 4).

## Spec conformance
| AC | Verdict | Evidence (test) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_guards.py::BashGuard::test_heredoc_redirect_after_marker` |
| AC-2 | ✅ met | `test_heredoc_redirect_after_marker` (state 4: artifact, `state/active`, `config.json`) |
| AC-3 | ✅ met | `test_more_write_forms_while_locked` |
| AC-4 | ✅ met | `test_aiops_tree_is_protected` |
| AC-5 | ✅ met | `tests/test_engine.py::States::test_initialized_when_tracked_but_missing`, `tests/test_shell_hooks.py::ShellHooks::test_engine_wrapper_stays_on_when_aiops_is_tracked_but_deleted` |
| AC-6 | ✅ met | `test_copied_folder_does_not_open_gates`, `test_id_is_immutable` |
| AC-7 | ✅ met | `test_engine_cannot_be_disguised`, `test_wrapped_engine_calls`, `test_engine_call_forms_round4`, `test_review_round5_forms`, `test_review_round6_forms` |
| AC-8 | ✅ met | `test_refuses_without_signing_key_before_stamping`, `test_approval_commit_is_signed` |
| AC-9 | ✅ met | `test_audit_requires_allow_listed_signer`, `test_audit_rejects_multi_file_approval_commit`, `tests/test_cli.py::Lifecycle::test_legacy_approvals_is_human_only` |
| AC-10 | ✅ met | `test_safety_guards_always_on` |
| AC-11 | ✅ met | `test_secret_reads_blocked`, `test_secret_reads_through_globs_and_substitutions` (`cat -b .env` etc.) |
| AC-12 | ✅ met | `tests/test_cli.py::Init::test_scaffold_pins_and_protects` |
| AC-13 | ✅ met | `test_done_reported_on_feature_branch_after_merge` |
| AC-14 | ✅ met | `test_policy_files_not_exempt` |
| AC-15 | ✅ met | `test_ci_pins_tools`, `test_version_matches_changelog` (0.2.0-alpha.1, logged human decision), strict `validate --all --ci --base origin/main` exits 0 |
| AC-16 | ✅ met | `test_key_policy_requires_a_human_per_signature`, `test_doctor_checks_signing`, `test_prompt_approval_explains_terminal_fallback` |
| AC-17 | ✅ met | `test_heredoc_marker_in_quotes_or_comment` |
| AC-18 | ✅ met | `test_engine_cannot_be_disguised_further`, `test_wrapped_engine_calls` (variable-built trailer) |
| AC-19 | ✅ met | `test_audit_fails_closed_on_unresolvable_base`, `test_audit_accepts_allow_listed_signer_against_base`, `test_validate_rejects_empty_base`, `test_audit_bootstraps_when_base_has_no_signer_list` |
| AC-20 | ✅ met | `test_aiops_tree_is_protected_from_globs_and_find` |
| AC-21 | ✅ met | `test_secret_reads_blocked_further` |
| AC-22 | ✅ met | `test_legacy_needs_full_sha_and_clean_commit`, `test_minor_write_forms`, `test_guard_bash` |
| AC-23 | ✅ met | `test_signing_toolchain_is_pinned`, `test_signing_toolchain_is_guarded`, `test_repo_local_config_is_allow_listed`, `test_approval_runs_no_monitor_or_filter`, `test_engine_runs_git_by_absolute_path`, `test_docs_state_the_residuals` |
| AC-24 | ✅ met | `test_secret_reads_beyond_env`, `test_secret_reads_through_globs_and_substitutions`, `test_secret_uploads_and_credential_printers` |
| AC-25 | ✅ met | `test_shell_writes_respect_protected_paths`, `test_review_round3_minor_forms` (checkout/restore), `test_scaffold_pins_and_protects` |
| AC-26 | ✅ met | `test_heredoc_marker_in_arithmetic_or_ansi_c` |
| AC-27 | ✅ met | `test_aiops_integrity_remaining_forms`, `test_review_round3_minor_forms` |
| AC-28 | ✅ met | `test_safety_variants`, `test_no_false_positives`, `test_engine_call_forms_round4` (false positives) |
| AC-29 | ✅ met | `test_legacy_write_only_pre_signing_on_main`, `test_sk_key_without_touch_rejected`, `test_ci_pins_tools` |

## Security
- **Verdict:** PASS (0 critical/high), 21/25.
- **Re-tests:** every round-6 finding was re-tested against the live hooks and is fixed. That covers directory
  and symlinked toolchain targets, PATH directories, absolute git/python/ssh-keygen, the approve command, credential
  printers, `rg -.` and curl `<`/`@` uploads.
- **[MEDIUM, fixed in `5bfec52`]** `$HOME`/`${HOME}` in shell write targets bypassed the out-of-repo guards.
  `test_review_round6_forms` goes red on the parent and green at HEAD.
- **[LOW] Known issues for alpha.2 (CHANGELOG):**
  - A PATH directory created in the same command.
  - Approve calls assembled after a variable assignment (they still need the human under `"human"`).
  - `~/.zlogin` and `~/.inputrc`.
  - More credential printers: `op item get`, `vault read`, `kubectl get secret -o yaml`, and others.
  - `--data-urlencode name@file`.
- **Accepted residual:** this repo's `"approval_key_policy": "any"`, by human decision.

Spec flags:

| Flag | Mitigated? |
|---|---|
| Signing-key access | **yes** for the documented scope. The key policy refuses passphrase-less, agent-loaded and `no-touch-required` keys. The commit is built with plumbing, by absolute tools. The same-user residual is documented ("Approval isolation"). This repo uses `any` by human decision. |
| Self-trust | **yes**: signers, legacy list and config are read from the base ref, and the audit fails closed. The PR's own workflow running is a documented residual. |
| Legacy loophole | **yes**: only main ancestors that predate signing, full shas, confirmed per entry, read from the base. |
| Secret reads | **yes, with LOW gaps** (known issues) |
| Supply chain | **yes**; a mutable tag is the documented residual |

## Plan conformance
- All 32 steps are ticked, and the diff matches the file lists.
- The review fixes (rounds 3-7) were made in state 5 as review-fix commits by human decision, so the plan approval
  holds.
- Every deviation is in the Deviation log with its commit, including:
  - the plumbing approval commit
  - the `shell.py` and `secret_scan.py` modules
  - R-12's ancestor rule (one level, outside the repo for Grep/Glob)
  - `timeout 30 $X close` kept blocked
  - the alpha version
- Nothing out of scope ships.

## Test-first evidence
- Every S1-S32 step and every review-fix commit carries `Red:`/`Green:` lines. The test count climbs from 59 to 115.
- In rounds 4-7, the reviewers ran each review-fix proof test against its parent commit in a temporary worktree.
  All of them failed with the recorded assertions and pass at HEAD.
- `5bfec52`'s proof test was confirmed red on its parent before the commit.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 36 | All ACs met. A few round-5 forms are only partly closed (known issues). |
| Security | 25 | 21 | 0 critical/high; the MEDIUM is fixed; LOW gaps are known issues |
| Test quality & test-first | 20 | 19 | Red on the parent for every proof test. Symlinked files and uninitialized repos aren't covered for toolchain shell writes. |
| Plan conformance | 10 | 10 | Every deviation logged with commits |
| Maintainability | 5 | 4 | The toolchain check exists in both bash and Python; the credential-printer list is regex-heavy |
| **Total** | 100 | **90** | **PASS**: ≥ 80, no BLOCKER, no CRITICAL/HIGH, every AC met |

### Before merging (human)
1. CODEOWNERS review of `.aiops/config/`. This is the bootstrap PR, so CI trusts its signer list.
2. Accept the documented alpha known issues, or ask for alpha.2 first.
