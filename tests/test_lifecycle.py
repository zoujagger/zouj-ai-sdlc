"""Install state and the lifecycle commands: list-installed, repair, upgrade, uninstall (0004)."""
import hashlib
import json
import shutil
import unittest

from helpers import INTENT, ROOT, RepoCase
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


class Repair(RepoCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        self.state0 = json.loads((self.root / STATE).read_text())

    def state(self):
        return json.loads((self.root / STATE).read_text())

    def test_restores_missing_keeps_modified(self):
        (self.root / "ops" / "bands.yaml").unlink()
        (self.root / "REVIEW.md").write_text("ours\n")
        r = self.run_sdlc("repair", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sha(self.root / "ops" / "bands.yaml"), self.state0["files"]["ops/bands.yaml"]["sha256"])
        self.assertEqual((self.root / "REVIEW.md").read_text(), "ours\n")
        self.assertIn("ops/bands.yaml", r.stdout)
        self.assertEqual(self.state()["files"]["ops/bands.yaml"]["sha256"], sha(self.root / "ops" / "bands.yaml"))
        r2 = self.run_sdlc("repair", "--yes")                              # nothing left to do
        self.assertEqual(r2.returncode, 0)
        self.assertIn("Nothing to repair", r2.stdout)

    def test_dry_run_and_no_tty_write_nothing(self):
        (self.root / "ops" / "bands.yaml").unlink()
        before = (self.root / STATE).read_text()
        r = self.run_sdlc("repair", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ops/bands.yaml", r.stdout)
        self.assertFalse((self.root / "ops" / "bands.yaml").exists())
        r = self.run_sdlc("repair")                                         # stdin isn't a terminal
        self.assertEqual(r.returncode, 2)
        self.assertFalse((self.root / "ops" / "bands.yaml").exists())
        self.assertEqual((self.root / STATE).read_text(), before)
        self.assertEqual(self.run_sdlc("repair", "--bogus").returncode, 1)

    def test_agent_skips_human_owned(self):
        (self.root / ".github" / "workflows" / "ci.yml").unlink()
        (self.root / "ops" / "bands.yaml").unlink()                         # code: read-only with no active intent
        (self.root / "docs" / "runbooks" / "README.md").unlink()            # docs: exempt from the lock
        r = self.run_sdlc("repair", "--yes", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.root / ".github" / "workflows" / "ci.yml").exists())
        self.assertFalse((self.root / "ops" / "bands.yaml").exists())       # the agent can't write it, so neither can repair
        self.assertTrue((self.root / "docs" / "runbooks" / "README.md").exists())
        self.assertIn(".github/workflows/ci.yml", r.stdout)
        self.assertIn("ops/bands.yaml", r.stdout)
        self.assertRegex(r.stdout, r"-I \S+/bin/sdlc repair")                # the human's terminal command

    def test_adopts_a_repo_without_state(self):
        (self.root / STATE).unlink()
        (self.root / "REVIEW.md").write_text("ours\n")
        r = self.run_sdlc("repair", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.state()
        self.assertTrue(st["adopted"])
        self.assertIsNone(st["files"]["REVIEW.md"]["sha256"])
        self.assertEqual((self.root / "REVIEW.md").read_text(), "ours\n")


class Ref(unittest.TestCase):
    """resolve_ref: installed_plugins.json's gitCommitSha, a pushed checkout's HEAD, else the tag (0004 S12)."""
    def setUp(self):
        import tempfile
        from pathlib import Path
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        (self.home / ".claude" / "plugins").mkdir(parents=True)
        self.plugin = self.tmp / "cache" / "zouj" / "zouj-ai-sdlc" / VERSION
        self.plugin.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def installed(self, sha, path=None):
        (self.home / ".claude" / "plugins" / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
            "zouj-ai-sdlc@zouj": [{"scope": "user", "installPath": str(path or self.plugin), "version": VERSION,
                                   "gitCommitSha": sha}]}}))

    def test_installed_plugins_sha(self):
        from sdlc_engine import lifecycle
        self.installed("a" * 40)
        self.assertEqual(lifecycle.resolve_ref(self.plugin, self.home), ("a" * 40, None))

    def test_malformed_or_other_install_ignored(self):
        from sdlc_engine import lifecycle
        for sha, path in (("not-a-sha", None), ("b" * 40, self.tmp / "elsewhere"), ("C" * 40, None)):
            self.installed(sha, path)
            ref, warning = lifecycle.resolve_ref(self.plugin, self.home)
            self.assertEqual(ref, f"v{VERSION}", sha)
            self.assertIn("tag", warning)

    def test_checkout_head_reachable(self):
        import subprocess
        from sdlc_engine import lifecycle
        g = lambda *a, cwd=self.plugin: subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True,  # noqa: E731
                                                       check=True).stdout.strip()
        g("init", "-q", "-b", "main")
        g("-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "--allow-empty", "-m", "x")
        head = g("rev-parse", "HEAD")
        ref, warning = lifecycle.resolve_ref(self.plugin, self.home)
        self.assertEqual(ref, f"v{VERSION}")                                # not on any remote: CI can't fetch it
        self.assertIn("not pushed", warning)
        g("update-ref", "refs/remotes/origin/main", head)
        self.assertEqual(lifecycle.resolve_ref(self.plugin, self.home), (head, None))


class Upgrade(RepoCase):
    """sdlc upgrade: stale files replaced, modified kept but for the ref, ref pinned to a sha, migrations listed."""
    SHA = "a" * 40

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        home = self.root.parent / f"{self.root.name}.home"
        (home / ".claude" / "plugins").mkdir(parents=True)
        (home / ".claude" / "plugins" / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
            "zouj-ai-sdlc@zouj": [{"installPath": str(ROOT), "gitCommitSha": self.SHA}]}}))
        self.addCleanup(shutil.rmtree, home, True)
        self.home = {"HOME": str(home)}
        st = json.loads((self.root / STATE).read_text())
        (self.root / "REVIEW.md").write_text("old template\n")                # stale: an older plugin wrote this
        st["files"]["REVIEW.md"] = {"sha256": sha(self.root / "REVIEW.md"), "version": "0.1.0", "human_owned": False}
        (self.root / STATE).write_text(json.dumps(st))
        claude = self.root / ".github" / "workflows" / "claude.yml"          # modified by the user
        claude.write_text(claude.read_text() + "# ours\n")

    def upgrade(self, *args, env=None):
        return self.run_sdlc("upgrade", *args, env={**self.home, **(env or {})})

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(self.root).parts[:1]}

    def test_replaces_stale_keeps_modified_bumps_ref(self):
        r = self.upgrade("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.root / "REVIEW.md").read_bytes(), (ROOT / "templates" / "scaffold" / "REVIEW.md").read_bytes())
        self.assertIn("-old template", r.stdout)                               # the diff was shown
        claude = (self.root / ".github" / "workflows" / "claude.yml").read_text()
        self.assertTrue(claude.endswith("# ours\n"))
        self.assertIn(f"ZOUJ_SDLC_REF: {self.SHA}", claude)
        for rel in (".github/workflows/aiops-gates.yml", ".github/workflows/claude-pr-review.yml"):
            self.assertIn(f"ZOUJ_SDLC_REF: {self.SHA}", (self.root / rel).read_text(), rel)
        self.assertIn(f'"ref": "{self.SHA}"', (self.root / ".claude" / "settings.json").read_text())
        st = json.loads((self.root / STATE).read_text())
        self.assertEqual((st["plugin_version"], st["ref"]), (VERSION, self.SHA))
        self.assertEqual(st["files"]["REVIEW.md"], {"sha256": sha(self.root / "REVIEW.md"), "version": VERSION,
                                                    "human_owned": False})
        self.assertEqual(st["files"][".github/workflows/aiops-gates.yml"]["sha256"],
                         sha(self.root / ".github" / "workflows" / "aiops-gates.yml"))

    def test_second_run_is_noop(self):
        self.assertEqual(self.upgrade("--yes").returncode, 0)
        before = self.snapshot()
        r = self.upgrade("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"Already at {VERSION}", r.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_and_no_tty_write_nothing(self):
        before = self.snapshot()
        r = self.upgrade("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("REVIEW.md", r.stdout)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.upgrade().returncode, 2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.upgrade("--force").returncode, 1)

    def test_agent_never_writes_human_owned(self):
        human_owned = [".github/workflows/aiops-gates.yml", ".github/workflows/claude.yml", ".claude/settings.json",
                       ".aiops/config.json", ".github/CODEOWNERS"]
        before = {rel: (self.root / rel).read_bytes() for rel in human_owned}
        st0 = json.loads((self.root / STATE).read_text())
        r = self.upgrade("--yes", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for rel in human_owned:
            self.assertEqual((self.root / rel).read_bytes(), before[rel], rel)
        self.assertIn(".github/workflows/aiops-gates.yml", r.stdout)
        self.assertRegex(r.stdout, r"-I \S+/bin/sdlc upgrade")
        st = json.loads((self.root / STATE).read_text())
        self.assertEqual(st["files"][".github/workflows/aiops-gates.yml"], st0["files"][".github/workflows/aiops-gates.yml"])
        self.assertEqual(st["ref"], st0["ref"])                                 # the human finishes the ref bump

    def test_legacy_approvals_listed_never_run(self):
        import os
        from unittest import mock
        from sdlc_engine import approvals, lifecycle
        os.chdir(self.root)
        self.addCleanup(os.chdir, str(ROOT))
        pending = [("b" * 40, "0001-x/intent.md")]
        with mock.patch.object(approvals, "unsigned_approvals", return_value=pending), \
                mock.patch.object(lifecycle, "resolve_ref", return_value=(self.SHA, None)), \
                mock.patch("sdlc_engine.cli.out") as said:
            self.assertEqual(lifecycle.cmd_upgrade(self.root, ["--yes"]), 0)
        text = "\n".join(str(c.args[0]) for c in said.call_args_list)
        self.assertIn("legacy-approvals", text)
        self.assertIn("legacy-approvals --write", text)
        legacy = self.root / ".aiops" / "config" / "legacy-approvals"
        self.assertNotIn("b" * 40, legacy.read_text() if legacy.exists() else "")   # never run by upgrade
        self.assertNotIn("legacy-approvals", json.loads((self.root / STATE).read_text())["migrations"])
        with mock.patch.object(approvals, "unsigned_approvals", return_value=[]), \
                mock.patch.object(lifecycle, "resolve_ref", return_value=(self.SHA, None)), mock.patch("sdlc_engine.cli.out"):
            self.assertEqual(lifecycle.cmd_upgrade(self.root, ["--yes"]), 0)
        self.assertIn("legacy-approvals", json.loads((self.root / STATE).read_text())["migrations"])


class Uninstall(RepoCase):
    """sdlc uninstall: human-only; removes only unmodified managed scaffold files, never artifacts (0004 S14)."""
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        self.d.mkdir(parents=True)
        self.write("intent", INTENT)

    def test_removes_only_unmodified_managed(self):
        (self.root / "REVIEW.md").write_text("ours\n")
        r = self.run_sdlc("uninstall", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for rel in ("CLAUDE.md", "Makefile", ".github/workflows/aiops-gates.yml", ".aiops/config.json",
                    ".aiops/README.md", STATE):
            self.assertFalse((self.root / rel).exists(), rel)
        for rel in ("REVIEW.md", ".aiops/0001-csv-export/intent.md", "src/app.py", "README.md"):
            self.assertTrue((self.root / rel).exists(), rel)
        self.assertTrue((self.root / ".aiops" / "state").is_dir())
        self.assertIn("REVIEW.md", r.stdout)                                    # kept, and why
        self.assertNotIn(".aiops/state/", (self.root / ".gitignore").read_text() if (self.root / ".gitignore").exists() else "")
        self.assertIn("/plugin uninstall", r.stdout)

    def test_tampered_state_refused(self):
        st = json.loads((self.root / STATE).read_text())
        for rel in ("src/app.py", ".aiops/0001-csv-export/intent.md", "../outside.txt"):
            st["files"][rel] = {"sha256": sha(self.root / rel) if (self.root / rel).is_file() else "0" * 64,
                                "version": VERSION, "human_owned": False}
        (self.root / STATE).write_text(json.dumps(st))
        r = self.run_sdlc("uninstall", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.root / "src" / "app.py").exists())
        self.assertTrue((self.root / ".aiops" / "0001-csv-export" / "intent.md").exists())
        self.assertRegex(r.stdout, r"refused.*src/app\.py|src/app\.py.*not a scaffold path")
        self.assertIn(".aiops/0001-csv-export/intent.md", r.stdout)

    def test_agent_refused_dry_run_allowed(self):
        before = sorted(str(p) for p in self.root.rglob("*"))
        r = self.run_sdlc("uninstall", "--yes", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("human", r.stderr)
        r = self.run_sdlc("uninstall", "--dry-run", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("CLAUDE.md", r.stdout)
        self.assertEqual(sorted(str(p) for p in self.root.rglob("*")), before)
        self.assertEqual(self.run_sdlc("uninstall").returncode, 2)               # no terminal, no --yes
        self.assertEqual(sorted(str(p) for p in self.root.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
