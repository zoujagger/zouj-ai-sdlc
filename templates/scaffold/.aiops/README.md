# .aiops: lifecycle artifacts (zouj-ai-sdlc)

Each change lives in `.aiops/NNNN-slug/`: `intent.md` → `spec.md` → `plan.md` → `review.md` (+ `pr.md`).
The `sdlc` engine derives each intent's state from these files and git. Run `sdlc status`.

- **Gates:** a human types `Intent Approved NNNN`, `Spec Approved NNNN` or `Plan Approved NNNN` as the whole prompt
  (or runs `sdlc approve NNNN intent|spec|plan` in a terminal). The approval is stamped (`approved-by/at/via/sha256`)
  and committed alone with an `AIOps-Approval:` trailer. CI (`aiops-gates.yml`) audits every gate.
- **Stale approvals:** editing an approved body re-closes its gate. Plans keep their approval when steps are ticked
  and the Deviation log grows.
- `config/`: human-owned guard lists that extend the plugin defaults (`protected-paths`, `test-paths`, `readonly-exempt`).
- `config.json`: `lock_when_idle` (code is read-only with no active intent), `commit_approvals`, `main_branch`,
  `require_signed_approvals` (CI rejects approval commits that aren't GPG/SSH-signed. Recommended for teams).
- `state/` (git-ignored): the active intent and the `/fix` test lock.

## Unattended execution (state 4)
Plugins can't grant permissions. To let the TDD loop run without prompts, add the rules for your stack to
`.claude/settings.json` → `permissions.allow`. The guards still apply on top of them. For example:
```json
["Bash(make *)", "Bash(sdlc *)", "Bash(git add *)", "Bash(git commit *)", "Bash(git switch *)",
 "Bash(npm test*)", "Bash(pytest*)", "Bash(go test*)", "Edit", "Write"]
```
