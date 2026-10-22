# AI-Native SDLC Template

A **stack-agnostic** boilerplate that implements Anthropic's *AI-Native SDLC Playbook* with
[Claude Code](https://docs.claude.com/en/docs/claude-code). Work **starts from an intent**, every stage commits an artifact the next stage reads,
hooks enforce the absolute rules, and humans decide at every gate.

```
Trigger: INTENT → 1 PLAN → 2 DESIGN → 3 BUILD → 4 TEST → 5 DEPLOY → 6 MAINTAIN ─┐
  /intent          (validate)  /spec      /plan      /verify   /review   /triage   │
  intent.md                    spec.md    /implement /fix      /pr       bands.yaml │
     ▲                                    plan.md    evals     /deploy             │
     └──────────────────────── diagnosis becomes a new intent.md ──────────────────┘
```

## What's inside
| Component | Location | Purpose |
|---|---|---|
| Project memory | `CLAUDE.md` | The loop, rules, definition of done, Lessons (about one page) |
| Workflow | `docs/sdlc.md` | Stage-by-stage guide (roles, artifacts, gates) |
| Review rules | `REVIEW.md` | 3-pass PR review: bugs, security, conformance to spec and plan |
| Governance | `docs/governance.md`, `governance/` | Sources of truth, audit trail, metrics, anti-patterns, managed settings |
| Change artifacts | `docs/intents/NNNN-slug/` | `intent.md` → `spec.md` → `plan.md` |
| **Skills** | `.claude/skills/` | Workflow: `/intent` `/spec` `/plan` `/implement` `/parallel` `/verify` `/fix` `/review` `/security-check` `/pr` `/release` `/deploy` `/triage` `/incident` `/postmortem` `/retro` `/learn` `/adr` `/sdlc` `/onboard` · Policy (auto-applied): security, compliance, UX, brand |
| **Subagents** | `.claude/agents/` | product-analyst, architect, planner, implementer, test-engineer, **verifier**, code-reviewer, security-reviewer, docs-writer, release-manager, **diagnostician**, incident-responder |
| **Hooks** | `.claude/hooks/` | guard-bash, guard-files, **guard-tests** (test lock), **guard-deploy** (prod gate), post-edit format+lint, stop-verify (definition of done), session-start |
| **Evals** | `evals/`, `scripts/run-evals.py` | Continuous evaluation of the agent setup; incidents become regression evals |
| **Control bands** | `ops/bands.yaml`, `scripts/check-bands.py` | Deterministic 1σ/2σ/3σ detection → log / diagnose / PR or runbook |
| **GitHub automation** | `.github/workflows/` | `ci`, `claude` (@claude), `claude-pr-review`, `claude-issue-triage`, `claude-evals`, `deploy` (staging auto, prod gated, 1-command rollback), `claude-maintain`, `claude-scheduled-scan`, `claude-release-notes` |
| Build contract | `Makefile` | `format lint typecheck test build check deploy rollback evals` |

## Quickstart

### 1. Install prerequisites
| Tool | Needed? | Used for |
|---|---|---|
| `git`, `make`, `python3` + `pyyaml` | **Required** | Repo, contract commands, hooks, evals and control bands |
| [Claude Code](https://docs.claude.com/en/docs/claude-code) | **Required** | The AI collaborator in every stage |
| `gh` (GitHub CLI) | Optional | Opening PRs and reading issues from the terminal (`/pr`, `/intent #12`) |
| `jq` | Optional | Faster hook JSON parsing (hooks fall back to python3) |

**Ubuntu / Debian / WSL**
```bash
sudo apt-get update && sudo apt-get install -y git make python3 python3-yaml jq
sudo apt-get install -y gh            # optional
```

**macOS** (with [Homebrew](https://brew.sh))
```bash
brew install git make python pyyaml jq
brew install gh                       # optional
```

**Windows**: use WSL. In an **admin PowerShell**, run `wsl --install`, reboot, open *Ubuntu*, and follow the Ubuntu steps above.

**Claude Code** (any OS)
```bash
curl -fsSL https://claude.ai/install.sh | bash     # native installer, no Node.js needed
# or: npm install -g @anthropic-ai/claude-code
claude                                             # first run: log in
```

**GitHub CLI login** (optional): `gh auth login`

**Check everything is ready:**
```bash
git --version && make --version | head -1 && python3 -c "import yaml; print('pyyaml ok')" && claude --version
```

### 2. Set up the project
Create your repo with **"Use this template"** on GitHub (no `gh` needed), then clone it. Or use the CLI: `gh repo create my-project --private --template <owner>/ai-native-sdlc-template --clone`.
```bash
cd my-project
scripts/bootstrap.sh my-project my-github-org   # check tools, personalise, git init if needed
$EDITOR Makefile                                # wire your stack into the contract targets
make validate-template && make check
```
Repo admins (once): add the `ANTHROPIC_API_KEY` secret (Settings → Secrets and variables → Actions, or `gh secret set ANTHROPIC_API_KEY`, or `/install-github-app` in Claude Code), then apply [branch protection and environments](docs/branch-protection.md).

### 3. Start working
```bash
claude
> /onboard
> /intent "Users can export their account data as CSV"
```

## One change, end to end
```text
/intent "CSV export"   → docs/intents/0001-csv-export/intent.md      ✋ product owner validates
/spec 0001             → spec.md (requirements + design, flags,       ✋ accepted (+ tech lead if high risk)
                          policy conflicts)
/plan 0001             → Plan mode → stress test → plan.md            ✋ engineer accepts
/implement             → TDD per task; plan.md updated with any deviation in the same commit
/verify                → fresh-context verifier: VERIFIED?
/review → /pr          → Claude reviews per REVIEW.md (comments only)  ✋ CODEOWNER approves
/deploy                → staging + prod handoff                       ✋ named human approves production
/triage alert:api_error_rate → diagnosis → new intent.md              ✋ service owner: fix / schedule / close
```
Bug? `/fix "<bug>"`: failing test → you approve it → tests locked → fix.
Repeated mistake? `/learn`: a lesson in CLAUDE.md plus a regression eval.

## Guardrails
- **Hooks (deterministic):** force-push, push to main, destructive deletes, `curl | sh`, reading `.env`, `--no-verify`, merging PRs,
  writing credentials, editing protected paths (`.claude/protected-paths`), editing tests under the test lock, **any production deploy**.
- **Ask first:** `git push`, `gh pr create`, `gh issue create`, tags, releases.
- **Definition of done:** Claude can't end a turn with changes while `make check` fails.
- **Org level:** `governance/managed-settings.example.json`.

## Requirements
See [Quickstart → Install prerequisites](#1-install-prerequisites). Maintainers who also want full template validation locally can install `shellcheck` and `actionlint` (CI installs them automatically).
