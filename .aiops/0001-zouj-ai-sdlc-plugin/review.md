---
id: 0001
verdict: CHANGES_REQUESTED
commit: c26f6913a328ba25e8840215ddf225bf12b3a3bd
score: 66/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-10-30
---

# Review: zouj-ai-sdlc plugin

<!-- State 5 PRE-REVIEW. Compiled only from the three fresh-context persona reports (base fb975f6, head c26f691).
     The human decides what happens next. -->

## Summary
The build is green: `make check` passes (58 tests), `claude plugin validate .` passes with an ICON_MISSING warning, and
`sdlc validate --all --ci` is clean. All three reviewers say the tests exercise real behaviour. But all three also
independently reproduced bypasses of the core guarantees.
- **The read-only lock can be bypassed.** A heredoc whose redirect comes after the marker (`cat <<EOF > src/app.py`)
  is allowed while locked.
- **The approval gate can be forged.** An agent can make an approval commit that the CI audit accepts: run an
  obfuscated `sdlc approve` with the Claude env vars cleared.
- **The process skipped its own gates.** The code was merged and tagged before the plan was approved and before
  this review existed.

Verdict: **CHANGES_REQUESTED**, score 66/100. The verifier says NOT VERIFIED, the security reviewer says FAIL (1 high),
and the code reviewer recommends CHANGES_REQUESTED.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `claude plugin validate .` (`make build`, CI), with an ICON_MISSING warning |
| AC-2 | ✅ met | `tests/test_engine.py:40` (states 1→5, next step), `:66`, `:75` (state 6), `:87`, `:186` (state 0), `tests/test_cli.py:52` |
| AC-3 | ❌ not met | Edit/Write/prompt paths are tested (`tests/test_guards.py:37`, `:44`, `:115`, `:164`, `:171`; `tests/test_engine.py:139`). Bypassed by a heredoc write of a stamped artifact (`lib/sdlc_engine/guards.py:123`) and by an obfuscated `sdlc approve` with the env vars cleared (`guards.py:145`, `approvals.py:17-18`) |
| AC-4 | ❌ not met | `tests/test_guards.py:22`, `:90`, `:107`, `:123`, `:131`. Bypassed by `cat <<EOF > src/app.py` (`guards.py:123`). Also `git commit <path>` (`guards.py:337-342`), `git -C src checkout`, `cp -t`, `find -delete` and `awk -i inplace` |
| AC-5 | ✅ met | `tests/test_guards.py:51`, `:61` |
| AC-6 | ✅ met | `tests/test_engine.py:24`, `:30`, `:87` |
| AC-7 | ✅ met | `tests/test_engine.py:66`, `tests/test_guards.py:136`, `:148`, `tests/test_shell_hooks.py:26`. State 6 is only reported on main (`machine.py:310`, MINOR) |
| AC-8 | ✅ met | `tests/test_shell_hooks.py:66`, `:91`, `tests/test_guards.py:76`, `:195` |
| AC-9 | ✅ met | `tests/test_cli.py:14`, `:27`, `:32` |
| AC-10 | ❌ not met | `tests/test_engine.py:151`, `:165`, `:179`, `tests/test_cli.py:62` only catch commits with a `Co-Authored-By: Claude` trailer. An agent-run approve passes `validate --ci` (verified end to end) |
| AC-11 | ⚠️ partial | `tests/test_shell_hooks.py:26`, `:36`, `:47`, `:57` check expected values, not old-vs-new behaviour. The guards are now dormant without `.aiops/`, and removing `.aiops/` disables them (`hooks/engine.sh:11-15`, `hooks/lib.sh:68`) |

## Security
- **[HIGH] An agent can forge an approval that the CI audit accepts.** `lib/sdlc_engine/guards.py:145` (ENGINE_RE),
  `approvals.py:17-18`, `approvals.py:75-104`.
  - How: `env -u CLAUDECODE -u CLAUDE_CODE_CHILD_SESSION` combined with `sdl\c approve`, a variable, or
    `"$(printf …)"` defeats both the text match and the env check. The engine then stamps and commits a normal
    approval, and `validate --ci` exits 0.
  - Fix: make approvals cryptographically human. Turn on `require_signed_approvals` by default and check signatures
    against an allow-list of approver keys (`%GF` / `allowedSignersFile`, since `U` accepts any key), or check a
    CODEOWNER review through the GitHub API.
  - Also put `/.aiops/config.json` under the guard-list CODEOWNERS line.
- **[MEDIUM] Removing or renaming `.aiops/` turns every guard off**, including the prod-deploy, secret and force-push
  guards. `hooks/engine.sh:11-15`, `hooks/lib.sh:68`, `guards.py:239-241`.
  - Fix: block rm/mv on `.aiops` and its folders. Decide whether the plugin is enabled from `git ls-files .aiops`,
    not the working tree. Keep deploy, secret and force-push rules unconditional.
