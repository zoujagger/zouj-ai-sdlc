"""Shared fixtures: a throwaway git repo initialized for zouj-ai-sdlc, and valid artifact bodies."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from sdlc_engine import approvals  # noqa: E402

SDLC = str(ROOT / "bin" / "sdlc")

INTENT = """---
id: {id}
title: CSV export
status: Draft
owner: po
created: 2026-10-30
---
# Intent: CSV export

## Problem
Users cannot export contacts.

## Desired outcome
A CSV download exists.

## Users & systems affected
- Users: sales reps

## Constraints
- none

## Out of scope
- XLSX

## Open questions
- [ ] Max rows? (po)
"""

SPEC = """---
id: {id}
title: CSV export
status: Draft
risk: low
---
# Spec

## Summary
Export contacts.

## Requirements
- R-1 export

## Acceptance criteria
- **AC-1**: Given contacts, when exporting, then a CSV is returned.
- **AC-2**: Given another tenant, when exporting, then 403.

## Data model
No change.

## API contracts
GET /contacts.csv

## Security & data-leak flags
- tenant isolation

## Architecture
Reuse the list query.

## Rollout & rollback
Flag `csv_export`.

## Open questions
- none
"""

PLAN = """---
id: {id}
title: CSV export
status: Draft
---
# Plan

## Approach
Small.

## Steps
- [ ] **S1**: add the endpoint (AC-1)
- [ ] **S2**: tenant check (AC-2)

## Risks
| Risk | L | I | M |
|---|---|---|---|

## Test definitions
| AC | Test |
|---|---|
| AC-1 | tests/test_csv.py::test_export |
| AC-2 | tests/test_csv.py::test_tenant |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
"""

REVIEW = """---
id: {id}
verdict: {verdict}
commit: {commit}
score: 90/100
---
# Review

## Summary
ok

## Spec conformance
| AC-1 | met | | AC-2 | met |

## Security
None found.

## Plan conformance
ok

## Test-first evidence
ok

## Score
90
"""


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


class RepoCase(unittest.TestCase):
    """Each test gets a fresh repo at self.root with `.aiops/` and intent 0001 on branch feat/0001-csv-export."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION", "AIOPS_INTENT", "SDLC_HOOK_PROFILE",
                                 "CLAUDE_PROJECT_DIR")}
        self._saved_env = dict(os.environ)
        os.environ.clear()
        os.environ.update(self.env)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.name", "Human Owner")
        git(self.root, "config", "user.email", "owner@example.com")
        git(self.root, "config", "commit.gpgsign", "false")
        (self.root / "README.md").write_text("x\n")
        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_text("x = 1\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        (self.root / ".aiops" / "state").mkdir(parents=True)
        self.d = self.root / ".aiops" / "0001-csv-export"
        self.d.mkdir()
        git(self.root, "switch", "-qc", "feat/0001-csv-export")

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_env)
        self._tmp.cleanup()

    # artifact helpers
    def write(self, kind, text):
        (self.d / f"{kind}.md").write_text(text.format(id="0001", verdict="PASS", commit="0" * 40)
                                           if "{id}" in text else text)

    def approve(self, kind):
        ok, msg = approvals.approve(self.root, self.d, kind, via="test")
        self.assertTrue(ok, msg)
        return msg

    def to_execution(self):
        self.write("intent", INTENT)
        self.approve("intent")
        self.write("spec", SPEC)
        self.approve("spec")
        self.write("plan", PLAN)
        self.approve("plan")

    def hook_input(self, tool, **ti):
        return {"tool_name": tool, "tool_input": ti, "cwd": str(self.root), "hook_event_name": "PreToolUse"}

    def run_sdlc(self, *args, stdin="", env=None):
        return subprocess.run([sys.executable, SDLC, *args], cwd=self.root, input=stdin, capture_output=True,
                              text=True, env={**self.env, **(env or {})})

    def hook(self, event, payload, env=None):
        return self.run_sdlc("hook", event, stdin=json.dumps(payload), env=env)
