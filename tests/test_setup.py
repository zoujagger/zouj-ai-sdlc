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


def stub(bindir, name, body):
    f = bindir / name
    f.write_text("#!/bin/sh\n" + body + "\n")
    f.chmod(0o755)


class Preflight(RepoCase):
    def bin_with(self, claude="2.1.40 (Claude Code)", gh_scopes="'gist', 'read:org', 'repo'", git=True):
        """A PATH with stub tools; gh logs every argument list it gets to gh.log."""
        bindir = self.root.parent / f"{self.root.name}.bin"
        bindir.mkdir(exist_ok=True)
        if claude:
            stub(bindir, "claude", f"echo '{claude}'")
        stub(bindir, "make", "exit 0")
        stub(bindir, "gh", f'echo "$@" >> "{bindir}/gh.log"\n'
                           f'[ "$1 $2" = "auth status" ] && echo "  - Token scopes: {gh_scopes}"\nexit 0')
        if git:
            (bindir / "git").symlink_to(shutil.which("git"))
        return bindir

    def test_rows_and_blocking(self):
        from sdlc_engine import setup
        bindir = self.bin_with(claude="2.0.9 (Claude Code)")
        r = self.run_sdlc("setup", "--profile", "solo", "--dry-run", env={"PATH": str(bindir)})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Preflight", r.stdout)
        self.assertRegex(r.stdout, r"! claude 2\.0\.9 \(>= 2\.1")                    # too old: warn, continue
        self.assertIn("gh auth refresh -h github.com -s workflow", r.stdout)       # missing scope: the fix
        self.assertIn("! git credential helper", r.stdout)
        self.assertIn("gh auth setup-git", r.stdout)
        log = (bindir / "gh.log").read_text()
        self.assertIn("auth status", log)
        self.assertNotRegex(log, r"(^|\s)(-t|--show-token)(\s|$)")                 # never print the token
        # git missing from PATH: ✗ and setup stops before writing anything
        bindir2 = self.bin_with(git=False)
        (bindir2 / "git").unlink(missing_ok=True)
        r = self.run_sdlc("setup", "--profile", "solo", "--yes", env={"PATH": str(bindir2)})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("✗ git", r.stdout)
        self.assertIn("nothing was written", r.stdout)
        self.assertFalse((self.root / "CLAUDE.md").exists())
        # python older than 3.9: ✗ and blocking
        rows = setup.preflight(self.root, "solo", version=(3, 8, 10))
        self.assertTrue(any(st == "✗" and "python" in label for st, label, _ in rows), rows)
        self.assertTrue(setup.blocking(rows))
        # a hung tool times out into a warning instead of hanging setup
        bindir = self.bin_with()                                                  # git is back on PATH
        stub(bindir, "claude", "sleep 30")
        rows = setup.preflight(self.root, "solo", path=str(bindir), timeout=1)
        self.assertTrue(any(st == "!" and "claude" in label for st, label, _ in rows), rows)
        self.assertFalse(setup.blocking(rows))


if __name__ == "__main__":
    unittest.main()
