# zouj-ai-sdlc

> **Status: alpha (0.2.0-alpha.3), experimental.** Gates and guards may change between alphas; don't rely on it
> for production governance yet. Feedback welcome.

A [Claude Code](https://code.claude.com) plugin that runs your software lifecycle as a **state machine over Markdown
artifacts versioned in Git**. It's inspired by [Superpowers](https://github.com/obra/superpowers) (a bootstrap skill,
trigger-style skills, red-flag tables, subagent-driven execution) and strictly modeled on Anthropic's *AI-Native SDLC
Playbook*: work starts from an intent, every state commits an artifact the next one reads, and **humans decide at every
gate**. Here those gates are enforced by hooks instead of being left to the model's good behaviour.

```
 1 BRAINSTORMING ──▶ 2 SPECIFICATION ──▶ 3 PLAN (read-only) ──▶ 4 EXECUTION (autonomous) ──▶ 5 PRE-REVIEW
   intent.md          spec.md             plan.md                code + green tests            review.md + pr.md
 ✋ "Intent Approved"  ✋ "Spec Approved"   ✋ "Plan Approved"       (make check green)             ✋ the human merges
```

## Start using
Start from what you're doing. Every route runs the same playbook workflow, with a human at every gate.

| You want to… | Run | Playbook stage |
|---|---|---|
| Try the workflow first | a throwaway repo: see **Just looking?** under Install | (any, risk-free) |
| Set up this repo | `/zouj-ai-sdlc:setup` (pick `solo`, `team` or `strict`) | 1 Plan: formalise and share |
| Build a feature or change | `/zouj-ai-sdlc:intent "<need>"` → spec → plan → implement | Trigger → Design → Build |
| Fix a bug | `/zouj-ai-sdlc:fix "<bug>"` (failing test first) | Test |
| Act on an alert or issue | `/zouj-ai-sdlc:triage alert:<metric>` → a new intent | Maintain → Trigger |
| Get a branch reviewed | `/zouj-ai-sdlc:review`, then `/zouj-ai-sdlc:pr` | Deploy: AI review |
| See where you are and what's next | `/zouj-ai-sdlc:status` | any |
| Upgrade, repair or remove the setup | `sdlc list-installed`, then `sdlc upgrade`, `repair` or `uninstall --dry-run` | Maintain |
| Understand a block | `sdlc why <id>` (the id is in `BLOCKED [G-…]`) | any |
| Not sure | `/zouj-ai-sdlc:help-me "<what you want>"` | any |

All commands: [COMMANDS-QUICK-REF.md](COMMANDS-QUICK-REF.md). Stuck? [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or
`sdlc feedback`.

## Install
Requirements: `git`, `make`, `python3` ≥ 3.9 (stdlib only), Claude Code ≥ 2.1. `gh` and `jq` are optional. The
current release is **0.2.0-alpha.3**: check yours with `/plugin list`.

> **Official sources only:** this repository (`github.com/zoujagger/zouj-ai-sdlc`) and the marketplace/plugin id
> `zouj-ai-sdlc@zouj`. Copies elsewhere aren't reviewed.
>
> **What you trust:** enabling the plugin trusts github.com/zoujagger/zouj-ai-sdlc at that ref. Its hooks run as you on
> every tool call, and `bin/sdlc` is what you run to approve. So the commands and the snippet pin a release tag (`ref`),
> and moving to a new release should be a reviewed change: rerunning `sdlc setup` after an upgrade proposes it as a
> diff.

Pick **one** path:

**A. Guided (recommended).** Install the plugin, pinned to the release, then let setup do the rest:
```text
/plugin marketplace add zoujagger/zouj-ai-sdlc@v0.2.0-alpha.3
/plugin install zouj-ai-sdlc@zouj
/zouj-ai-sdlc:setup
```
Setup checks the prerequisites, asks for a profile, previews every change and the gates, applies after you confirm,
and prints the steps only you can do (signing, CODEOWNERS, commit). Rerun it any time: it changes nothing when
everything is in place. Run by Claude, setup scaffolds with the `team` default; `solo` or `strict` is applied by your
own terminal run: `<plugin>/bin/sdlc setup --profile solo|team|strict [--dry-run] [--yes]`.

**B. Just the plugin.** The same two `/plugin` commands, then `/zouj-ai-sdlc:init` (or
`sdlc init --stack python|node|go`) in each repo.

**C. For a team, declaratively.** Commit this to the project's `.claude/settings.json` (`init` and `setup` write it
for you); Claude Code then offers the plugin to everyone who opens the repo:
```json
{
  "extraKnownMarketplaces": {
    "zouj": { "source": { "source": "github", "repo": "zoujagger/zouj-ai-sdlc", "ref": "v0.2.0-alpha.3" } }
  },
  "enabledPlugins": { "zouj-ai-sdlc@zouj": true }
}
```

