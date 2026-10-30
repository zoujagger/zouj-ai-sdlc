"""`sdlc` CLI: init (non-destructive scaffold), new/draft/use/status/validate, lock/unlock."""
import json
import shutil
import unittest

from helpers import INTENT, RepoCase


class Init(RepoCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")

    def test_scaffolds_without_overwriting(self):
        (self.root / "Makefile").write_text("mine:\n\techo keep\n")
        r = self.run_sdlc("init")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.root / "Makefile").read_text(), "mine:\n\techo keep\n")
        self.assertIn("Kept existing", r.stdout)
        for rel in (".aiops/README.md", ".aiops/config.json", ".aiops/state", "REVIEW.md", "CLAUDE.md",
                    ".github/workflows/aiops-gates.yml", "ops/bands.yaml"):
            self.assertTrue((self.root / rel).exists(), rel)
        self.assertIn(".aiops/state/", (self.root / ".gitignore").read_text())
        self.assertEqual(self.run_sdlc("init").returncode, 0)   # idempotent
        self.assertEqual((self.root / ".gitignore").read_text().count(".aiops/state/"), 1)

    def test_stack_preset_wires_the_makefile(self):
        r = self.run_sdlc("init", "--stack", "python")
        self.assertIn("wired format, lint, typecheck, test, build", r.stdout)
        self.assertIn("pytest -q", (self.root / "Makefile").read_text())

    def test_unknown_stack_fails(self):
        self.assertEqual(self.run_sdlc("init", "--stack", "cobol").returncode, 1)


class Lifecycle(RepoCase):
    def test_new_draft_status_validate(self):
        shutil.rmtree(self.d)
        r = self.run_sdlc("new", "csv-export", "--title", "CSV export")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("feat/0001-csv-export", r.stdout)
        self.assertTrue((self.d / "intent.md").is_file())
        self.assertEqual(self.run_sdlc("draft", "0001", "spec").returncode, 1)     # intent not approved
        st = json.loads(self.run_sdlc("status", "--json").stdout)
        self.assertEqual((st["state"], st["waiting_on"]), (1, "human"))
        self.assertEqual(self.run_sdlc("validate").returncode, 0)                   # template is structurally valid
        self.write("intent", INTENT)
        self.assertEqual(self.run_sdlc("approve", "1", "intent").returncode, 0)
        self.assertEqual(self.run_sdlc("draft", "0001", "spec").returncode, 0)
        self.assertIn("2 SPECIFICATION", self.run_sdlc("status").stdout)

    def test_status_table_without_active_intent(self):
        self.write("intent", INTENT)
        self.run_sdlc("new", "other")
        (self.root / ".aiops" / "state" / "active").unlink()
        from helpers import git
        git(self.root, "switch", "-qc", "chore/x")
        out = self.run_sdlc("status").stdout
        self.assertIn("| 0001-csv-export | 1 BRAINSTORMING", out)
        self.assertIn("| 0002-other |", out)

    def test_validate_ci_fails_on_agent_authored_approval(self):
        from helpers import git
        from sdlc_engine import artifacts as A
        self.write("intent", INTENT)
        text = (self.d / "intent.md").read_text()
        (self.d / "intent.md").write_text(A.set_fields(text, {
            "status": "Approved", "approved-by": "bot", "approved-sha256": A.approval_hash("intent", text)}))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "intent", "-m", "Co-Authored-By: Claude <noreply@anthropic.com>")
        self.assertEqual(self.run_sdlc("validate", "--all").returncode, 0)
        r = self.run_sdlc("validate", "--all", "--ci")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not an approval commit", r.stdout)

    def test_lock_is_agent_settable_but_only_human_releasable(self):
        self.assertEqual(self.run_sdlc("lock", env={"CLAUDECODE": "1"}).returncode, 0)
        self.assertTrue((self.root / ".aiops" / "state" / "test-lock").exists())
        self.assertEqual(self.run_sdlc("unlock", env={"CLAUDECODE": "1"}).returncode, 1)
        self.assertEqual(self.run_sdlc("unlock").returncode, 0)
        self.assertFalse((self.root / ".aiops" / "state" / "test-lock").exists())


if __name__ == "__main__":
    unittest.main()
