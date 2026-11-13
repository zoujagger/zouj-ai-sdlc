---
id: 0007
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: a693a2f86ef28c8ccd98faaf388ea33a69a1ea60
score: 89/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-13
---

# Review: First run in five minutes (profile by /setup, terminal command, core scaffold)

<!-- State 5 PRE-REVIEW. Written from the reports of three fresh-context personas that did not write the code.
     Rounds 1-3 (87d3ac8, ccef62e, 7437154) reviewed the `Setup Profile` phrase: PASS 86, 88, 92. After round 3 the
     human removed the phrase and amended intent, spec and plan (S14-S20: the typed `/zouj-ai-sdlc:setup <profile>`,
     which in a fresh repo also writes the core scaffold). Round 4 at a693a2f (this file). Diff against origin/main;
     the style-only commit 7d8d4d0 changes no engine syntax tree (both reviewers checked). -->

## Summary
0007 adds three things:
- **Profile by the typed setup command.** The human types `/zouj-ai-sdlc:setup solo|team|strict`. In a repo
  without `.aiops/`, the prompt hook first writes the core scaffold (missing files only). Then it sets the first
  profile and commits `.aiops/config.json` alone. The `Setup Profile` phrase is gone.
- **`sdlc where`.** It prints the terminal command, and the state card shows it.
- **A core-only scaffold.** The default installs only `core`; the other parts are opt in with `--with`.

It ships as 0.2.0-alpha.4.

Round 4 results:
- **Verifier:** VERIFIED. All 23 ACs have passing tests. `make check` (415 tests) and `make build` pass.
- **Code-reviewer:** 89/100, no BLOCKER.
- **Security-reviewer:** PASS, 22/25, no CRITICAL or HIGH.

