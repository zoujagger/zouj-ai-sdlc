# What is enforced (and how)

| Rule | Mechanism |
|---|---|
| Only a human opens a gate | A `UserPromptSubmit` hook accepts the phrase only as the *whole* prompt. It stamps `approved-by/at/via/sha256` and commits the file alone, **SSH-signed**, with an `AIOps-Approval:` trailer. These are blocked: edits to `status`/`approved-*`/`id`, disguised `sdlc approve` calls, env-marker tampering and forged trailers |
| States 1-3 are read-only | `sdlc hook pre-edit` and `pre-bash` block writes outside `.aiops/` and docs: Edit/Write, redirects, `sed -i`, `cp/mv/rm`, package installs, formatters, and `git add/commit/apply/stash` of code |
| Artifacts in order | `spec.md` needs an approved intent, `plan.md` an approved spec, `review.md` an approved plan. New artifacts start as Draft |
| Approvals can't silently drift | Editing an approved body re-closes its gate. Plans keep their approval when steps are ticked and the Deviation log grows |
| Schema-valid artifacts | `schemas/*.json` define the required front matter and sections and the AC ids, and require every AC to be covered by the plan and the review. Checked after each edit and before each approval |
| Definition of done | The Stop hook requires `make check` green. A PASS review goes stale if code changes after it |
| Human-only final gate | These are blocked: merging on main, `gh pr merge`/approve, pushing to main, and production deploys |
| CI audit | `aiops-gates.yml` runs `sdlc validate --all --ci --base <target>`. Every open gate must trace to a single-file approval commit signed by a key in the **target branch's** `allowed-signers`, or be listed in its `legacy-approvals` |
| `.aiops/` integrity | From the shell, these can't be deleted, moved or overwritten (`G-FILE-05`): `.aiops`, intent folders and their files; the repo; a directory above it; a directory holding a protected path or a tracked secret. Archives, `git stash pop`, and merges or rebases from branches other than main can't bring in `.aiops/config*`, settings or protected paths (`G-FILE-06`). `git pull` off main is refused (fetch, then an inspected merge). A git-tracked `.aiops/` counts as initialized |
| Always-on safety | In **every** repo: secret reads and writes (Read/Grep/Glob and shell), credentials, force-push, history rewrites, production deploys |
| SDLC-only guards | Active after `sdlc init`: protected paths, push-to-main, the merge gate, the `/fix` test lock, `make check` |

Local hooks are a strong deterrent, not a sandbox. The CI audit plus CODEOWNERS on `.aiops/` are the backstop
([threat model](architecture.md#threat-model)).

## Components
| Kind | Location | Contents |
|---|---|---|
| Skills | `skills/` | `using-zouj-ai-sdlc` (bootstrap, injected at session start) · core states `intent` `spec` `plan` `implement` `review` `pr` `status` · `init` `fix` `parallel` · Maintain `deploy` `triage` `incident` `postmortem` `retro` `release` `learn` `adr` `security-check` · `help-me` `onboard` · policies (security, compliance, UX, brand) |
| Agents | `agents/` | 12 role agents, from product-analyst (state 1) to incident-responder (Maintain): [who does what](sdlc.md#who-does-what) |
| Hooks | `hooks/hooks.json` | SessionStart, UserPromptSubmit (approvals), PreToolUse (gate, lock, bash, files, tests, deploy guards), PostToolUse (validate + format/lint), Stop (`make check`) |
| Engine | `bin/sdlc`, `lib/sdlc_engine/`, `schemas/` | the `sdlc` CLI and the hook dispatcher (all commands: [COMMANDS-QUICK-REF.md](../COMMANDS-QUICK-REF.md)) |
| Templates | `templates/artifacts/`, `templates/scaffold/` | artifact templates · what `init` copies into a repo (Makefile contract, CLAUDE.md, REVIEW.md, CI, bands) |
| Tests / evals | `tests/`, `evals/` | deterministic guard tests (`make test`) · behavioural evals (`make evals`, the `claude plugin eval` format) |