**Just looking?** Try it in a throwaway repo, so no real project is touched:
`mkdir /tmp/sdlc-try && cd /tmp/sdlc-try && git init -q && git commit -q --allow-empty -m init`. Set it up with
`<plugin>/bin/sdlc setup --profile solo --yes` in that terminal (solo needs your own run: setup run by Claude keeps
the team default), then commit the scaffold: `git add -A && git commit -m "chore: adopt zouj-ai-sdlc"`.
Start with `/zouj-ai-sdlc:intent "greet people in French"` in `claude`, walk the five states, then delete the
directory.

**Profiles** change only how a human approval is proven; the workflow and every gate are the same:

| Profile | Approval proof | For |
|---|---|---|
| `solo` | the typed phrase + an unsigned approval commit | one developer, trying it out |
| `team` | an SSH-signed commit, a human per signature (passphrase key out of ssh-agent) | most teams |
| `strict` | an `sk-` key touch per signature, plus CODEOWNERS on `/.aiops/` | regulated or high-risk repos |

Without `.aiops/` the plugin's **SDLC gates are dormant** until you run setup or init. Its safety guards (secret reads,
force-push, history rewrites, production deploys, and Edit/Write of secrets, your shell startup files and the installed
plugin) are on in every repo. Shell writes to those are checked only in initialized repos for now (intent 0005).

## Lifecycle: upgrade, repair, remove
`init` and `setup` record what they wrote in `.aiops/install-state.json`: the plugin version, the CI ref, the profile
and a hash of every file. The engine owns that file; the agent can't edit it, and CODEOWNERS covers it.

| Command | What it does |
|---|---|
| `sdlc list-installed` | Each installed file: `current`, `stale` (an older plugin wrote it), `modified` (yours now), `missing`, `unmanaged`, `dropped`, `new`, `declined` (you removed it before adoption: never re-created). Read-only |
| `sdlc repair [--dry-run] [--yes]` | Restores missing files. Never touches one you modified |
| `sdlc upgrade [--dry-run] [--yes]` | After you update the plugin with `/plugin`: replaces stale files (diff shown), creates new ones, keeps your modified files except for the CI ref, pins every literal `ZOUJ_SDLC_REF` and the zouj marketplace `ref` (nothing else, every change shown as a diff first) to the plugin's full commit sha, and lists migrations (e.g. `legacy-approvals`, which only you run) |
| `sdlc uninstall --dry-run`, then `sdlc uninstall` | Removes the plugin's unmodified files, install-state and its `.gitignore` lines. Never `.aiops/NNNN-*`: the audit trail stays. **Human only**: refused inside Claude Code |

Repos set up by 0.2.0-alpha.1 or alpha.2 have no install-state. The first `upgrade` or `repair` adopts them: files
equal to a released scaffold become managed, the rest count as modified and are never touched. Run by Claude, these
commands never write a human-owned file (workflows, `.claude/settings.json`, `.aiops/config*`, CODEOWNERS) or code
under the read-only lock: they print your terminal command instead.

**Blocked by mistake?** Every block names its rule (`BLOCKED [G-ENV-03] by guard-bash: …`); `sdlc why <id>` explains
it. Two heuristic rules (`G-ENV-03` env/printenv, `G-BASH-07` sudo and friends) accept a human-owned exact-command
allowance: add `<id> <exact command>` to `.aiops/config/allowed-commands` (never a whole-environment dump such as a
bare `printenv`). It lifts that one rule for that one command,
and every other rule still runs. No rule that protects a gate, a secret or the approval toolchain can be allowed, and
there is no per-rule disable switch (`docs/adr/0002-allowances-never-touch-a-gate.md`).