**Verdict: CHANGES_REQUESTED**, for one reason. The code-reviewer's HIGH: the live check that Claude Code hands
`UserPromptSubmit` the typed `/zouj-ai-sdlc:setup solo` line, not the expanded skill, was never run. The whole
feature rests on it, and every automated test feeds the hook a payload directly. The verifier flags the same gap.
One MEDIUM (an untested refusal path) is also worth closing before the merge. The human decides.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:1186 FirstProfile::test_sets_and_commits_config_alone`; `tests/test_cli.py:531 SetupCommand::test_whole_prompt_sets_the_profile` |
| AC-2 | ✅ met | `tests/test_playbook.py:344-387 CommandWalk::test_solo` (fresh repo, every prompt through `engine.sh` with both markers) |
| AC-3 | ✅ met | `tests/test_setup.py:1233`, `:1238`, `:1249`, `:1260`; `tests/test_cli.py:570` (outside the session repo; an empty `CLAUDE_PROJECT_DIR` fails closed) |
| AC-4 | ✅ met | `tests/test_cli.py:544`, `:561`; `tests/test_shell_hooks.py:717-728` |
| AC-5 | ✅ met | `tests/test_shell_hooks.py:691 test_prompt_hook_dormant_except_the_setup_command` (a fake plugin logs every python start) |
| AC-6 | ✅ met | `tests/test_cli.py:591`; `tests/test_playbook.py:354-361` |
| AC-7 | ✅ met | `tests/test_cli.py:613` |
| AC-8 | ✅ met | `tests/test_setup.py:1325`, `:1332` (terminal `--profile` × 3), `:1346`, `:1138`. Byte equality holds by construction; the test compares parsed JSON |
| AC-9 | ✅ met | `tests/test_cli.py:667 Where::test_first_line_is_the_terminal_command` |
| AC-10 | ✅ met | `tests/test_cli.py:714`, `:731`, `:740`, `:757` |
| AC-11 | ✅ met | `tests/test_cli.py:412`; `tests/test_setup.py:973` |
| AC-12 | ✅ met | `tests/test_cli.py:421`, `:431`, `:436`, `:447`; `tests/test_setup.py:1008`, `:1023` |
| AC-13 | ✅ met | `tests/test_lifecycle.py:757-786`; `tests/test_playbook.py:193` |
| AC-14 | ✅ met | `tests/test_lifecycle.py:707`, `:729`; `tests/test_cli.py:454`, `:461` |
| AC-15 | ✅ met | `tests/test_lifecycle.py:829-850` |
| AC-16 | ✅ met | `tests/test_playbook.py:338 CoreWalk`, `:344 CommandWalk` × solo/team/strict |
| AC-17 | ✅ met | `tests/test_cli.py:780` |
| AC-18 | ⚠️ partial | `tests/test_cli.py:792`, `:809`, `:825`, `:836`; `tests/test_setup.py:895`. The AC says no shipped file mentions `Setup Profile`, but R-4 requires the commit title `chore(aiops): Setup Profile <name>`, which README, SECURITY.md, the architecture and the ADR quote. The test exempts the title. The human accepts the exemption or amends the AC |
| AC-19 | ✅ met | `tests/test_cli.py:883`; `tests/test_rules.py:326`; `make build` passes |
| AC-20 | ✅ met | `tests/test_cli.py:470`, `:485`; `tests/test_setup.py:1032` |
| AC-21 | ✅ met (run quoted below) | `tests/test_cli.py:913 Docs::test_profile_eval_case_is_complete` |
| AC-22 | ⚠️ partial | `tests/test_setup.py:1076`, `:1103`. Nothing pins the exact paths inside the scaffold commit command (only `git add -- ` and each path somewhere in the reply) |
| AC-23 | ✅ met | `tests/test_setup.py:1115` (not a git repo, `$HOME`, `GIT_DIR`, no `make`) |

**AC-21: the run** (plan.md Deviation log, S19, 2026-11-13): `claude plugin eval … --allow-tools Bash Write Edit
--case profile-by-setup-command --runs 3`.
- **With the plugin:** 1.00 (asks-for-setup-command PASS ×3, config-unchanged ✓ ×3).
- **Without the plugin:** 0.67.
- Δ +0.33, $0.87, 93 s.

## Security
- [MEDIUM, accepted residual] `lib/sdlc_engine/cli.py:932-954`; no rule in `guards.py`.
  - **Exploit:** an agent runs `claude -p "/zouj-ai-sdlc:setup solo"` in a repo with no profile and nothing approved.
    The child session's hook can't tell that from a human, so it scaffolds and commits `solo`. Then
    `claude -p "Intent Approved 0001"` and the next phrases open the gates unsigned.
  - **Bounds:** one visible commit; CI reads the base branch's config and CODEOWNERS.
  - **Status:** recorded in the spec and in Known gaps.
  - **Fix (backlog, R-22):** a pre-bash rule refusing `claude` when its prompt matches `APPROVE_RE` or
    `PROFILE_RE`.
- [LOW] `lib/sdlc_engine/setup.py:802` with `approvals.py:28-31`: `Set-By:` reads `user.name`, which the agent can
  set in a fresh repo's local config before `.aiops/` exists. This misleads attribution only (unsigned, opens no
  gate); `approved-by` has the same class. → Read the global identity, or flag a repo-local one.
- [LOW] `setup.py:306-321`, `:811`: in an already-initialized repo the command shows nothing to review, so an
  `allowed-signers` the agent committed beforehand is never shown. This is the documented "committed counts as
  reviewed" residual, with less chance of notice. → List the non-comment lines of `allowed-signers`,
  `legacy-approvals` and `allowed-commands` in the reply.

Spec flags (security-reviewer):

| Flag | Mitigated? | Evidence |
|---|---|---|
| A hook writes a human-owned file | Yes | session repo only (`cli.py:940-946`), template-or-none config, no Approved/Closed, no approval in `--all` history (`setup.py:691-740`); exact write, committed alone; CI reads the base config |
| The hook writes the core scaffold without a preview (R-2a) | Yes | `scaffold_root_problem`, Preflight ✗, `symlink_refusal`, create-only through `write_file` (O_NOFOLLOW, O_EXCL) (`setup.py:749-765`); only the config is committed; the reply lists every file; `engine.sh` wakes python only for the exact command |
| The agent prompts a session of its own | Partly (accepted) | R-2 bounds in code; no pre-bash rule yet (MEDIUM) |
| The agent asks the human to type the command | Yes | the skill states each profile's proof first; a bare command previews |
| The profile commit is unsigned in team/strict | Yes, as designed | opens no gate; audits need signed approval commits |
| `sdlc where` prints a home path | Yes | local only; reads no secret |
| A core-only repo lacks the AI review and scheduled scan | Yes | every security-relevant file is core; the parts left out are named |
| No change to secrets, lock, approval path, audit, allowed-commands | Yes | those modules' syntax trees are identical apart from formatting |

## Plan conformance
- **Steps:** all 20 are ticked, and S14-S20 match the diff file by file.
- **Deviation log:** all 33 rows check out, and every code divergence is logged.
- **Not logged:** the live `make dev` check of the typed command. Spec Open question 2 and the plan's Risks call
  for it before the merge; it wasn't done, and only the S7 row (for the old phrase) mentions it.
- **Plan reference:** the plan's AC-19 row names the wrong file for `Feedback::test_prints_links_offline` (it is in
  `tests/test_setup.py`).

## Test-first evidence
| Step | Red recorded in the commit body |
|---|---|
| S14 `3bacac1` | "the engine never saw '/zouj-ai-sdlc:setup solo'" |
| S15 `66b297e` | 9 `SetupCommand` tests, no hook output |
| S16 `3943f29` | 4 `FirstRun` tests: "this repo isn't set up yet" |
| S17 `f564359` | the card test. `CommandWalk` passed first time: its behaviour came red-first in S14 and S16 (logged) |
| S18 `676a468` | two named Docs tests |
| S19 `ae31453` | `test_profile_eval_case_is_complete` |
| S20 `a693a2f` | three named Docs tests |

The red runs were run and seen in the authoring session. Each step lands its test and code in one commit, so git
history can't show the order. The reviewers' attempts to replay red against parent commits were refused by the
sandbox.

## Fixes requested
1. **[HIGH] The live check (human).** In a `make dev` session, in a fresh throwaway repo, type
   `/zouj-ai-sdlc:setup solo` once. Confirm the reply says `profile SET: solo` with the created files, and record the
   result in the Deviation log. If the hook got the expanded skill text instead, the feature doesn't work and S15
   needs `UserPromptExpansion`.
2. **[MEDIUM] `lib/sdlc_engine/setup.py:749`.** `scaffold_first`'s refusal on an approval commit in the history is
   untested. → Add a `FirstRun` case (no `.aiops/`, an `AIOps-Approval:` commit on some ref): `profile NOT set`, no
   `.aiops/`, HEAD unchanged.

## Other findings (non-blocking)
- [LOW] `setup.py:763-764`, `:786`: after a write that failed part-way, the reply lists what was written and then
  says "Nothing was written". → Drop the sentence on that path.
- [LOW] `setup.py:752`: Preflight on the hook path runs `claude --version`, `gh auth status` and `git config`,
  which can add up to ~15 s to the matching prompt. → Skip the `!`-only rows there.
- [LOW] `hooks/engine.sh:13` vs `cli.py:41`: `PROFILE_RE` accepts a trailing newline; the `engine.sh` pre-filter
  doesn't (it sees `\n`). So the command with a trailing newline works in an initialized repo but not a fresh one.
  → Make them agree.
- [LOW] `cli.py:984`, `engine.sh:16`: in a repo without `.aiops/`, the session-start notice still names
  `/zouj-ai-sdlc:init`. → Name `/zouj-ai-sdlc:setup solo|team|strict`.
- [LOW] AC-18 wording vs R-4 (see the table).
- [NIT] `tests/test_setup.py:1152` (the `FirstProfile` docstring) and `setup.py:688` (a section comment) still
  name the phrase.
- **Verifier notes:**
  - AC-14's alpha.3 state isn't exercised through `repair`, `setup` or `init`.
  - AC-20's core-only rerun is tested for `init` only.
  - AC-22 doesn't assert a user's `CLAUDE.md` as a step.
- **Local checks:** shellcheck isn't installed locally; CI runs it on `engine.sh`.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 35 | AC-18 and AC-22 partial; the live typed-command check missing |
| Security | 25 | 22 | Both reviewers 22: the accepted nested-session MEDIUM; the fresh-repo history refusal untested |
| Test quality & test-first | 20 | 17 | Strong `engine.sh`-level tests, including "no python start"; one security path untested; red only in commit bodies |
| Plan conformance | 10 | 10 | Every code divergence logged |
| Maintainability | 5 | 5 | Two small helpers, reuse of `preflight`, `init_actions`, `apply_init`, `_commit_alone` |
| **Total** | 100 | **89** | PASS needs ≥ 80, no BLOCKER or HIGH, every AC met |
