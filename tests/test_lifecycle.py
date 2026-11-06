"""Install state and the lifecycle commands: list-installed, repair, upgrade, uninstall (0004)."""
import hashlib
import json
import shutil
import unittest

from helpers import ROOT, RepoCase
from test_setup import SetupCase

VERSION = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
STATE = ".aiops/install-state.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InstallState(RepoCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")

    def state(self):
        return json.loads((self.root / STATE).read_text())

    def test_init_records_every_file(self):
        r = self.run_sdlc("init")
        self.assertEqual(r.returncode, 0, r.stderr)
        st = self.state()
        self.assertEqual(st["schema"], 1)
        self.assertEqual(st["plugin_version"], VERSION)
        self.assertEqual(st["ref"], f"v{VERSION}")
        self.assertEqual(st["profile"], "team")
        self.assertIsNone(st["stack"])
        scaffold = sorted(str(p.relative_to(ROOT / "templates" / "scaffold"))
                          for p in (ROOT / "templates" / "scaffold").rglob("*") if p.is_file())
        self.assertEqual(sorted(st["files"]), scaffold)
        for rel, entry in st["files"].items():
            self.assertFalse(rel.startswith("/") or ".." in rel.split("/"), rel)       # repo-relative only
            self.assertEqual(entry["sha256"], sha(self.root / rel), rel)              # the bytes on disk
            self.assertEqual(entry["version"], VERSION, rel)
        self.assertTrue(st["files"][".github/workflows/aiops-gates.yml"]["human_owned"])
        self.assertTrue(st["files"][".aiops/config.json"]["human_owned"])
        self.assertFalse(st["files"]["Makefile"]["human_owned"])
        self.assertNotIn(str(self.root), (self.root / STATE).read_text())              # no absolute paths
        self.assertNotIn(".gitignore", st["files"])                                     # appended to, not owned

    def test_kept_files_are_not_recorded_and_rerun_keeps_state(self):
        (self.root / "Makefile").write_text("mine:\n\techo keep\n")
        self.run_sdlc("init")
        self.assertNotIn("Makefile", self.state()["files"])
        before = (self.root / STATE).read_text()
        self.assertEqual(self.run_sdlc("init").returncode, 0)                           # nothing new written
        self.assertEqual((self.root / STATE).read_text(), before)

    def test_stack_wiring_is_hashed_as_written(self):
        self.run_sdlc("init", "--stack", "python")
        st = self.state()
        self.assertEqual(st["stack"], "python")
        self.assertEqual(st["files"]["Makefile"]["sha256"], sha(self.root / "Makefile"))

    def test_scaffold_codeowners_covers_install_state(self):
        self.run_sdlc("init")
        self.assertRegex((self.root / ".github" / "CODEOWNERS").read_text(), r"(?m)^/\.aiops/install-state\.json\s+@")


class SetupState(SetupCase):
    def test_setup_records_profile_and_stack(self):
        r = self.setup_run("--profile", "solo", "--stack", "go", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = json.loads((self.root / STATE).read_text())
        self.assertEqual((st["profile"], st["stack"]), ("solo", "go"))
        self.assertEqual(st["files"][".aiops/config.json"]["sha256"], sha(self.root / ".aiops" / "config.json"))
        self.assertEqual(st["files"]["Makefile"]["sha256"], sha(self.root / "Makefile"))

    def test_dry_run_writes_no_state(self):
        self.setup_run("--profile", "solo", "--dry-run")
        self.assertFalse((self.root / STATE).exists())


class ListInstalled(RepoCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.run_sdlc("init", "--stack", "python").returncode, 0)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(self.root).parts[:1]}

    def rows(self, out):
        return dict(reversed(ln.split(None, 1)) for ln in out.splitlines()
                    if ln.startswith("  ") and ln.split(None, 1)[0] in
                    ("current", "stale", "modified", "missing", "unmanaged", "dropped", "new"))

    def test_statuses_and_no_writes(self):
        (self.root / "REVIEW.md").write_text("ours\n")
        (self.root / "ops" / "bands.yaml").unlink()
        before = self.snapshot()
        r = self.run_sdlc("list-installed")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.rows(r.stdout)
        self.assertEqual(rows["REVIEW.md"], "modified")
        self.assertEqual(rows["ops/bands.yaml"], "missing")
        self.assertEqual(rows["Makefile"], "current")                  # stack-wired, still current
        self.assertEqual(rows[".github/workflows/aiops-gates.yml"], "current")
        self.assertIn(f"recorded: {VERSION}", r.stdout)
        self.assertIn("stack python", r.stdout)
        self.assertIn(f"running plugin: {VERSION}", r.stdout)
        self.assertEqual(self.snapshot(), before)                       # read-only

    def test_stale_and_dropped(self):
        st = json.loads((self.root / STATE).read_text())
        (self.root / "REVIEW.md").write_text("old template\n")         # what an older plugin wrote
        st["files"]["REVIEW.md"] = {"sha256": sha(self.root / "REVIEW.md"), "version": "0.1.0", "human_owned": False}
        (self.root / "docs" / "old.md").write_text("gone from the plugin\n")
        st["files"]["docs/old.md"] = {"sha256": sha(self.root / "docs" / "old.md"), "version": "0.1.0",
                                      "human_owned": False}
        (self.root / STATE).write_text(json.dumps(st))
        rows = self.rows(self.run_sdlc("list-installed").stdout)
        self.assertEqual(rows["REVIEW.md"], "stale")
        self.assertEqual(rows["docs/old.md"], "dropped")

    def test_without_install_state(self):
        (self.root / STATE).unlink()
        r = self.run_sdlc("list-installed")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no install state", r.stdout)
        self.assertEqual(self.rows(r.stdout)["REVIEW.md"], "unmanaged")
        self.assertFalse((self.root / STATE).exists())


if __name__ == "__main__":
    unittest.main()
