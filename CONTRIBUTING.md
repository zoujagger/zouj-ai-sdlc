# Contributing

Every change follows the AI-native SDLC in [docs/sdlc.md](docs/sdlc.md):

1. **Intent.** Open an *Intent* issue, or run `/intent "<need>"`. The product owner validates `docs/intents/NNNN-slug/intent.md`.
2. **Design.** `/spec NNNN` produces `spec.md` (requirements + design, flags, policy conflicts). A human accepts it.
3. **Build.** `/plan NNNN` in Plan mode → stress-test → `plan.md`. Then `/implement`.
   When code diverges from the plan, update `plan.md` in the same commit.
4. **Test.** `make check` must pass (the Stop hook enforces it). `/verify` for an independent check. Bugs go through `/fix`.
5. **Deploy.** `/review` → `/pr`. Claude reviews per [REVIEW.md](REVIEW.md), and a CODEOWNER approves. `/deploy` goes to staging, and production needs a named approver.
6. **Maintain.** Alerts and tickets become new intents (`/triage`).

Exempt from intent/spec/plan: typos, docs-only changes, dependency bumps.

## Using AI responsibly
- You're accountable for every line you merge. Disclose AI assistance in the PR template.
- Never bypass hooks. If one blocks you, it says why and what to do.
- Changing `CLAUDE.md`, skills, hooks, or `REVIEW.md`? The eval suite runs on your PR.
- See [docs/ai-usage-policy.md](docs/ai-usage-policy.md) and [docs/governance.md](docs/governance.md).

## Commit style
[Conventional Commits](https://www.conventionalcommits.org/), with footer `Refs: docs/intents/NNNN-slug`.
