---
id: 0007
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 53c90c034b531689466443e9470672744c120d69
score: 87/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-13
---

# Review: First run in five minutes (profile by /setup, terminal command, core scaffold)

<!-- State 5 PRE-REVIEW. Written from the reports of three fresh-context personas that did not write the code.
     Rounds 1-3 (87d3ac8, ccef62e, 7437154) reviewed the removed `Setup Profile` phrase: PASS 86, 88, 92. Round 4 at
     a693a2f (the typed `/zouj-ai-sdlc:setup <profile>`): CHANGES_REQUESTED 89 (HIGH: the live check of the typed
     line; MEDIUM: an untested refusal). Fixed in c29390f and 53c90c0 (a `claude -p` probe confirmed the hook gets the
     typed line). Round 5 at 53c90c0 (this file). Diff against origin/main. -->

## Summary
0007 adds three things:
- **Profile by the typed setup command.** In a fresh repo, `/zouj-ai-sdlc:setup solo|team|strict` first writes
  the core scaffold, then sets the first profile and commits `.aiops/config.json` alone.
- **`sdlc where`.** It prints the terminal command, and the state card shows it.
- **A core-only scaffold.** The default installs only `core`; the other parts are opt in with `--with`.

It ships as 0.2.0-alpha.4.

Round 5 results:
- **Verifier:** VERIFIED. All 23 ACs have passing tests. `make check` (420), `make build` and `sdlc validate` pass.
- **Code-reviewer:** 87/100, no BLOCKER or HIGH.
- **Security-reviewer:** PASS, 23/25, no CRITICAL, HIGH or MEDIUM.

**Verdict: CHANGES_REQUESTED.** There's no BLOCKER or HIGH, but two things stand in the way:
- **One MEDIUM:** after a fresh-repo command, install-state records the template config's hash, so `sdlc
  list-installed` shows the config as `modified`.
- **Two ACs only partly met** (AC-18, AC-23). In both, the spec's wording conflicts with a decision already taken.
  The human accepts the exemption or amends the AC.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:1256`; `tests/test_cli.py:531` |
| AC-2 | ✅ met | `tests/test_playbook.py:344 CommandWalk::test_solo` (fresh repo, every prompt through `engine.sh`, no agent-run setup) |
| AC-3 | ✅ met | `tests/test_setup.py:1303`, `:1308`, `:1319`, `:1330`; `tests/test_cli.py:572` |
| AC-4 | ✅ met | `tests/test_cli.py:546` (11 forms, empty output), `:563` |
| AC-5 | ✅ met | `tests/test_shell_hooks.py:691` (a fake plugin logs every python start; normal and compact payloads) |
| AC-6 | ✅ met | `tests/test_cli.py:593` |
| AC-7 | ✅ met | `tests/test_cli.py:615` |
| AC-8 | ✅ met | `tests/test_setup.py:1410`, `:1417`, `:1431`, `:1207` |
| AC-9 | ✅ met | `tests/test_cli.py:669` |
| AC-10 | ✅ met | `tests/test_cli.py:716`, `:733`, `:742`, `:759` |
| AC-11 | ✅ met | `tests/test_cli.py:412`; `tests/test_setup.py:973` |
| AC-12 | ✅ met | `tests/test_cli.py:421`, `:431`, `:436`, `:447`; `tests/test_setup.py:1008`, `:1023` |
| AC-13 | ✅ met | `tests/test_lifecycle.py:763`, `:775`, `:791` |
| AC-14 | ✅ met | `tests/test_lifecycle.py:709`, `:730`; `tests/test_cli.py:454`, `:461` |
| AC-15 | ✅ met | `tests/test_lifecycle.py:830-851` |
| AC-16 | ✅ met | `tests/test_playbook.py:338 CoreWalk`, `:344 CommandWalk` × solo/team/strict |
| AC-17 | ✅ met | `tests/test_cli.py:782` |
| AC-18 | ⚠️ partial | `tests/test_setup.py:895`; `tests/test_cli.py:794`, `:811`, `:827`, `:838`, `:969`. Behaviour met. The AC says no shipped file mentions `Setup Profile`, but R-4 requires the commit title `chore(aiops): Setup Profile <name>`, which `setup.py:809`, README, SECURITY.md, the ADR and the architecture quote; the test exempts the title. **Human decision:** accept the exemption, or amend the AC (or rename the commit title) |
| AC-19 | ✅ met | `tests/test_cli.py:885`; `tests/test_shell_hooks.py:595`; `tests/test_rules.py:326`; `make build` passes |
| AC-20 | ✅ met | `tests/test_cli.py:470`, `:485`; `tests/test_setup.py:1032` |
| AC-21 | ✅ met (run quoted below) | `tests/test_cli.py:915` |
| AC-22 | ✅ met | `tests/test_setup.py:1076`, `:1103` |
| AC-23 | ⚠️ partial | `tests/test_setup.py:1115` (not a git repo, `$HOME`, `GIT_DIR`, a Preflight ✗), `:1138`. The AC names "not the top of a git work tree"; a subdirectory resolves to the repo's top and is scaffolded there (logged S16, `tests/test_cli.py:587-589`). **Human decision:** accept, or amend the AC |

