# zouj-ai-sdlc

> **Status: beta (0.2.0-beta.1).** The workflow, gates and guards are settling but may still change between betas;
> don't rely on it for production governance yet. Feedback welcome.

**Coding agents skip steps.** They write code before anyone agreed on what to build, approve their own plans, and
call work done when the tests are red. Instructions in a prompt ask them not to; nothing stops them.

zouj-ai-sdlc is a [Claude Code](https://code.claude.com) plugin that runs your software lifecycle as a **state
machine over Markdown artifacts versioned in Git**, modeled on Anthropic's *AI-Native SDLC Playbook*. Work starts
from an intent, every state commits an artifact the next one reads, and **humans decide at every gate**. Hooks
enforce those gates instead of relying on the model's good behaviour.

<!-- Demo GIF: record it with docs/demo/demo.tape (see docs/demo/README.md), then replace this comment with:
<p align="center"><img src="docs/demo/demo.gif" alt="Claude blocked before a plan, a human approves, Claude runs TDD" width="900"></p>
-->
**Demo:** Claude is blocked from writing code before a plan exists, the human types `Plan Approved 0001`, and Claude
runs TDD to a green `make check` (the recording script is in [docs/demo](docs/demo/)).

```mermaid
flowchart TD
  A["1 BRAINSTORMING<br/>intent.md"] -->|"✋ Intent Approved NNNN"| B["2 SPECIFICATION<br/>spec.md"]
  B -->|"✋ Spec Approved NNNN"| C["3 PLAN · code read-only<br/>plan.md"]
  C -->|"✋ Plan Approved NNNN"| D["4 EXECUTION · autonomous TDD<br/>code + tests"]
  D -->|"all steps [x] · make check green"| E["5 PRE-REVIEW<br/>review.md + pr.md"]
  E -->|"CHANGES_REQUESTED"| D
  E -->|"✋ the human merges"| F(["DONE"])
```

## Start using
Start from what you're doing. Every route runs the same playbook workflow, with a human at every gate.

| You want to… | Run | Playbook stage |
|---|---|---|
| Try the workflow first | a throwaway repo: see **Just looking?** under Install | (any, risk-free) |
| Set up this repo | type `/zouj-ai-sdlc:setup solo` (or `team`, `strict`) | (once per repo, before the loop) |
| Build a feature or change | `/zouj-ai-sdlc:intent "<need>"` → spec → plan → implement | Plan → Design → Build |
| Fix a bug | `/zouj-ai-sdlc:fix "<bug>"` (failing test first) | Test |
| Act on an alert or issue | `/zouj-ai-sdlc:triage alert:<metric>` → a new intent | Maintain → Plan (a new intent) |
| Get a branch reviewed | `/zouj-ai-sdlc:review`, then `/zouj-ai-sdlc:pr` | Deploy: AI review |
| See where you are and what's next | `/zouj-ai-sdlc:status` | any |
| Upgrade, repair or remove the setup | `sdlc list-installed`, then `sdlc upgrade`, `repair` or `uninstall --dry-run` | Maintain |
| Understand a block | `sdlc why <id>` (the id is in `BLOCKED [G-…]`) | any |
| Run a human-only command in your own terminal | `sdlc where` prints it with the plugin's full path | any |
| Not sure | `/zouj-ai-sdlc:help-me "<what you want>"` | any |

All commands: [COMMANDS-QUICK-REF.md](COMMANDS-QUICK-REF.md). Stuck? [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or
`sdlc feedback`.

## Install
Requirements: `git`, `make`, `python3` ≥ 3.9 (stdlib only), Claude Code ≥ 2.1.

**A. Guided (recommended).** In Claude Code:
```text
/plugin marketplace add zoujagger/zouj-ai-sdlc@v0.2.0-beta.1
/plugin install zouj-ai-sdlc@zouj
```
(From a terminal: `claude plugin marketplace add zoujagger/zouj-ai-sdlc@v0.2.0-beta.1`, then
`claude plugin install zouj-ai-sdlc@zouj`.)

Then, in your repo, type `/zouj-ai-sdlc:setup solo` (or `team`, `strict`) as your whole prompt. It writes the core
scaffold (missing files only), sets the repo's first profile and commits `.aiops/config.json` alone. Claude can't do
this step for you. Type `/zouj-ai-sdlc:setup` alone to preview first. Changing a profile later is a run in your own
terminal: `sdlc setup --profile solo|team|strict`.

**Just looking?** Try it in a throwaway repo:
`mkdir /tmp/sdlc-try && cd /tmp/sdlc-try && git init -q && git commit -q --allow-empty -m init`, start `claude` there
and type `/zouj-ai-sdlc:setup solo`. Commit the scaffold with the command the reply gives
(`git add … && git commit -m "chore: adopt zouj-ai-sdlc (profile solo)"`). Then run
`/zouj-ai-sdlc:intent "greet people in French"`, walk the five states, and delete the directory.

| Profile | Approval proof | For |
|---|---|---|
| `solo` | the typed phrase + an unsigned approval commit | one developer, trying it out |
| `team` | an SSH-signed commit, a human per signature ([approver setup](docs/approver-setup.md)) | most teams |
| `strict` | an `sk-` key touch per signature, plus CODEOWNERS on `/.aiops/` | regulated or high-risk repos |

**Good to know:**
- **Profiles:** they change only how an approval is proven; every gate is the same. Choose with
  `/zouj-ai-sdlc:setup solo|team|strict`. Under `team` and `strict` you approve with a signing key, from your own
  terminal: `/usr/bin/python3 -I <plugin>/bin/sdlc approve NNNN intent|spec|plan`
  ([approver setup](docs/approver-setup.md)). The escape hatch `"approval_key_policy": "any"` accepts any key, at a
  cost: anything running as you can then sign approvals.
- **Opt-in parts:** setup installs the core only. Add `review`, `maintain`, `deploy`, `governance` or `issues` with
  `sdlc setup --with <part>`.
- **Your own terminal:** `sdlc` is on PATH only inside Claude Code. `sdlc where` prints the command to run there.
- **Without `.aiops/`:** the gates are dormant, but the safety guards are always on.

**B. For a team, declaratively.** Commit this to `.claude/settings.json` (setup writes it), and Claude Code offers
the plugin to everyone who opens the repo:
```json
{
  "extraKnownMarketplaces": {
    "zouj": { "source": { "source": "github", "repo": "zoujagger/zouj-ai-sdlc", "ref": "v0.2.0-beta.1" } }
  },
  "enabledPlugins": { "zouj-ai-sdlc@zouj": true }
}
```

> **What you trust:** enabling the plugin trusts github.com/zoujagger/zouj-ai-sdlc at that ref. Its hooks run as you
> on every tool call, so every command here pins a release tag. Official sources only: this repository and the
> plugin id `zouj-ai-sdlc@zouj`.

Everything else (the terminal-only install, the parts table, configuration): [docs/install.md](docs/install.md).

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

## How it differs from prompt-only workflows
Skill and prompt workflows describe a good process and hope the model follows it. Here the process is enforced:

| | Prompt-only workflow | zouj-ai-sdlc |
|---|---|---|
| Who opens a gate | the model decides it's ready | only a human, by typing `Plan Approved NNNN` as the whole prompt |
| Enforcement | advice in the context window | hooks that block the tool call (`BLOCKED [G-…]`, `sdlc why <id>`) |
| Planning states | the model may start coding early | code is read-only until the plan is approved |
| Where state lives | the conversation | derived from Markdown artifacts and git on every call |
| Definition of done | the model says so | the Stop hook requires `make check` green |
| Audit | none | CI traces every open gate to a signed, single-file approval commit |
| Drift | a changed plan goes unnoticed | editing an approved artifact re-closes its gate |

Local hooks are a strong deterrent, not a sandbox; the signed-approval CI audit is the hard guarantee. Details:
[what is enforced](docs/enforcement.md) · [threat model](docs/architecture.md#threat-model).

## Lifecycle
`init` and `setup` record what they wrote, including the opt-in parts, in `.aiops/install-state.json`. After a plugin
update, `sdlc upgrade` refreshes the scaffold; `sdlc repair` restores missing files; `sdlc uninstall --dry-run` shows
what removal would delete. Your modified files are never touched. Blocked by mistake? `sdlc why <id>` explains the
rule. Details: [docs/lifecycle.md](docs/lifecycle.md).

## Develop
```bash
make check        # lint + compile + unit, hook and playbook-conformance tests
make validate     # claude plugin validate .
make dev          # claude --plugin-dir .
make evals        # behavioural evals against a live model
```
Docs: [install](docs/install.md) · [approver setup](docs/approver-setup.md) · [enforcement](docs/enforcement.md) ·
[lifecycle](docs/lifecycle.md) · [state machine](docs/state-machine.md) · [architecture](docs/architecture.md) ·
[playbook mapping](docs/sdlc.md) · [governance](docs/governance.md) · [adoption ladder](docs/adoption.md) ·
[roadmap](docs/roadmap.md) · [worked example](docs/examples/0001-csv-export/).
This repo dogfoods itself:
see [`.aiops/0001-zouj-ai-sdlc-plugin/`](.aiops/0001-zouj-ai-sdlc-plugin/).
