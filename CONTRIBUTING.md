# Contributing to zouj-ai-sdlc

This repo dogfoods the plugin. Load it with `make dev` (`claude --plugin-dir .`) and follow the five states:

1. **Intent.** `/zouj-ai-sdlc:intent "<need>"` → `.aiops/NNNN-slug/intent.md`. A maintainer types `Intent Approved NNNN`.
2. **Spec.** `/zouj-ai-sdlc:spec`: requirements, ACs, contracts (CLI flags, hook JSON, schemas) and security flags → `Spec Approved NNNN`.
3. **Plan.** `/zouj-ai-sdlc:plan`, read-only → `Plan Approved NNNN`.
4. **Execute.** `/zouj-ai-sdlc:implement`. Guard and engine changes are test-first in `tests/`. `make check` must be green.
5. **Review.** `/zouj-ai-sdlc:review` → `review.md` + `pr.md`, then `/zouj-ai-sdlc:pr`. A CODEOWNER merges.

Exempt from the flow: typos and docs-only changes (`*.md`, `docs/`).

## Checks
- `make check`: bash syntax, shellcheck and ruff (if installed), JSON validity, byte-compile, and the unit and hook tests.
- `make validate`: `claude plugin validate .`.
- `make evals`: behavioural evals (`claude plugin eval`). Run them when you change skills, agents, hooks or schemas.
- `python3 scripts/scaffold-history.py [--check]`: regenerates (or checks) `defaults/scaffold-history.json`, the hash
  of every scaffold file in every release, which `sdlc upgrade`/`repair` use to adopt older repos. Run it when you
  change `templates/scaffold/` or `templates/stacks/`, and at each release.

## Using AI responsibly
You're accountable for every line you merge. Never bypass a hook: it says why it blocked you and what to do.

## Commit style
[Conventional Commits](https://www.conventionalcommits.org/), with footer `Refs: .aiops/NNNN-slug`.
