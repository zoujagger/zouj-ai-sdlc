<!-- PR description for intent 0007, generated in state 5. `gh pr create --body-file` it. -->
## 0007 follow-up: `/zouj-ai-sdlc:setup <profile>` replaces the profile phrase; review rounds 4-15

**Intent:** `.aiops/0007-first-run/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** round 15 CHANGES_REQUESTED, 91/100 at `9b068a1`. Its one blocker, a false positive, is fixed in
`2ef6811`. A round 16 was started on that commit and stopped by the human before it reported. The human decides
the merge.

PR #18 merged the first part of 0007 at round 3 (`2da5b05`). This PR carries everything after it.

### What and why
- **The typed `/zouj-ai-sdlc:setup solo|team|strict` sets the first profile.** It replaces the `Setup Profile <name>`
  phrase that PR #18 shipped. In a repo without `.aiops/` it first writes the core scaffold, creating missing files
  only. It then commits `.aiops/config.json` alone, as `chore(aiops): Setup Profile <name>` (the spec was amended
  and re-approved for this: `3f73ade`, AC-18). The hook acts only on the session's repo, while the config is the
  untouched template and nothing has been approved in the files or the history
  ([ADR 0003](../../docs/adr/0003-first-profile-by-typed-setup-command.md)).
- **What the human sees directly (`systemMessage`).** The result, the identity and trust-list warnings, and the
  human-owned files to review. Kept scaffold files that differ from the plugin's are named. The message is built
  apart from the steps and escaped, so a planted `user.name`, a trust-list line, a directory name or a commit subject
  can't cut it short or forge a line.
- **G-GATE-07 runs in every repo.** It refuses `sdlc hook` and the plugin's own `hooks/engine.sh`. Without `.aiops/`,
  only the hook-feeding forms are refused, so unrelated projects keep working. The check fails closed on paths it
  can't read. It allows a project's own `engine.sh`, other plugins' scripts and ordinary shell globs.
- **Hardening from the reviews:**
  - `core.worktree` is refused.
  - The commit and install-state hold the bytes the hook wrote.
  - The approver identity is kept to one printable line.
  - Trust lists are capped.
  - `python3 -I …/sdl? hook` is refused (a gap on main too).

### Acceptance criteria
All 23 met. The round 15 verifier (`9b068a1`) found every AC test passing: `make check` (442), `make build` and
`sdlc validate`. The per-AC table with test paths is in [review.md](review.md). AC-21's eval run (1.00 with the
plugin, 0.67 without) is from S19 and was not re-run.

### Deviations from plan
No new Steps. Each review round (r4-r15) has a Deviation log row in [plan.md](plan.md) naming its red tests.

### Risks and rollback
- **Accepted residual (Known gaps, `docs/architecture.md`).** An agent-started session (`claude -p "/zouj-ai-sdlc:setup
  solo"`) and the fed-payload forms static parsing can't see can set a first profile, or open a gate under `solo`.
  Those forms are a non-literal event, a renamed copy, stdin, or a script the agent wrote. What bounds them: the
  untouched template config, nothing approved, one visible commit, and CI reading the config from the base branch.
  Under `team` and `strict`, signing still holds. The planned pre-bash rule against agent-started sessions is on the
  backlog.
- **Not verified here.** `shellcheck` isn't installed locally, so CI is the shell lint. No one has yet typed the
  command by hand in a `make dev` session, so do that once before the release.
- **Rollback:** revert the PR. A profile set by the command is an ordinary `config.json`.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
