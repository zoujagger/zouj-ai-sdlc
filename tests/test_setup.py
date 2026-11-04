"""`sdlc setup`: guided, rerunnable onboarding that keeps the playbook workflow in every profile."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from helpers import SDLC, RepoCase, git

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
        rerun = self.run_sdlc("init")
        self.assertIn("Kept existing", rerun.stdout)
        self.assertNotIn("--force", rerun.stdout)                                # nothing suggests resetting files
        self.assertNotIn("re-run with --stack", rerun.stdout)                    # a rerun keeps the Makefile


def stub(bindir, name, body):
    f = bindir / name
    f.write_text("#!/bin/sh\n" + body + "\n")
    f.chmod(0o755)


class SetupCase(RepoCase):
    """A fresh, uninitialized repo, and a PATH of stub tools so setup's output doesn't depend on the machine. Tests
    run from inside the repo, as setup is (it scaffolds only the repo it runs in)."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)

    def bin_with(self, claude="2.1.40 (Claude Code)", gh_scopes="'gist', 'read:org', 'repo', 'workflow'", git=True):
        """Stub tools; gh logs every argument list it gets to gh.log."""
        bindir = self.root.parent / f"{self.root.name}.bin"
        bindir.mkdir(exist_ok=True)
        if claude:
            stub(bindir, "claude", f"echo '{claude}'")
        stub(bindir, "make", 'exec /usr/bin/make "$@"' if Path("/usr/bin/make").exists() else "exit 0")
        stub(bindir, "gh", f'echo "$@" >> "{bindir}/gh.log"\n'
                           f'[ "$1 $2" = "auth status" ] && echo "  - Token scopes: {gh_scopes}"\nexit 0')
        if git and not (bindir / "git").exists():
            (bindir / "git").symlink_to(shutil.which("git"))
        return bindir

    def setup_run(self, *args, stdin="", env=None):
        return self.run_sdlc("setup", *args, stdin=stdin, env={"PATH": str(self.bin_with()), **(env or {})})

    def snapshot(self):
        files = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*")
                       if p.is_file() and p.relative_to(self.root).parts[0] != ".git")
        return files, git(self.root, "status", "--porcelain")


class Preflight(SetupCase):
    def test_rows_and_blocking(self):
        from sdlc_engine import setup
        bindir = self.bin_with(claude="2.0.9 (Claude Code)", gh_scopes="'gist', 'read:org', 'repo'")
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


