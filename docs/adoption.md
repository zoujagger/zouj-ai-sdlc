# Adoption ladder

The playbook's advice is to start small: pick one play, run it by hand, then codify it and automate its trigger. This
page is that advice for zouj-ai-sdlc. Each step works without the next one, and every step from 1 up runs the same
workflow with a human at every gate. There is no step without the gates.

| Step | You get | You do | Move up when |
|---|---|---|---|
| 0 Plugin only | The safety guards in every repo: secret reads and writes, force-push, history rewrites, production deploys, your toolchain | Install the plugin ([README](../README.md#install)). No repo is changed | You want the workflow in a repo |
| 1 `solo`, one repo | The five states and the read-only lock. An approval is the typed phrase plus an unsigned commit | `/zouj-ai-sdlc:setup solo`, type `Setup Profile solo` as your whole prompt, commit the scaffold, then `/zouj-ai-sdlc:intent "<need>"` | A second person merges your changes |
| 2 `team` | Signed approvals that CI audits; teammates are offered the plugin when they open the repo | In a new repo, `/zouj-ai-sdlc:setup team` and `Setup Profile team`; moving up from `solo`, `<plugin>/bin/sdlc setup --profile team` in your terminal. Then one signing key per approver, `aiops-gates / audit` as a required check, CODEOWNERS on `.aiops/` ([branch protection](../templates/scaffold/docs/branch-protection.md)) | The repo is regulated or high-risk |
| 3 `strict` + the loop | An `sk-` key touch per approval, org-wide settings, and the Maintain loop feeding new intents | `<plugin>/bin/sdlc setup --profile strict --with maintain` in your terminal, managed settings ([governance](governance.md#org-level-enforcement)), real queries in `ops/bands.yaml` | — |

The typed phrase sets a repo's **first** profile. Changing one that is set is a run in your own terminal:
`sdlc where` (in Claude Code) prints the full command that `<plugin>/bin/sdlc` stands for.

## Step 0: try it without touching a real project
The README's **Just looking?** recipe walks the five states in a throwaway repo under `solo`. It takes one terminal
line to create the repo, then a few prompts, and you delete the directory afterwards.

## Step 1: what to wire first
- **`make check`.** The scaffold's Makefile targets print `not configured` and count as a pass until you wire them
  (`sdlc init --stack python|node|go` fills in a preset). State 4 proves nothing until `make check` checks something.
  `sdlc doctor` lists the unwired targets.
- **CLAUDE.md.** Add your stack and conventions under "Project notes", and keep the file to about a page.
- **One policy.** Replace the defaults in one `policy-*` skill with your organization's rule, starting with the one
  your reviews cite most.

## The workflows the scaffold adds
Setup installs the core scaffold, and the rest arrives by part when you ask for it
(`sdlc setup --with <part>[,<part>…]`, or `--with all`):

| Part | Workflows | Needs | Add it at |
|---|---|---|---|
| core (always) | `aiops-gates.yml`, `ci.yml` | nothing | step 1: these are the audit and your checks |
| `review` | `claude-pr-review.yml`, `claude.yml` | `ANTHROPIC_API_KEY` (or the Claude GitHub App) | step 2, once the secret is set |
| `issues` | `claude-issue-triage.yml`, the issue forms | the secret, for triage | step 2 |
| `governance` | none: policy examples, branch-protection notes, `docs/adr/`, Dependabot | nothing | step 2 |
| `deploy` | `deploy.yml`, `claude-release-notes.yml` | `make deploy` wired, GitHub Environments `staging` and `production` | when you deploy from CI |
| `maintain` | `claude-maintain.yml` (every 30 minutes), `claude-scheduled-scan.yml` (weekly) | the secret, and real metric queries in `ops/bands.yaml` | step 3 |

`--with` only adds, and `sdlc list-installed` ends with the parts you don't have. A repo set up before
0.2.0-alpha.4 has every part. To hold a workflow back there without deleting it, disable it on GitHub:
`gh workflow disable claude-maintain.yml`. A deleted file of an installed part shows as `missing` in
`sdlc list-installed`, and `sdlc repair` would restore it.

## Step 3: close the loop
1. Add the part if the repo doesn't have it (`sdlc setup --with maintain`), point one metric in `ops/bands.yaml` at
   your monitoring system and let it collect a baseline.
2. Enable `claude-maintain.yml`. A band 2 breach opens a PR with a draft `intent.md` for the service owner to triage.
3. Turn each production incident into a regression eval (`/zouj-ai-sdlc:postmortem`).