**AC-21: the run** (plan.md Deviation log S19, 2026-11-13; `--allow-tools Bash Write Edit`, 3 runs per arm):
`profile-by-setup-command` 1.00 with the plugin (asks-for-setup-command PASS ×3, config-unchanged ✓ ×3), 0.67
without, Δ +0.33, $0.87.

## Security
Fixed since round 4:
- the history refusal in a fresh repo is tested;
- a repo-local `Set-By` identity is flagged;
- the trust lists are listed in the reply;
- the hook runs only Preflight's blocking rows;
- the typed line was probed live (`claude -p`, Deviation log r4 HIGH).

Round 5 findings:
- [MEDIUM, accepted residual] An agent-started session (`claude -p "/zouj-ai-sdlc:setup solo"`) can type the
  command. It is bounded to a repo with no profile and nothing approved; it leaves one visible commit, and CI reads
  the base config. Recorded in Known gaps; the pre-bash rule is on the backlog.
- [LOW] `lib/sdlc_engine/setup.py:324-339`: in a fresh repo, the hook's `git diff` calls use the unpinned
  `machine.git`. A `core.fsmonitor` the agent set while the gates were off would run inside the hook's process. That
  matters only where a sandbox allows `.git/config` writes. → Run the profile path's git calls with
  `approvals.PINNED` (or `-c core.fsmonitor=false -c core.hooksPath=/dev/null`), refuse or list
  `approvals.local_config_keys`, and add a red test with a marker-writing fsmonitor.
- [LOW] The trust-list and `Set-By` warnings reach the human only through the agent (`additionalContext`). → Also
  send them in the hook JSON's `systemMessage`, which Claude Code shows the user.
- [LOW] `docs/architecture.md:69`: in a repo without `.aiops/`, an agent can pipe a crafted payload into
  `sdlc hook prompt`, because `check_bash` returns before G-GATE-07 when `gates=False`. It gains nothing new (it can
  already write and commit the config there), but the commit looks human-made. → Name the route in the threat-model
  row and Known gaps.
- [LOW] The interactive check is half done: the probe ran in `-p` mode with a throwaway plugin. → The human types
  `/zouj-ai-sdlc:setup solo` once in a `make dev` session in a scratch repo.

Spec flags (security-reviewer):

| Flag | Mitigated? | Evidence |
|---|---|---|
| A hook writes a human-owned file | Yes | session-repo check (`cli.py` `hook_profile`); `no_profile_yet` and `approval_in_history`; the exact write via `write_file`, committed alone; CI reads the base config |
| The hook writes the core scaffold without a preview (R-2a) | Yes, with the fsmonitor LOW | `scaffold_first`: `scaffold_root_problem`, history, quick Preflight, create-only `init_actions(parts=[])`, `symlink_refusal`, `write_file`; only the config is committed; the reply lists the files; `engine.sh` wakes python only for the command |
| The agent prompts a session of its own | Accepted residual | bounded by `no_profile_yet` and the session-repo check; Known gaps |
| The agent asks the human to type the command | Yes | a bare command previews; only the qualified exact form matches |
| The profile commit is unsigned in team/strict | Yes, as designed | opens no gate; the audit ignores it |
| `sdlc where` prints a home path | Yes | local only; starts no process |
| A core-only repo lacks the AI review and scheduled scan | Yes | `list-installed` names the parts left out; the CI audit is core |
| No change to secrets, lock, approval path, audit, allowed-commands | Yes | `approvals.py` is formatting only |