class Plan(SetupCase):
    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        r = self.setup_run("--profile", "team", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for section in ("Preflight", "Inventory", "Plan", "Gates"):
            self.assertRegex(r.stdout, rf"(?m)^{section}$", section)
        self.assertIn("+ .aiops/config.json", r.stdout)
        self.assertIn("+ .claude/settings.json", r.stdout)
        self.assertIn("not initialized", r.stdout)
        for gate in ("Intent Approved", "Spec Approved", "Plan Approved", "read-only", "make check", "merge"):
            self.assertIn(gate, r.stdout, gate)
        self.assertIn("dry run: nothing was written", r.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_no_tty_needs_yes(self):
        before = self.snapshot()
        r = self.setup_run()                                          # no profile, no --yes, stdin is not a tty
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--profile solo|team|strict", r.stdout)
        self.assertIn("--yes", r.stdout)
        r = self.setup_run("--profile", "solo")                       # a profile, but nobody confirmed
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--yes", r.stdout)
        self.assertIn("nothing was written", r.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_arguments_parsed_once_and_checked_up_front(self):
        """Round 4: one parser; --stack is a preset name only; checked before preflight, dry run included."""
        before = self.snapshot()
        evil = self.root.parent / f"{self.root.name}.evil"
        for args, says in ((("--profile", "solo", "--yes", "--stack", str(evil)), "unknown stack"),
                           (("--dry-run", "--stack", "bogus"), "unknown stack"),
                           (("--stack", "--dry-run", "--profile", "solo"), "unknown stack '--dry-run'"),
                           (("--profile",), "--profile needs a value"),
                           (("--profile=solo", "--yes"), "unknown option '--profile=solo'")):
            r = self.setup_run(*args)
            self.assertEqual(r.returncode, 1, (args, r.stdout + r.stderr))
            self.assertIn(says, r.stderr, args)
            self.assertNotIn("dry run", r.stdout, args)
            self.assertEqual(r.stdout, "", args)                          # refused before preflight
        r = self.run_sdlc("init", "--stack", str(evil))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_unknown_stored_profile(self):
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        cfg = self.root / ".aiops" / "config.json"
        for value in ('"bogus"', "null"):
            cfg.write_text('{"commit_approvals": true, "require_signed_approvals": true, "profile": ' + value + "}\n")
            r = self.setup_run("--dry-run")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn(".aiops/config.json", r.stderr)
            self.assertIn("solo, team or strict", r.stderr)
            d = self.run_sdlc("doctor")
            self.assertEqual(d.returncode, 1, d.stdout)
            self.assertRegex(d.stdout, r"✗ profile: (bogus|None)")


class Apply(SetupCase):
    def fresh_repo(self, name):
        d = self.root.parent / f"{self.root.name}.{name}"
        d.mkdir()
        git(d, "init", "-q", "-b", "main")
        for key, value in (("user.name", "Human Owner"), ("user.email", "owner@example.com"),
                           ("commit.gpgsign", "false")):
            git(d, "config", key, value)
        (d / "README.md").write_text("demo\n")
        git(d, "add", "-A")
        git(d, "commit", "-qm", "init")
        return d

    def sdlc_in(self, d, *args):
        env = {**self.env, "PATH": str(self.bin_with()), "CLAUDE_PROJECT_DIR": str(d)}
        return subprocess.run([sys.executable, SDLC, *args], cwd=d, input="", capture_output=True, text=True, env=env)

    def test_fresh_repo_each_profile(self):
        expected = {"solo": (False, "any"), "team": (True, "human"), "strict": (True, "sk")}
        for profile, (signed, policy) in expected.items():
            with self.subTest(profile=profile):
                d = self.fresh_repo(profile)
                r = self.sdlc_in(d, "setup", "--profile", profile, "--stack", "python", "--yes")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                cfg = json.loads((d / ".aiops" / "config.json").read_text())
                self.assertEqual((cfg["profile"], cfg["require_signed_approvals"], cfg["approval_key_policy"],
                                  cfg["commit_approvals"]), (profile, signed, policy, True))
                self.assertIn("pytest -q", (d / "Makefile").read_text())
                self.assertIn(".aiops/state/", (d / ".gitignore").read_text())
                steps = r.stdout.split("Human steps\n", 1)[1].split("\nDoctor\n", 1)[0]
                self.assertIn(f"/plugin marketplace add zoujagger/zouj-ai-sdlc@v{cli.plugin_version()}", steps)
                self.assertIn("/plugin install zouj-ai-sdlc@zouj", steps)
                self.assertEqual("git config --global user.signingkey" in steps, profile != "solo")
                self.assertEqual("ed25519-sk" in steps, profile == "strict")
                self.assertEqual("/.aiops/ @" in steps, profile == "strict")       # CODEOWNERS for strict
                self.assertIn("No intents yet", self.sdlc_in(d, "status").stdout)
                # code is read-only until a plan is approved: the playbook gate holds right after setup
                edit = {"tool_name": "Write", "cwd": str(d),
                        "tool_input": {"file_path": str(d / "src" / "app.py"), "content": "x = 1\n"}}
                env = {**self.env, "CLAUDE_PROJECT_DIR": str(d)}
                h = subprocess.run([sys.executable, SDLC, "hook", "pre-edit"], cwd=d, input=json.dumps(edit),
                                   capture_output=True, text=True, env=env)
                self.assertEqual(h.returncode, 2, h.stdout + h.stderr)
                self.assertIn("read-only lock", h.stderr)

    def test_rerun_plans_nothing(self):
        d = self.fresh_repo("rerun")
        self.assertEqual(self.sdlc_in(d, "setup", "--profile", "solo", "--yes").returncode, 0)
        stamp = {p: p.stat().st_mtime_ns for p in d.rglob("*") if p.is_file() and ".git" not in p.parts}
        r = self.sdlc_in(d, "setup", "--profile", "solo", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotRegex(r.stdout, r"(?m)^  [+~] ")                                 # 0 writes planned
        self.assertIn("nothing to write", r.stdout)
        self.assertEqual({p: p.stat().st_mtime_ns for p in d.rglob("*") if p.is_file() and ".git" not in p.parts},
                         stamp)


class Owned(SetupCase):
    CUSTOM = {"permissions": {"deny": ["Read(./.env)"], "allow": ["Bash(make *)"]},
              "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]},
              "model": "opus"}

    def alpha1_repo(self):
        """A repo set up by 0.2.0-alpha.1: no profile in config.json, a customised .claude/settings.json."""
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        cfg, settings = self.root / ".aiops" / "config.json", self.root / ".claude" / "settings.json"
        cfg.write_text('{"lock_when_idle": true, "commit_approvals": true, "main_branch": "main",\n'
                       ' "require_signed_approvals": true}\n')
        settings.write_text(json.dumps(self.CUSTOM) + "\n")
        return cfg, settings

    def test_agent_never_writes_existing_owned_files(self):
        cfg, settings = self.alpha1_repo()
        before = (cfg.read_bytes(), settings.read_bytes())
        r = self.setup_run("--profile", "solo", "--yes", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((cfg.read_bytes(), settings.read_bytes()), before)          # untouched under the agent
        steps = r.stdout.split("Human steps\n", 1)[1]
        self.assertIn("Change .claude/settings.json yourself", steps)
        self.assertIn('"zouj-ai-sdlc@zouj": true', steps)                           # the exact keys to add
        self.assertIn("Apply profile solo in your own terminal", steps)
        self.assertIn('"profile": "solo"', steps)
        self.assertIn('"require_signed_approvals": false', steps)

    def test_agent_creates_a_missing_config_with_init_defaults(self):
        """Round 4 MEDIUM: under the agent, a new config.json is what init writes (team); the profile is a human step."""
        scaffold = json.loads((cli.TEMPLATES / "scaffold" / ".aiops" / "config.json").read_text())
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        (self.root / ".aiops" / "config.json").unlink()                             # initialized, but no config
        for case in ("initialized repo", "fresh repo"):
            if case == "fresh repo":
                shutil.rmtree(self.root / ".aiops")
            r = self.setup_run("--profile", "solo", "--yes", env={"CLAUDECODE": "1"})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            cfg = json.loads((self.root / ".aiops" / "config.json").read_text())
            self.assertEqual(cfg, scaffold, case)                                    # no solo keys written
            steps = r.stdout.split("Human steps\n", 1)[1]
            self.assertIn("Apply profile solo in your own terminal", steps, case)
            self.assertIn('"require_signed_approvals": false', steps, case)
            (self.root / ".aiops" / "config.json").unlink()
        human = self.setup_run("--profile", "solo", "--yes")                       # a human run still applies it
        self.assertEqual(json.loads((self.root / ".aiops" / "config.json").read_text())["profile"], "solo",
                         human.stdout + human.stderr)

    def test_agent_downgrade_is_labelled_and_the_commit_names_the_real_profile(self):
        """Round 7 LOW/MINOR: a weaker profile the agent asked for is called a downgrade, and the suggested commit
        message names the profile config.json actually has."""
        r = self.setup_run("--profile", "solo", "--yes", env={"CLAUDECODE": "1"})       # fresh repo: team written
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        steps = r.stdout.split("Human steps\n", 1)[1]
        self.assertIn("Downgrade requested by the agent's run (team to solo)", steps)
        self.assertIn('"chore: adopt zouj-ai-sdlc (profile team)"', steps)
        self.assertNotIn("(profile solo)", steps)
        r = self.setup_run("--profile", "strict", "--dry-run", env={"CLAUDECODE": "1"})  # stronger: no label
        self.assertNotIn("Downgrade", r.stdout)
        shutil.rmtree(self.root / ".aiops")
        human = self.setup_run("--profile", "solo", "--yes")                             # the human's own choice
        steps = human.stdout.split("Human steps\n", 1)[1]
        self.assertNotIn("Downgrade", steps)
        self.assertIn('"chore: adopt zouj-ai-sdlc (profile solo)"', steps)

    def test_agent_hands_the_profile_to_the_human_and_reruns_cleanly(self):
        """Round 5: the agent's run names the terminal command for the profile; its rerun has nothing to write."""
        r = self.setup_run("--profile", "solo", "--yes", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        steps = r.stdout.split("Human steps\n", 1)[1]
        self.assertIn("bin/sdlc setup --profile solo", steps)
        self.assertIn("your own terminal", steps)
        before = self.snapshot()
        again = self.setup_run("--profile", "solo", env={"CLAUDECODE": "1"})     # no --yes, no tty
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("Nothing for the agent to write", again.stdout)
        self.assertNotIn("Applied", again.stdout)
        self.assertIn("bin/sdlc setup --profile solo", again.stdout.split("Human steps\n", 1)[1])
        self.assertEqual(self.snapshot(), before)

    def test_diff_shown_before_confirmation(self):
        import contextlib
        import io
        from sdlc_engine import setup
        cfg, settings = self.alpha1_repo()
        before = (cfg.read_bytes(), settings.read_bytes())
        r = self.setup_run("--profile", "solo", "--dry-run")                      # the dry run shows the diffs too
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for rel in (".aiops/config.json", ".claude/settings.json"):
            self.assertIn(f"--- a/{rel}", r.stdout)
            self.assertLess(r.stdout.index(f"--- a/{rel}"), r.stdout.index("dry run: nothing was written"))
        self.assertRegex(r.stdout, r'(?m)^\+.*"require_signed_approvals": false')
        seen = {}
        buf = io.StringIO()

        def confirm():                                                            # what the human sees when asked
            seen["text"] = buf.getvalue()
            return False
        with mock.patch.object(setup, "_is_tty", return_value=True), \
                mock.patch.object(setup, "_confirm", confirm), \
                mock.patch.object(setup, "preflight", return_value=[("✓", "git", "")]), \
                contextlib.redirect_stdout(buf):
            code = setup.main(self.root, ["--profile", "solo"])
        self.assertEqual(code, 2)                                                 # not confirmed: nothing written
        self.assertIn("--- a/.aiops/config.json", seen["text"])                    # the diff came before the question
        self.assertIn("--- a/.claude/settings.json", seen["text"])
        self.assertEqual((cfg.read_bytes(), settings.read_bytes()), before)

    def test_stale_or_foreign_marketplace_is_proposed(self):
        from sdlc_engine import setup
        cfg, settings = self.alpha1_repo()
        for source in ({"source": "github", "repo": "zoujagger/zouj-ai-sdlc", "ref": "v0.2.0-alpha.1"},   # older
                       {"source": "github", "repo": "someone/zouj-ai-sdlc-fork"}):                     # a fork
            with self.subTest(source=source):
                settings.write_text(json.dumps({**self.CUSTOM, "extraKnownMarketplaces": {"zouj": {"source": source}},
                                                "enabledPlugins": {"zouj-ai-sdlc@zouj": True}}))
                self.assertIn(".claude/settings.json", setup.owned_changes(self.root, "team"))
                self.assertTrue(any(st == "!" for st, _, _ in setup.inventory(self.root)))

    def test_invalid_json_is_refused(self):
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        for rel in (".aiops/config.json", ".claude/settings.json"):
            with self.subTest(file=rel):
                f = self.root / rel
                good = f.read_text()
                f.write_text('{"profile": "team",\n')                                 # truncated
                r = self.setup_run("--profile", "strict", "--yes")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(f"✗ {rel} isn't valid JSON", r.stdout)
                self.assertIn("nothing was written", r.stdout)
                self.assertNotIn("Already set up", r.stdout)
                self.assertEqual(f.read_text(), '{"profile": "team",\n')               # left for the human to fix
                self.assertEqual(self.setup_run("--profile", "strict", "--dry-run").returncode, 1)
                f.write_text(good)

    def test_json_that_isnt_an_object_is_refused(self):
        """Round 5: valid JSON of the wrong shape gets a ✗ row, never a traceback."""
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        for rel, bad in ((".aiops/config.json", "1\n"), (".aiops/config.json", "[]\n"),
                         (".claude/settings.json", "[]\n"),
                         (".claude/settings.json", '{"extraKnownMarketplaces": "x"}\n'),
                         (".claude/settings.json", '{"enabledPlugins": 1}\n')):
            with self.subTest(file=rel, content=bad):
                f = self.root / rel
                good = f.read_text()
                f.write_text(bad)
                for args in (("--profile", "strict", "--yes"), ("--dry-run",)):
                    r = self.setup_run(*args)
                    self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                    self.assertNotIn("Traceback", r.stderr)
                    self.assertIn(f"✗ {rel}", r.stdout)
                self.assertEqual(f.read_text(), bad)                                    # left for the human
                f.write_text(good)

    def test_human_merges_only_marketplace_keys(self):
        cfg, settings = self.alpha1_repo()
        r = self.setup_run("--profile", "solo", "--yes")                            # a human, in a terminal
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        merged = json.loads(settings.read_text())
        self.assertEqual(merged["extraKnownMarketplaces"]["zouj"]["source"],
                         {"source": "github", "repo": "zoujagger/zouj-ai-sdlc", "ref": f"v{cli.plugin_version()}"})
        self.assertIs(merged["enabledPlugins"]["zouj-ai-sdlc@zouj"], True)
        for key, value in self.CUSTOM.items():                                      # permissions, hooks, the rest
            self.assertEqual(merged[key], value, key)
        self.assertEqual(set(merged) - set(self.CUSTOM), {"extraKnownMarketplaces", "enabledPlugins"})
        conf = json.loads(cfg.read_text())
        self.assertEqual((conf["profile"], conf["require_signed_approvals"], conf["approval_key_policy"]),
                         ("solo", False, "any"))
        self.assertEqual(conf["main_branch"], "main")                               # other keys kept
        self.assertIn("--- a/.aiops/config.json", r.stdout)                         # the change is shown as a diff
        self.assertRegex(r.stdout, r'(?m)^-.*"require_signed_approvals": true')
        self.assertIn("--- a/.claude/settings.json", r.stdout)
        rerun = self.setup_run("--profile", "solo", "--yes")
        self.assertIn("nothing to write", rerun.stdout)


class Symlinks(SetupCase):
    """Round 4 HIGH: no scaffold or setup write follows a symlink or a hard link, inside or outside the repo."""

    def outside(self):
        d = self.root.parent / f"{self.root.name}.outside"
        d.mkdir()
        self.addCleanup(shutil.rmtree, d, True)
        return d

    def scaffolded(self):
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "scaffold")
        return self.snapshot(), (self.root / ".claude" / "settings.json").read_bytes()

    def test_agent_force_through_a_link_to_a_human_owned_file(self):
        before, settings = self.scaffolded()
        (self.root / "REVIEW.md").unlink()
        (self.root / "REVIEW.md").symlink_to(".claude/settings.json")
        r = self.run_sdlc("init", "--force", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("REVIEW.md", r.stderr)
        self.assertIn("symlink", r.stderr)
        self.assertEqual((self.root / ".claude" / "settings.json").read_bytes(), settings)
        self.assertTrue((self.root / "REVIEW.md").is_symlink())                   # refused before any write

    def test_link_to_a_file_outside_the_repo(self):
        self.scaffolded()
        target = self.outside() / "gitconfig"
        target.write_text("[user]\n\tname = me\n")
        (self.root / "REVIEW.md").unlink()
        (self.root / "REVIEW.md").symlink_to(target)
        r = self.run_sdlc("init", "--force")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(target.read_text(), "[user]\n\tname = me\n")

    def test_linked_directory_and_dangling_link_in_a_fresh_repo(self):
        out = self.outside()
        (self.root / "scripts").symlink_to(out)                                   # a directory on PATH, say
        (self.root / "ops").mkdir()
        (self.root / "ops" / "bands.yaml").symlink_to(out / "planted")            # dangling
        before = self.snapshot()
        for args in (("init",), ("setup", "--profile", "solo", "--yes")):
            r = self.run_sdlc(*args, env={"CLAUDECODE": "1", "PATH": str(self.bin_with())})
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("scripts", r.stdout + r.stderr)
            self.assertEqual(sorted(p.name for p in out.iterdir()), [])           # nothing created outside
            self.assertEqual(self.snapshot(), before)                             # nor inside: refused up front

    def test_writer_refuses_a_link_that_appears_after_the_preview(self):
        out = self.outside()
        actions = cli.init_actions(self.root)                                     # previewed while still safe
        (self.root / "scripts").symlink_to(out)
        with self.assertRaises(OSError):
            cli.apply_init(self.root, actions)
        self.assertEqual(sorted(p.name for p in out.iterdir()), [])

    def test_hard_link_is_replaced_not_written_through(self):
        self.scaffolded()
        target = self.outside() / "notes"
        target.write_text("mine\n")
        (self.root / "REVIEW.md").unlink()
        import os
        os.link(target, self.root / "REVIEW.md")
        r = self.run_sdlc("init", "--force")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(target.read_text(), "mine\n")
        self.assertIn("REVIEW.md", (self.root / "REVIEW.md").read_text())


class WriteErrors(SetupCase):
    """Round 5: a failed write is reported with what was already written, never as a traceback."""

    def test_init_force_over_a_directory(self):
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        (self.root / "REVIEW.md").unlink()
        (self.root / "REVIEW.md").mkdir()
        r = self.run_sdlc("init", "--force")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("REVIEW.md", r.stderr)
        self.assertIn("written before the error", r.stderr)

    def test_setup_reports_a_failed_write(self):
        import contextlib
        import io
        from sdlc_engine import setup
        real, calls = cli.write_file, []

        def flaky(root, rel, data, mode=0o644):
            calls.append(rel)
            if len(calls) == 3:
                raise OSError(f"{rel} is a symlink; refusing to write through it")
            return real(root, rel, data, mode)
        err, out = io.StringIO(), io.StringIO()
        with mock.patch.object(cli, "write_file", flaky), mock.patch.object(setup, "preflight", return_value=[]), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            code = setup.main(self.root, ["--profile", "team", "--yes"])
        self.assertEqual(code, 1, out.getvalue() + err.getvalue())
        self.assertIn(calls[2], err.getvalue())
        self.assertIn("written before the error", err.getvalue())
        for rel in calls[:2]:
            self.assertIn(rel, err.getvalue())


class PreflightTools(SetupCase):
    """Round 5: preflight never runs a tool from a PATH directory inside the repo, nor hands it the human's stdin."""

    def test_planted_tools_are_not_run(self):
        planted = self.root / ".venv" / "bin"
        planted.mkdir(parents=True)
        log = self.root.parent / f"{self.root.name}.planted.log"
        self.addCleanup(lambda: log.unlink(missing_ok=True))
        for name in ("gh", "claude", "git"):
            stub(planted, name, f'echo "{name} $@" >> "{log}"')
        outside = self.bin_with()
        (outside / "gh").write_text(f'#!/bin/sh\ncat >> "{log}.stdin"\n'
                                    '[ "$1 $2" = "auth status" ] && echo "  - Token scopes: \'repo\', \'workflow\'"\nexit 0\n')
        self.addCleanup(lambda: Path(f"{log}.stdin").unlink(missing_ok=True))
        r = self.run_sdlc("setup", "--dry-run", "--profile", "team", stdin="my secret\n",
                          env={"PATH": f"{planted}:{outside}"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(log.exists(), log.read_text() if log.exists() else "")       # nothing planted ran
        self.assertIn("✓ gh logged in", r.stdout)                                     # the real one did
        self.assertEqual(Path(f"{log}.stdin").read_text(), "")                         # without the human's stdin


class Unreviewed(SetupCase):
    """Round 7 MEDIUM: a human-owned file that exists before setup and isn't committed was never reviewed (the agent
    may have planted it while the guards were off), so setup shows it and never folds it into the commit."""
    PLANTED = 'agent@example.com namespaces="git" ssh-ed25519 AAAAplantedByTheAgent\n'

    def plant(self):
        f = self.root / ".aiops" / "config" / "allowed-signers"
        f.parent.mkdir(parents=True)
        f.write_text(self.PLANTED)
        return f

    def commit_step(self, out):
        steps = out.split("Human steps\n", 1)[1]
        return next(line for line in steps.splitlines() if "git commit" in line), steps

    def test_planted_signer_is_shown_and_left_out_of_the_commit(self):
        self.plant()
        for env in ({}, {"CLAUDECODE": "1"}):                                       # a human's run, the agent's run
            with self.subTest(agent=bool(env)):
                r = self.setup_run("--profile", "team", "--dry-run", env=env)
                self.assertIn("! .aiops/config/allowed-signers", r.stdout)
                self.assertIn("AAAAplantedByTheAgent", r.stdout)                    # its content is shown
        r = self.setup_run("--profile", "team", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.root / ".aiops" / "config" / "allowed-signers").read_text(), self.PLANTED)
        commit, steps = self.commit_step(r.stdout)
        self.assertNotIn("git add -A", steps)
        self.assertIn("git add --", commit)
        self.assertIn(".aiops/config.json", commit)                                 # what setup wrote
        self.assertNotIn("allowed-signers", commit)                                 # never the unreviewed file
        self.assertIn("Review", steps)
        self.assertIn(".aiops/config/allowed-signers", steps)

    def test_staged_trust_file_is_flagged_and_never_committed(self):
        """Round 8 MEDIUM: a key staged with git plumbing (the file on disk still equals HEAD) is flagged, and the
        printed commit step commits only setup's files, never the rest of the index."""
        self.assertEqual(self.setup_run("--profile", "team", "--yes").returncode, 0)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "scaffold")
        signers = self.root / ".aiops" / "config" / "allowed-signers"
        evil = signers.read_text() + 'agent@example.com namespaces="git" ssh-ed25519 AAAAagentStaged\n'
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.root, input=evil, text=True,
                              capture_output=True, env=self.env).stdout.strip()
        git(self.root, "update-index", "--cacheinfo", f"100644,{blob},.aiops/config/allowed-signers")
        r = self.setup_run("--profile", "solo", "--yes")                           # a human changes the profile
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("! .aiops/config/allowed-signers", r.stdout)
        commit, _steps = self.commit_step(r.stdout)
        done = subprocess.run(["bash", "-c", commit.strip()], cwd=self.root, capture_output=True, text=True,
                              env=self.env)                                         # the human runs the step
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("AAAAagentStaged", git(self.root, "show", "HEAD:.aiops/config/allowed-signers"))
        self.assertIn('"solo"', git(self.root, "show", "HEAD:.aiops/config.json"))  # setup's own change is in

    def test_committed_files_are_not_flagged(self):
        self.assertEqual(self.setup_run("--profile", "team", "--yes").returncode, 0)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "scaffold")
        r = self.setup_run("--profile", "team", "--dry-run")
        self.assertNotIn("! .aiops/config/allowed-signers", r.stdout)
        self.assertIn("= .aiops/config/allowed-signers", r.stdout)


class Roots(SetupCase):
    """Round 5 MEDIUM: init and setup scaffold only the top of a git repo, never $HOME, ~/.claude or a toolchain path."""

    def side(self, name, repo=False):
        d = self.root.parent / f"{self.root.name}.{name}"                       # a sibling of the temp repo
        d.mkdir()
        self.addCleanup(shutil.rmtree, d, True)                                  # removes only what this test made
        if repo:
            git(d, "init", "-q", "-b", "main")
        return d

    def refused(self, cwd, home=None, says="", extra=None):
        env = {**self.env, "PATH": str(self.bin_with()), **(extra or {})}
        if home:
            env["HOME"] = str(home)
        for args in (("init",), ("setup", "--profile", "team", "--yes"), ("setup", "--dry-run", "--profile", "team")):
            before = sorted(p.name for p in cwd.iterdir())
            r = subprocess.run([sys.executable, SDLC, *args], cwd=cwd, input="", capture_output=True, text=True,
                               env=env)
            self.assertEqual(r.returncode, 1, (args, r.stdout + r.stderr))
            self.assertIn(says, r.stderr, args)
            self.assertIn("nothing was written", r.stderr.lower(), args)
            self.assertEqual(sorted(p.name for p in cwd.iterdir()), before, args)

    def test_not_a_git_repo(self):
        self.refused(self.side("plain"), says="git init")

    def test_home_and_claude_dir(self):
        home = self.side("home", repo=True)                                      # a dotfiles repo at $HOME
        self.refused(home, home=home, says="home directory")
        claude = home / ".claude"
        claude.mkdir()
        git(claude, "init", "-q", "-b", "main")
        self.refused(claude, home=home, says="~/.claude")

    def test_toolchain_path(self):
        home = self.side("home2")
        localbin = home / ".local" / "bin"
        localbin.mkdir(parents=True)
        git(localbin, "init", "-q", "-b", "main")
        self.refused(localbin, home=home, says="toolchain")

    def test_git_location_variables_are_refused(self):
        """Round 6 MEDIUM: GIT_DIR / GIT_WORK_TREE would point the "top of a repo" check at another directory."""
        target = self.side("redirected")                                          # not a repo
        dotgit = str(self.root / ".git")
        self.refused(target, says="GIT_DIR", extra={"GIT_DIR": dotgit})
        self.refused(target, says="GIT_DIR", extra={"GIT_DIR": dotgit, "GIT_WORK_TREE": str(target)})
        self.refused(self.root, says="GIT_WORK_TREE", extra={"GIT_WORK_TREE": str(target)})

    def test_guard_keeps_agent_scaffolding_in_the_session_repo(self):
        """Round 6 MEDIUM: the pre-bash guard (it knows the session's project) refuses the agent's init/setup elsewhere."""
        import os
        from sdlc_engine import guards
        other = self.side("other", repo=True)                                     # another of the user's repos
        sub = self.root / "pkg"
        sub.mkdir()

        def check(cwd, cmd):
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.root)}):
                return guards.check_bash({"tool_input": {"command": cmd}, "cwd": str(cwd)})
        for cwd, cmd in ((other, "sdlc setup --profile team --yes"),
                         (self.root, f"cd {other} && sdlc init"),
                         (self.root, "pushd ../x; sdlc setup --yes"),
                         (self.root, f"GIT_DIR={other}/.git GIT_WORK_TREE=. sdlc setup --profile team --yes"),
                         (self.root, f"sdlc init -C {other}"),
                         (self.root, f"/opt/plugin/bin/sdlc init --force; cd {other}; true"),
                         # round 7: variables the CLI reads, env --chdir, an attached -C, find -execdir
                         (self.root, f"CLAUDE_PROJECT_DIR={other} sdlc init"),
                         (self.root, f"export CLAUDE_PROJECT_DIR={other}; sdlc setup --profile team --yes"),
                         (self.root, "HOME=/tmp/fake sdlc init --force"),
                         (self.root, f"env --chdir={other} /opt/plugin/bin/sdlc init"),
                         (self.root, f"env -C{other} /opt/plugin/bin/sdlc init"),
                         (self.root, f"find {other} -maxdepth 1 -name .git -execdir /opt/plugin/bin/sdlc init ;")):
            self.assertIsNotNone(check(cwd, cmd), (cwd, cmd))
        for cwd, cmd in ((self.root, "sdlc setup --profile team --yes"),
                         (sub, "/opt/plugin/bin/sdlc setup --dry-run --profile team"),
                         (self.root, "sdlc status"),
                         (other, "sdlc status"),
                         # round 7: `sdlc setup` that isn't the command being run is not a scaffold call
                         (self.root, 'grep -n "sdlc setup" README.md; cd docs'),
                         (self.root, 'git log --oneline -1; echo "run sdlc init -C later"')):
            self.assertIsNone(check(cwd, cmd), (cwd, cmd))

    def test_root_is_the_working_directorys_repo(self):
        """Round 7 MEDIUM: CLAUDE_PROJECT_DIR can't point init/setup at another repo than the one they run in."""
        other = self.side("elsewhere", repo=True)
        env = {**self.env, "PATH": str(self.bin_with()), "CLAUDE_PROJECT_DIR": str(other)}
        for args in (("init",), ("setup", "--profile", "team", "--yes")):
            r = subprocess.run([sys.executable, SDLC, *args], cwd=self.root, input="", capture_output=True,
                               text=True, env=env)
            self.assertEqual(r.returncode, 1, (args, r.stdout + r.stderr))
            self.assertIn("CLAUDE_PROJECT_DIR", r.stderr, args)
            self.assertEqual(sorted(p.name for p in other.iterdir()), [".git"], args)   # nothing written there

    def test_home_comes_from_the_account_too(self):
        """Round 7 LOW: a spoofed $HOME doesn't let init/setup scaffold the real home (or its ~/.claude)."""
        import os
        real_home = self.side("realhome", repo=True)
        account = mock.Mock(pw_dir=str(real_home))
        os.chdir(real_home)                     # init/setup run from inside it (SetupCase restores the directory)
        with mock.patch.dict(os.environ, {"HOME": str(self.side("fakehome"))}), \
                mock.patch.object(cli.pwd, "getpwuid", return_value=account):
            self.assertIn("home directory", cli.scaffold_root_problem(real_home) or "")

    def test_git_ceiling_directories_is_allowed(self):
        """Round 7 MINOR: a ceiling only limits git's upward search; it can't fake the top of a repo."""
        r = self.run_sdlc("setup", "--profile", "team", "--dry-run",
                          env={"PATH": str(self.bin_with()), "GIT_CEILING_DIRECTORIES": "/nonexistent"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_subdirectory_of_a_repo_is_fine(self):
        sub = self.root / "pkg"
        sub.mkdir()
        r = subprocess.run([sys.executable, SDLC, "setup", "--dry-run", "--profile", "team"], cwd=sub, input="",
                           capture_output=True, text=True, env={**self.env, "PATH": str(self.bin_with())})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)                 # scaffolds the repo's top level


class NoSandbox(SetupCase):
    """The sandbox was removed (review round 3): setup writes only in the repo it runs in; the README has a recipe."""

    def test_unknown_option_refused(self):
        before = self.snapshot()
        box = self.root.parent / f"{self.root.name}.sandbox"
        for args in (("--sandbox", str(box)), ("--profile", "solo", "--yes", "--bogus")):
            r = self.setup_run(*args)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn(f"unknown option {args[0] if args[0] == '--sandbox' else '--bogus'!r}", r.stderr)
            self.assertIn("--profile", r.stderr)                                  # names the valid options
            self.assertEqual(r.stdout, "")                                        # refused before preflight
        self.assertFalse(box.exists())
        self.assertEqual(self.snapshot(), before)                                 # nothing written

    def test_docs_offer_the_recipe_not_a_sandbox(self):
        root = Path(cli.__file__).resolve().parents[2]
        self.assertFalse((cli.TEMPLATES / "sandbox").exists())
        for rel in ("README.md", "COMMANDS-QUICK-REF.md", "skills/setup/SKILL.md", "lib/sdlc_engine/cli.py",
                    "lib/sdlc_engine/setup.py"):
            text = (root / rel).read_text()
            self.assertNotIn("--sandbox", text, rel)
            self.assertNotIn("sandbox <dir>", text, rel)
        readme = (root / "README.md").read_text()
        for piece in ("git init", "sdlc setup --profile solo --yes", "/zouj-ai-sdlc:intent"):
            self.assertIn(piece, readme.split("\n**Just looking?**", 1)[1].split("\n\n", 1)[0], piece)


class Feedback(RepoCase):
    def test_prints_links_offline(self):
        import contextlib
        import io
        import os
        import socket
        from unittest import mock
        buf, cwd = io.StringIO(), os.getcwd()
        os.chdir(self.root)
        try:
            with mock.patch.object(socket, "socket", side_effect=AssertionError("feedback opened a socket")), \
                    mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")), \
                    contextlib.redirect_stdout(buf):
                code = cli.main(["feedback"])
        finally:
            os.chdir(cwd)
        text = buf.getvalue()
        self.assertEqual(code, 0, text)
        base = "https://github.com/zoujagger/zouj-ai-sdlc/issues/new"
        self.assertIn(f"{base}?template=install-problem.yml", text)
        self.assertIn(f"{base}?template=quick-feedback.yml", text)
        self.assertIn("doctor:", text)                                   # the summary to paste
        self.assertIn("nothing was sent", text.lower())
        self.assertNotIn(str(self.root.parent), text)                    # no local paths beyond the repo name


if __name__ == "__main__":
    unittest.main()
