"""`sdlc setup`: guided, rerunnable onboarding that keeps the playbook workflow in every profile."""
import shutil
import unittest

from helpers import RepoCase

from sdlc_engine import cli


class Init(RepoCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")

    def test_init_actions_preview_matches_apply(self):
        (self.root / "Makefile").write_text("mine:\n\techo keep\n")
        actions = cli.init_actions(self.root)
        created = {rel for act, rel in actions if act == "create"}
        kept = {rel for act, rel in actions if act == "keep"}
        self.assertIn("Makefile", kept)
        self.assertIn(".aiops/config.json", created)
        self.assertFalse((self.root / ".aiops" / "config.json").exists())       # previewing writes nothing
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        for rel in created | kept:
            self.assertTrue((self.root / rel).exists(), rel)
        self.assertEqual((self.root / "Makefile").read_text(), "mine:\n\techo keep\n")
        again = cli.init_actions(self.root)
        self.assertEqual({act for act, _ in again}, {"keep"})                    # a rerun plans no creation


if __name__ == "__main__":
    unittest.main()
