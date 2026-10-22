# Evals: continuous evaluation of the agent setup

`CLAUDE.md`, skills, hooks and `REVIEW.md` are code that shapes agent behavior, so changes to them are tested like code.
`claude-evals.yml` runs this suite on every PR that touches them.

## Task format (`evals/tasks/<id>.yaml`)
```yaml
id: fix-does-not-edit-tests
description: During /fix the agent repairs code without touching locked tests
source: lesson            # seed | lesson | incident:<docs/postmortems/file.md>
setup: |                  # shell, run in a fresh worktree; committed automatically afterwards
  ...
prompt: |                 # sent to `claude -p` headless
  ...
check: |                  # shell, run in the worktree after Claude finishes; exit 0 = pass
  ...                     # $EVAL_OUTPUT = file holding Claude's final output
max_turns: 30
```

## Running
```bash
python3 scripts/run-evals.py --dry-run          # list tasks
python3 scripts/run-evals.py                    # run all (needs `claude` CLI + ANTHROPIC_API_KEY)
python3 scripts/run-evals.py --only intent-first
```
Each task runs in a throwaway `git worktree` with the repo's real `.claude/` config, so the hooks are exercised too.
Requires `pyyaml` (`pip install pyyaml`).

## Growing the suite
- Target **20-50 tasks drawn from real work**. The seeds here are only examples.
- **Every production incident becomes a regression eval** (`/postmortem` → `/learn`).
- Every repeated agent mistake that earned a CLAUDE.md lesson gets an eval that would have caught it.
- Keep checks deterministic (files, exit codes, git diff). Use output grep only as a last resort.
