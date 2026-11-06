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
        (self.root / "REVIEW.md").write_text("ours\n")
        r = self.run_sdlc("list-installed")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no install state", r.stdout)
        self.assertIn("preview", r.stdout)                              # what adoption would record (S10)
        self.assertEqual(self.rows(r.stdout)["REVIEW.md"], "modified")
        self.assertEqual(self.rows(r.stdout)["CLAUDE.md"], "current")
        self.assertFalse((self.root / STATE).exists())


RELEASES = {"0.2.0-alpha.1": "429614a3cd49ec4e33ed16a3a40cc54a01fc2998",     # v0.2.0-alpha.1
            "0.2.0-alpha.2": "0f8d4f60aea85ad898969d2dc31dcb351c73404b"}     # v0.2.0-alpha.2 (PR #9 merge)


class Adoption(RepoCase):
    """Repos initialized before install-state are adopted from defaults/scaffold-history.json (0004 S10)."""
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")

    def scaffold_as_released(self, version):
        """Write the scaffold exactly as `sdlc init` of that release did (ref pinned to its tag)."""
        import io
        import subprocess
        import tarfile
        tar = subprocess.run(["git", "archive", RELEASES[version], "templates/scaffold"], cwd=ROOT,
                             capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(tar)) as t:
            for m in t.getmembers():
                if m.isfile():
                    rel = m.name.split("templates/scaffold/", 1)[1]
                    data = t.extractfile(m).read().replace(b"__ZOUJ_SDLC_REF__", f"v{version}".encode())
                    (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
                    (self.root / rel).write_bytes(data)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(self.root).parts[:1]}

    def test_alpha1_and_alpha2_repos_adopted(self):
        from sdlc_engine import lifecycle
        for version in RELEASES:
            with self.subTest(version=version):
                shutil.rmtree(self.root / ".aiops", ignore_errors=True)
                self.scaffold_as_released(version)
                (self.root / "REVIEW.md").write_text("our own review rules\n")
                before = self.snapshot()
                st = lifecycle.adopt(self.root)
                self.assertEqual(self.snapshot(), before)                       # adopt() writes nothing
                files = st["files"]
                self.assertIsNone(files["REVIEW.md"]["sha256"])                 # differs from every release
                for rel in (".github/workflows/aiops-gates.yml", "Makefile", ".aiops/README.md"):
                    self.assertEqual(files[rel]["sha256"], sha(self.root / rel), rel)
                    self.assertIsNotNone(files[rel]["version"], rel)
                self.assertEqual(files[".github/workflows/aiops-gates.yml"]["version"], version)  # its ref pins it
                self.assertEqual(st["ref"], f"v{version}")
                self.assertTrue(st["adopted"])
                rows = self.run_sdlc("list-installed").stdout
                self.assertIn("preview", rows)
                self.assertRegex(rows, r"(?m)^  modified\s+REVIEW\.md$")
                self.assertEqual(self.snapshot(), before)                       # the preview writes nothing

    def test_stack_wired_makefile_matches(self):
        from sdlc_engine import lifecycle
        self.run_sdlc("init", "--stack", "go")
        (self.root / STATE).unlink()
        st = lifecycle.adopt(self.root)
        self.assertEqual(st["files"]["Makefile"]["sha256"], sha(self.root / "Makefile"))
        self.assertEqual(st["stack"], "go")

    def test_links_and_non_scaffold_files_are_never_claimed(self):
        from sdlc_engine import lifecycle
        self.run_sdlc("init")
        (self.root / STATE).unlink()
        (self.root / "REVIEW.md").unlink()
        (self.root / "REVIEW.md").symlink_to(self.root / "CLAUDE.md")
        files = lifecycle.adopt(self.root)["files"]
        self.assertNotIn("REVIEW.md", files)
        self.assertNotIn("src/app.py", files)


if __name__ == "__main__":
    unittest.main()