## How it works
| State | You run | The agent produces | Leaves the state when |
|---|---|---|---|
| 1 BRAINSTORMING | `/zouj-ai-sdlc:intent "<need>"` | a targeted clarification interview → `.aiops/NNNN-slug/intent.md` | you type **`Intent Approved NNNN`** |
| 2 SPECIFICATION | `/zouj-ai-sdlc:spec` | `spec.md`: requirements, ACs, **DB schema, API contracts, security and data-leak flags** | you type **`Spec Approved NNNN`** |
| 3 PLAN | `/zouj-ai-sdlc:plan` | `plan.md`: chronological file-by-file steps, risks, test definitions. **Code is read-only** | you type **`Plan Approved NNNN`** |
| 4 EXECUTION | `/zouj-ai-sdlc:implement` | per step: proof test → see it fail → code → green, on `feat/NNNN-slug`, no questions asked | every step ticked, `make check` green |
| 5 PRE-REVIEW | `/zouj-ai-sdlc:review` | fresh-context verifier, code-reviewer and security-reviewer → `review.md` (score /100) + `pr.md` | **you** merge (the agent can't) |

`sdlc status` (or `/zouj-ai-sdlc:status`) always shows the state, who it's waiting on, and the exact next step.
The state is **derived** from the artifacts and git, never stored.

## What is enforced (and how)
| Rule | Mechanism |
|---|---|
| Only a human opens a gate | A `UserPromptSubmit` hook accepts the phrase only as the *whole* prompt. It stamps `approved-by/at/via/sha256` and commits the file alone, **SSH-signed**, with an `AIOps-Approval:` trailer. Edits to `status`/`approved-*`/`id`, disguised `sdlc approve` calls, env-marker tampering and forged trailers are blocked |
| States 1-3 are read-only | `sdlc hook pre-edit` and `pre-bash` block writes outside `.aiops/` and docs: Edit/Write, redirects, `sed -i`, `cp/mv/rm`, package installs, formatters, `git add/commit/apply/stash` of code |
| Artifacts in order | `spec.md` needs an approved intent, `plan.md` an approved spec, `review.md` an approved plan. New artifacts start as Draft |
| Approvals can't silently drift | Editing an approved body re-closes its gate. Plans keep their approval when steps are ticked and the Deviation log grows |
| Schema-valid artifacts | `schemas/*.json`: required front matter and sections, AC ids, every AC covered by the plan and the review. Checked after each edit and before each approval |
| Definition of done | The Stop hook requires `make check` green. A PASS review goes stale if code changes after it |
| Human-only final gate | Merging on main, `gh pr merge`/approve, pushing to main, and production deploys are blocked |
| CI audit | `aiops-gates.yml` runs `sdlc validate --all --ci --base <target>`: every open gate must trace to a single-file approval commit signed by a key in the **target branch's** `allowed-signers` (or listed in its `legacy-approvals`) |
| `.aiops/` integrity | `.aiops`, intent folders and their files can't be deleted, moved or overwritten from the shell; a git-tracked `.aiops/` counts as initialized |
| Always-on safety | in **every** repo: secret reads and writes (Read/Grep/Glob and shell), credentials, force-push, history rewrites, production deploys |
| SDLC-only guards | after `sdlc init`: protected paths, push-to-main, the merge gate, the `/fix` test lock, `make check` |

Local hooks are a strong deterrent, not a sandbox. The CI audit plus CODEOWNERS on `.aiops/` are the backstop
([docs/architecture.md](docs/architecture.md#threat-model)).

## Components
| Kind | Location | Contents |
|---|---|---|
| Skills | `skills/` | `using-zouj-ai-sdlc` (bootstrap, injected at session start) · core states `intent` `spec` `plan` `implement` `review` `pr` `status` · `init` `fix` `parallel` · Maintain `deploy` `triage` `incident` `postmortem` `retro` `release` `learn` `adr` `security-check` · `help-me` `onboard` · policies (security, compliance, UX, brand) |
| Agents | `agents/` | product-analyst, architect, planner, implementer, verifier, code-reviewer, security-reviewer, test-engineer, docs-writer, release-manager, diagnostician, incident-responder |
| Hooks | `hooks/hooks.json` | SessionStart, UserPromptSubmit (approvals), PreToolUse (gate, lock, bash, files, tests, deploy guards), PostToolUse (validate + format/lint), Stop (`make check`) |
| Engine | `bin/sdlc`, `lib/sdlc_engine/`, `schemas/` | `status next new draft use validate approve close lock unlock init doctor` |
| Templates | `templates/artifacts/`, `templates/scaffold/` | artifact templates · what `init` copies into a repo (Makefile contract, CLAUDE.md, REVIEW.md, CI, bands) |
| Tests / evals | `tests/`, `evals/` | deterministic guard tests (`make test`) · behavioural evals (`make evals`, the `claude plugin eval` format) |

## Configuration (per repo, human-owned)
- `.aiops/config.json`: `lock_when_idle` (default true), `commit_approvals`, `main_branch`, `require_signed_approvals` (default **true**).
- `.aiops/config/allowed-signers` (keys allowed to approve) and `legacy-approvals` (pre-signing approvals the audit still accepts).
- `.aiops/config/{readonly-exempt,protected-paths,secret-paths,test-paths}` extend the plugin's `defaults/`.
- `SDLC_HOOK_PROFILE=spike` lifts the read-only lock and `make check` for throwaway exploration. The approval and merge gates still hold.
- The active intent comes from the branch (`feat/NNNN-*`), else `sdlc use NNNN`, else `$AIOPS_INTENT`.
- Unattended state 4: plugins can't grant permissions, so add the allow-rules from `.aiops/README.md` to `.claude/settings.json`.

## Approver setup (signed approvals)
```bash
ssh-keygen -t ed25519 -f ~/.ssh/aiops_signing -C "aiops approvals"   # a dedicated key, WITH a passphrase (or an sk- key)
git config --global gpg.format ssh                       # global: repo-local signing settings are refused
git config --global user.signingkey ~/.ssh/aiops_signing.pub
ssh-add -d ~/.ssh/aiops_signing 2>/dev/null              # keep it OUT of ssh-agent, which would sign silently
echo "$(git config user.email) namespaces=\"git\" $(cat ~/.ssh/aiops_signing.pub)" >> .aiops/config/allowed-signers
sdlc legacy-approvals --write                           # once, when upgrading: records older unsigned approvals
git add .aiops/config && git commit -m "chore(aiops): approver keys"   # lands via PR; CI trusts the target branch's list
```
Signing-key options, from strongest to weakest: approve from a separate OS user or a clean clone; an `sk-` key (touch,
without `no-touch-required`); a dedicated passphrase key kept out of ssh-agent. The escape hatch
`"approval_key_policy": "any"` (in `.aiops/config.json`) accepts any key, at a cost: anything running as you can then
sign approvals ([approval isolation](docs/architecture.md#approval-isolation)).

`sdlc doctor` checks the setup. Under the default `approval_key_policy: "human"`, `sdlc approve` refuses before
stamping anything unless each signature needs you: a passphrase key not loaded in ssh-agent, or an `sk-` key (touch).
Approve in your own terminal with `/usr/bin/python3 -I <plugin>/bin/sdlc approve NNNN intent|spec|plan` (Claude prints the exact path), which asks for the passphrase. Typing
`Plan Approved NNNN` in Claude works with an `sk-` key. With a passphrase key, Claude is told the exact terminal
command instead.

## Develop
```bash
make check        # lint + compile + unit, hook and playbook-conformance tests
make validate     # claude plugin validate .
make dev          # claude --plugin-dir .
make evals        # behavioural evals against a live model
```
Docs: [state machine](docs/state-machine.md) · [architecture](docs/architecture.md) · [playbook mapping](docs/sdlc.md) ·
[governance](docs/governance.md) · [worked example](docs/examples/0001-csv-export/). This repo dogfoods itself:
see [`.aiops/0001-zouj-ai-sdlc-plugin/`](.aiops/0001-zouj-ai-sdlc-plugin/).