- **[MEDIUM] Consumer repos lose the `.env`/secret read protection.** The old `permissions.deny` for
  Read(.env*, secrets/**, *.pem, *.key) is gone, and nothing guards Read/Grep/Glob or `awk|sed -n|cp` on `.env`.
  - Fix: add a `Read|Grep|Glob` PreToolUse matcher using the secret globs, and ship
    `templates/scaffold/.claude/settings.json` with the old deny list.
- **[MEDIUM] The scaffold's Claude workflows load the plugin unpinned**, in jobs that hold `ANTHROPIC_API_KEY` and
  write permissions (`templates/scaffold/.github/workflows/claude*.yml`).
  - Fix: pin to a tag or commit sha, or vendor the plugin. Pin `aiops-gates.yml` to a sha too.
- **[LOW] This repo's own `aiops-gates` job runs the PR's own engine** (`.github/workflows/ci.yml`).
  - Fix: run the audit with the base-branch engine.
- **[LOW] CI tools are unpinned** (`ruff`, `@anthropic-ai/claude-code`).

Spec flags:

| Flag | Mitigated? | Evidence |
|---|---|---|
| Local hooks are a deterrent. The backstop is the CI audit plus CODEOWNERS | Partially | The audit accepts an agent-produced approval, so only CODEOWNERS review actually mitigates this |
| The approval hook commits only the approved file | Yes | `approvals.py:54-58`, `:98-101` |
| The credential scanner and `.env` guards are kept | Partially | The content scanner is kept, but Read-tool protection is lost, and the guards are off without `.aiops/` |

## Plan conformance
- **[MAJOR] The gates were opened after the fact.**
  - The code was merged at 14:32Z (`1afe6b7`, PR #5), then tagged `v0.1.0`, and the CHANGELOG was cut (`658cb2e`).
  - Only after that were the intent, spec and plan approved, at 14:52-14:53Z (`0ae7bae`, `b013108`, `a09f5b1`).
  - No review.md existed before release. The Plan-mode acceptance that plan.md's Approach points to isn't recorded in the repo.
- **[MAJOR] Unlogged deviation in S7.** The plan and spec describe the cutover as `.update/apply.sh`, run by the
  human. It landed as commit `283bc6b`, co-authored by Claude, and the script is in neither the tree nor history. S7 is ticked anyway.
- **[MINOR]** The Commit column is empty in all 12 Deviation log rows. The spec was approved as `risk: high` with its
  tech-lead question still open.
- **[MINOR] Read-only exemption too broad:** `defaults/readonly-exempt` lets `*.md` through in the read-only states.
  That includes `skills/*/SKILL.md`, `agents/*.md`, CLAUDE.md and REVIEW.md.
- **[MINOR] Unguarded engine commands:** `sdlc use` and branch switching move to another, already unlocked intent.
  Copying an approved folder (`cp -r .aiops/0001-x .aiops/0002-y`) gives a new intent in state 4 locally (CI catches this one).
- Out of scope: nothing significant. `fce7b53` and `f5a2f60` are CI fixes under the same intent.

## Test-first evidence
- **[MAJOR]** None of the 13 commits from `fb975f6` to HEAD has a `Red:` line. S1-S6, the code and the tests all land in one commit
  (`71f89b1`). Its claim that the verifier gaps were "fixed test-first" isn't backed by any recorded failing run.
- **[MINOR]** `tests/test_engine.py:177` accepts `"only" in e or "sha256" in e`, so the single-file-commit rule is never tested on its own.
- Strength: the tests really assert behaviour. They drive `bin/sdlc hook …` through real git repos (verifier, code-reviewer).

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 30 | AC-3, AC-4 and AC-10 bypassed; AC-11 partial |
| Security | 25 | 16 | 1 HIGH (forgeable approvals), 3 MEDIUM |
| Test quality & test-first | 20 | 11 | real behavioural tests; no red-first evidence |
| Plan conformance | 10 | 5 | gates opened after merge and release; unlogged S7 deviation |
| Maintainability | 5 | 4 | clean stdlib engine; `_check_command` is dense |
| **Total** | 100 | **66** | **CHANGES_REQUESTED**: below 80, one HIGH finding, ACs not met |

### Fixes requested, in order
1. Heredoc parsing in `guards.py:123`: strip only the body lines. Add regressions for code, artifact and state targets.
2. Approvals that can't be forged: require signed approvals by default (allow-listed keys) or a CODEOWNER check
   through the GitHub API. Normalise the command name before ENGINE_RE matching. Put `config.json` under the
   guard-list CODEOWNERS line.
3. Guard `.aiops` itself: block rm/mv; decide "enabled" from `git ls-files`; keep the deploy, secret and force-push guards unconditional.
4. Add secret-read protection (`Read|Grep|Glob` matcher) and a scaffold `.claude/settings.json` deny list.
5. Pin the plugin in the scaffold's Claude workflows, and pin `aiops-gates` to a sha.
6. Plan hygiene: log the bootstrap exception and the S7 deviation; fill in the Commit column; record `Red:` evidence for each future step.
7. MINORs: `git commit <path>`, `git -C`, `find -delete`; narrow the `*.md` exemption; state 6 off main; the single-file audit test.
