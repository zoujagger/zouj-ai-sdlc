# .aiops: lifecycle artifacts (zouj-ai-sdlc)

Each change lives in `.aiops/NNNN-slug/`: `intent.md` → `spec.md` → `plan.md` → `review.md` (+ `pr.md`).
The `sdlc` engine derives each intent's state from these files and git. Run `sdlc status`.

- **Gates:** a human types `Intent Approved NNNN`, `Spec Approved NNNN` or `Plan Approved NNNN` as the whole prompt
  (or runs `sdlc approve NNNN intent|spec|plan` in a terminal). The approval is stamped (`approved-by/at/via/sha256`)
  and committed alone, **SSH-signed**, with an `AIOps-Approval:` trailer. CI (`aiops-gates.yml`) checks the signature
  against the target branch's `config/allowed-signers`.
- **Approver setup:** a dedicated key (`ssh-keygen -t ed25519 -f ~/.ssh/aiops_signing`, with a passphrase), then
  `git config --global gpg.format ssh` and `git config --global user.signingkey ~/.ssh/aiops_signing.pub` (repo-local
  signing settings are refused). Add the key to `config/allowed-signers` (`<email> namespaces="git" <public key>`) and
  land it through a reviewed PR. `sdlc doctor` checks the setup.
- **Profile:** how an approval is proven: `solo` (the typed phrase and an unsigned commit), `team` (an SSH-signed
  commit) or `strict` (an `sk-` key touch). A human sets the first one by typing `Setup Profile solo|team|strict` as
  the whole prompt. Changing it later is `sdlc setup --profile <name>` in your own terminal.
- **A human for each signature** (`approval_key_policy: "human"`, the default): use a passphrase-protected key that
  isn't loaded in ssh-agent, or an `sk-` key. Approve in your terminal with the command the refusal prints
  (`/usr/bin/python3 -I <plugin>/bin/sdlc approve NNNN intent|spec|plan`). `sdlc where` prints that command's path.
- **Stale approvals:** editing an approved body re-closes its gate. Plans keep their approval when steps are ticked
  and the Deviation log grows.
- `config/`: human-owned guard lists that extend the plugin defaults (`protected-paths`, `test-paths`, `readonly-exempt`).
- `config.json`: `lock_when_idle` (code is read-only with no active intent), `commit_approvals`, `main_branch`,
  `require_signed_approvals` (CI rejects approval commits that aren't GPG/SSH-signed. Recommended for teams).
- `state/` (git-ignored): the active intent and the `/fix` test lock.
- **Parts:** setup installs the core scaffold. The rest is opt-in: `sdlc setup --with review` (Claude reviews pull
  requests), `maintain` (control bands, scheduled scans), `deploy`, `governance` or `issues`, or `--with all`.
  `sdlc list-installed` shows what is installed.

## Unattended execution (state 4)
Plugins can't grant permissions, so choose how the TDD loop runs without a prompt at every step. Either way the
plugin's guards still run: the read-only lock, the approval and merge gates, secrets and production deploys.

**Auto mode.** Claude Code judges each step and asks only for the risky ones. Start the session with
`claude --permission-mode auto`, or make it your default with `"permissions": {"defaultMode": "auto"}` in your
user settings (`~/.claude/settings.json`). It can't be committed for the team:
Claude Code ignores that value in project settings. The plugin never sets a permission mode.

**Allow-rules.** Add the rules for your stack to `.claude/settings.json` → `permissions.allow`. For example:
```json
["Bash(make *)", "Bash(sdlc *)", "Bash(git add *)", "Bash(git commit *)", "Bash(git switch *)",
 "Bash(npm test*)", "Bash(pytest*)", "Bash(go test*)", "Edit", "Write"]
```