## Plan conformance
- **Steps:** all 20 are done and match the diff.
- **Deviation log:** every divergence the code-reviewer found is in it, including the format commit, the r1-r4
  fixes, the S16 subdirectory decision, S17's harness-only red and the S19 regex grader.
- **Scope:** nothing ships outside it.
- **Backlog, not this intent:** `uncommitted_scaffold` leaves `.aiops/install-state.json` out of the "Commit the
  scaffold" command. That predates 0007.

## Test-first evidence
Every step and review fix has a `Red:` line in its commit body:
- S1-S13: `f00d51b`…`3cd2b8e`
- r1 `ccef62e`, r2 `7437154`
- S14 `3bacac1`, S15 `66b297e`, S16 `3943f29`, S17 `f564359`, S18 `676a468`, S19 `ae31453`, S20 `a693a2f`
- r4 `c29390f`

The commit messages quote the failing assertions. `53c90c0` adds a test that already passed, and its message says
so. S7's and S17's walks had their red in the steps that built the behaviour (logged). Tests and code share
commits, as this repo accepts.

## Fixes requested
1. **[MEDIUM] `lib/sdlc_engine/setup.py:770`.** `lifecycle.record` runs inside `scaffold_first`, before the profile
   is written (`:806`). Install-state then stores the template's hash, and `sdlc list-installed` reports `modified
   .aiops/config.json` right after a fresh setup. A human's terminal `setup --profile` records `current`, so this
   departs from R-2a. If the config write or commit then fails, install-state also says `profile: solo`. → Record
   the config after it is written; assert `current` in `FirstRun::test_fresh_repo_gets_core_and_the_profile`.
2. **[Human] AC-18 and AC-23.** Accept the exemptions above, or amend the spec.

## Other findings (non-blocking)
- [LOW] `setup.py:822`: "Created the core scaffold (17 files, nothing existing changed)". The 17 includes
  `.gitignore`, and an existing `.gitignore` *is* changed (lines are appended). → Count the 16 core files and name
  the `.gitignore` lines separately.
- [LOW] `cli.py:42` vs `engine.sh:13`: `PROFILE_RE` accepts a leading tab, but the `engine.sh` pre-filter never sees
  one (JSON escapes it as `\t`). A fresh repo and an initialized one still differ for a tab. → Spaces only.
- [NIT] `setup.py:712`: the refusal for `.aiops/` without a config says "run /zouj-ai-sdlc:setup first" to someone who
  just typed it.
- [NIT] `CHANGELOG.md:8`: `[0.2.0-alpha.4] - 2026-11-11` predates the changes it lists. Set the date at tagging.
- [NIT] `CLAUDE.md:16` (133 characters); `docs/architecture.md:22` ("set_first_profile() for the typed phrase").
- **Verifier notes:**
  - AC-8 compares parsed JSON (the bytes match by construction).
  - AC-14's "unchanged": 22 init tests now pass `--with all` (logged S2).

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 35 | AC-18 and AC-23 partial (spec wording); the install-state hash departs from R-2a |
| Security | 25 | 22 | Lower of the two reviewers' scores (22 and 23): unpinned git on the fresh-repo path, warnings only through the agent, the `sdlc hook prompt` route undocumented, the TUI check open |
| Test quality & test-first | 20 | 17 | Strong `engine.sh`-level tests and Red lines throughout; the config hash after the hook is untested |
| Plan conformance | 10 | 9 | All divergences logged |
| Maintainability | 5 | 4 | `setup.py` keeps growing; small wording issues |
| **Total** | 100 | **87** | PASS needs ≥ 80, no BLOCKER or HIGH, every AC met |
