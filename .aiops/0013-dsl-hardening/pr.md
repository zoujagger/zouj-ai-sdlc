<!-- PR description for intent 0013, generated in state 5. `gh pr create --body-file` it. -->
## Harden the dsl part: safe detection, validator edge cases, implement and review guidance

**Intent:** `.aiops/0013-dsl-hardening/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 95/100 at `5ee366a`

### What and why
This fixes the 0012 review's pre-release findings and completes the second half of the 0012 split. 0012 is
unreleased, so no adopter ever sees the problems fixed here:

- **Safe detection.** The part is active only when install-state names `dsl` or a `domain/*.dsl.json` file exists.
  A repo's own `domain/` source folder (DDD, Go, Python) no longer gets a failing `make check` after `upgrade` or a
  new `## Domain DSL` requirement. The Makefile's `validate-dsl` runs the validator when `scripts/validate-dsl.py`
  exists, fails with the `sdlc setup --with dsl` hint when only model files exist, and skips otherwise.
- **A hardened validator:**
  - a non-string `kind`, `from`, `to`, `initial`, `final`, `start` or `next` is a reported problem, never a
    traceback;
  - a symlinked `domain/` exits 1 instead of being skipped;
  - set lookups make it linear: 80,000 states take **0.14 s** instead of 24.7 s.
- **State 4** updates and validates `domain/*.dsl.json` before application code.
- **State 5's code-reviewer** looks for transitions and rules hardcoded in controllers, handlers and UI. Each
  confirmed case is a **MEDIUM** finding in `## Domain model`, 3 points off Spec conformance.
- **The docs and the unreleased 0012 CHANGELOG entry** now describe activation by model files.

### Acceptance criteria
- [x] AC-1: a bare `domain/` activates nothing; a model file or install-state does
  (`tests/test_engine.py::DomainDsl`, `tests/test_cli.py::…::test_draft_spec_adds_domain_dsl_when_active`)
- [x] AC-2: the recipe's three branches, and wired Makefiles through `upgrade` (`tests/test_dsl.py::MakeCheck`,
  `tests/test_lifecycle.py::Detected::test_wired_makefile_keeps_recipes_with_validate_dsl`)
- [x] AC-3: no traceback, a reported link, linear time (`tests/test_dsl.py::ValidateDsl::test_non_string_references`,
  `::test_symlinked_domain_dir`, `::test_file_named_domain_is_skipped`, `::test_large_model_is_linear`)
- [x] AC-4: model first in State 4 (`tests/test_cli.py::Docs::test_dsl_hardening_guidance`)
- [x] AC-5: the hardcoding check, and the corrected wording (same test, with a scan for the old phrases);
  `make check` green

### Deviations from plan
- **S5:** `README.md` and `templates/scaffold/.aiops/README.md` needed no change. They don't describe activation by
  `domain/`, and the old-wording test still scans them.

### Risks and rollback
- **Accepted:** deleting or renaming the model files lifts the requirement in CI, as deleting `domain/` did. It's
  visible in the PR diff, and install-state keeps the requirement on locally.
- **Non-blocking backlog** (review.md):
  - `$.kind: missing` wording;
  - edge cases where the engine, Makefile and validator disagree (dotfile and dangling-link models);
  - an unreadable `domain/` traceback, which fails closed;
  - an untested `OSError` branch;
  - two wording nits.
- **Rollback:** revert the PR. Don't release 0012 without this.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
