<!-- PR description for intent 0012, generated in state 5. `gh pr create --body-file` it. -->
## Opt-in dsl part: a validated domain/ model for specs and plans

**Intent:** `.aiops/0012-dsl-part/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 89/100 at `05e793f`

### What and why
Teams that want domain-first modeling had no supported way to ask for it, and the plugin must not assume a business
domain. This adds an opt-in `dsl` part, the first half of the split request; implement and review are the next
intent, 0013:

- **`sdlc setup --with dsl`** adds `domain/README.md` (the format) and `scripts/validate-dsl.py`, a stdlib-only
  validator for state machines, rule sets and workflows in `domain/*.dsl.json`. It reports
  `<file>: <json path>: <problem>`. `--with all` leaves `dsl` out, and repos set up before this never get it from
  `upgrade` or `repair` (`LEGACY_PARTS`).
- **`make check`** runs `validate-dsl`, which is skipped without `domain/`. A Makefile you've edited isn't changed:
  setup prints the target to add.
- **While the part is active** (`domain/` exists, or install-state names `dsl`), `sdlc validate` requires
  `## Domain DSL` in specs whose gate is closed, naming the model files or saying `No domain changes`. `sdlc draft`
  adds the section. Approved specs are exempt, so turning the part on in a repo with history stays green.
- **The spec and plan skills** and the architect and planner model the domain before the Data model, and plan
  Step 1 updates `domain/` and runs `make validate-dsl`.

### Acceptance criteria
- [x] AC-1: explicit opt-in, recorded, only missing files written
  (`tests/test_setup.py::Apply::test_with_dsl_installs_the_part`, `::test_with_all_leaves_dsl_out`,
  `tests/test_lifecycle.py::DslPart`)
- [x] AC-2: the validator's exit codes and located problem lines (`tests/test_dsl.py::ValidateDsl`)
- [x] AC-3: `make check` is dormant without `domain/`, fails on an invalid model, and keeps wired recipes
  (`tests/test_dsl.py::MakeCheck`, `tests/test_lifecycle.py::Detected::test_wired_makefile_keeps_recipes_with_validate_dsl`)
- [x] AC-4: the conditional `## Domain DSL` section and the draft (`tests/test_engine.py::DomainDsl`,
  `tests/test_cli.py::…::test_draft_spec_adds_domain_dsl_when_active`)
- [x] AC-5: the guidance ships (`tests/test_cli.py::Docs::test_dsl_guidance`); `make check` 559 OK

### Deviations from plan
Nine are logged in plan.md. The main ones:
- **S1:** seven existing tests now read "every part" as the five older parts.
- **S2:** `typecheck` uses `compile()` (no `__pycache__` in the scaffold), and an E741 is fixed in `check-bands.py`.
- **S4 (confirmed by the human):** approved, unchanged specs are exempt from `## Domain DSL`, as 0011's
  `scope_size` is.
- **S6:** the manual scratch-repo run was denied by permissions; `MakeCheck` and the setup test cover it.

### Risks and rollback
- **Before release (review):** a repo with its own top-level `domain/` source directory activates the part
  without `--with dsl`. After `upgrade`, its `make check` fails ("scripts/validate-dsl.py is missing") and its
  specs require `## Domain DSL`. Decide whether to key activation on `domain/*.dsl.json`.
- **Validator robustness:** three LOW issues (a `TypeError` on unhashable values, O(n²) membership, a symlinked
  `domain` skipped) are in the review backlog.
- **Rollback:** revert the PR. Repos that installed the part keep `domain/` and the script as their own files.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
