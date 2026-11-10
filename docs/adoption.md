# Adoption ladder

The playbook's advice is to start small: pick one play, run it by hand, then codify it and automate its trigger. This
page is that advice for zouj-ai-sdlc. Each step works without the next one, and every step from 1 up runs the same
workflow with a human at every gate. There is no step without the gates.

| Step | You get | You do | Move up when |
|---|---|---|---|
| 0 Plugin only | The safety guards in every repo: secret reads and writes, force-push, history rewrites, production deploys, your toolchain | Install the plugin ([README](../README.md#install)). No repo is changed | You want the workflow in a repo |
| 1 `solo`, one repo | The five states and the read-only lock. An approval is the typed phrase plus an unsigned commit | `<plugin>/bin/sdlc setup --profile solo` in your terminal, commit the scaffold, then `/zouj-ai-sdlc:intent "<need>"` | A second person merges your changes |
| 2 `team` | Signed approvals that CI audits; teammates are offered the plugin when they open the repo | `<plugin>/bin/sdlc setup --profile team`, one signing key per approver, `aiops-gates / audit` as a required check, CODEOWNERS on `.aiops/` ([branch protection](../templates/scaffold/docs/branch-protection.md)) | The repo is regulated or high-risk |
| 3 `strict` + the loop | An `sk-` key touch per approval, org-wide settings, and the Maintain loop feeding new intents | `<plugin>/bin/sdlc setup --profile strict`, managed settings ([governance](governance.md#org-level-enforcement)), real queries in `ops/bands.yaml` | — |

`<plugin>` is the installed plugin's folder: see [Where is `<plugin>`?](../README.md#install) in the README.

## Step 0: try it without touching a real project
The README's **Just looking?** recipe walks the five states in a throwaway repo under `solo`. It takes a few terminal
commands and a few prompts, and you delete the directory afterwards.

## Step 1: what to wire first
- **`make check`.** The scaffold's Makefile targets print `not configured` and count as a pass until you wire them
  (`sdlc init --stack python|node|go` fills in a preset). State 4 proves nothing until `make check` checks something.
  `sdlc doctor` lists the unwired targets.
- **CLAUDE.md.** Add your stack and conventions under "Project notes", and keep the file to about a page.
- **One policy.** Replace the defaults in one `policy-*` skill with your organization's rule, starting with the one
  your reviews cite most.

## The workflows the scaffold adds
Setup writes every workflow at once. They don't all need to run on day one:

| Workflow | Needs | Leave for later? |
|---|---|---|
| `aiops-gates.yml`, `ci.yml` | nothing | No: these are the audit and your checks |
| `claude-pr-review.yml`, `claude.yml`, `claude-issue-triage.yml`, `claude-release-notes.yml` | `ANTHROPIC_API_KEY` (or the Claude GitHub App) | Yes, until the secret is set |
| `claude-maintain.yml` (every 30 minutes), `claude-scheduled-scan.yml` (weekly) | the secret, and real metric queries in `ops/bands.yaml` | Yes: step 3 |
| `deploy.yml` | `make deploy` wired, GitHub Environments `staging` and `production` | Yes, until you deploy from CI |

To hold one back without deleting it, disable it on GitHub: `gh workflow disable claude-maintain.yml`. A deleted
scaffold file shows as `missing` in `sdlc list-installed`, and `sdlc repair` would restore it.

## Step 3: close the loop
1. Point one metric in `ops/bands.yaml` at your monitoring system and let it collect a baseline.
2. Enable `claude-maintain.yml`. A band 2 breach opens a PR with a draft `intent.md` for the service owner to triage.
3. Turn each production incident into a regression eval (`/zouj-ai-sdlc:postmortem`).
