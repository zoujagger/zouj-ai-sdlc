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
        self.assertFalse((self.root / ".aiops" / "config.json").exists())  # previewing writes nothing
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
        for rel in created | kept:
            self.assertTrue((self.root / rel).exists(), rel)
        self.assertEqual((self.root / "Makefile").read_text(), "mine:\n\techo keep\n")
        again = cli.init_actions(self.root)
        self.assertEqual({act for act, _ in again}, {"keep"})  # a rerun plans no creation
        rerun = self.run_sdlc("init", "--with", "all")
        self.assertIn("Kept existing", rerun.stdout)
        self.assertNotIn("--force", rerun.stdout)  # nothing suggests resetting files
        self.assertNotIn("re-run with --stack", rerun.stdout)  # a rerun keeps the Makefile


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
        stub(
            bindir,
            "gh",
            f'echo "$@" >> "{bindir}/gh.log"\n'
            f'[ "$1 $2" = "auth status" ] && echo "  - Token scopes: {gh_scopes}"\nexit 0',
        )
        if git and not (bindir / "git").exists():
            (bindir / "git").symlink_to(shutil.which("git"))
        return bindir

    def setup_run(self, *args, stdin="", env=None):
        return self.run_sdlc("setup", *args, stdin=stdin, env={"PATH": str(self.bin_with()), **(env or {})})

    def snapshot(self):
        files = sorted(
            str(p.relative_to(self.root))
            for p in self.root.rglob("*")
            if p.is_file() and p.relative_to(self.root).parts[0] != ".git"
        )
        return files, git(self.root, "status", "--porcelain")


class Preflight(SetupCase):
    def test_rows_and_blocking(self):
        from sdlc_engine import setup

        bindir = self.bin_with(claude="2.0.9 (Claude Code)", gh_scopes="'gist', 'read:org', 'repo'")
        r = self.run_sdlc("setup", "--profile", "solo", "--dry-run", env={"PATH": str(bindir)})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Preflight", r.stdout)
        self.assertRegex(r.stdout, r"! claude 2\.0\.9 \(>= 2\.1")  # too old: warn, continue
        self.assertIn("gh auth refresh -h github.com -s workflow", r.stdout)  # missing scope: the fix
        self.assertIn("! git credential helper", r.stdout)
        self.assertIn("gh auth setup-git", r.stdout)
        log = (bindir / "gh.log").read_text()
        self.assertIn("auth status", log)
        self.assertNotRegex(log, r"(^|\s)(-t|--show-token)(\s|$)")  # never print the token
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
        bindir = self.bin_with()  # git is back on PATH
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
        r = self.setup_run()  # no profile, no --yes, stdin is not a tty
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--profile solo|team|strict", r.stdout)
        self.assertIn("--yes", r.stdout)
        r = self.setup_run("--profile", "solo")  # a profile, but nobody confirmed
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--yes", r.stdout)
        self.assertIn("nothing was written", r.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_arguments_parsed_once_and_checked_up_front(self):
        """Round 4: one parser; --stack is a preset name only; checked before preflight, dry run included."""
        before = self.snapshot()
        evil = self.root.parent / f"{self.root.name}.evil"
        for args, says in (
            (("--profile", "solo", "--yes", "--stack", str(evil)), "unknown stack"),
            (("--dry-run", "--stack", "bogus"), "unknown stack"),
            (("--stack", "--dry-run", "--profile", "solo"), "unknown stack '--dry-run'"),
            (("--profile",), "--profile needs a value"),
            (("--profile=solo", "--yes"), "unknown option '--profile=solo'"),
        ):
            r = self.setup_run(*args)
            self.assertEqual(r.returncode, 1, (args, r.stdout + r.stderr))
            self.assertIn(says, r.stderr, args)
            self.assertNotIn("dry run", r.stdout, args)
            self.assertEqual(r.stdout, "", args)  # refused before preflight
        r = self.run_sdlc("init", "--with", "all", "--stack", str(evil))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_unknown_stored_profile(self):
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
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
        for key, value in (
            ("user.name", "Human Owner"),
            ("user.email", "owner@example.com"),
            ("commit.gpgsign", "false"),
        ):
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
                self.assertEqual(
                    (
                        cfg["profile"],
                        cfg["require_signed_approvals"],
                        cfg["approval_key_policy"],
                        cfg["commit_approvals"],
                    ),
                    (profile, signed, policy, True),
                )
                self.assertIn("pytest -q", (d / "Makefile").read_text())
                self.assertIn(".aiops/state/", (d / ".gitignore").read_text())
                steps = r.stdout.split("Human steps\n", 1)[1].split("\nDoctor\n", 1)[0]
                self.assertIn(f"/plugin marketplace add zoujagger/zouj-ai-sdlc@v{cli.plugin_version()}", steps)
                self.assertIn("/plugin install zouj-ai-sdlc@zouj", steps)
                self.assertEqual("git config --global user.signingkey" in steps, profile != "solo")
                self.assertEqual("ed25519-sk" in steps, profile == "strict")
                self.assertEqual("/.aiops/ @" in steps, profile == "strict")  # CODEOWNERS for strict
                self.assertIn("No intents yet", self.sdlc_in(d, "status").stdout)
                # code is read-only until a plan is approved: the playbook gate holds right after setup
                edit = {
                    "tool_name": "Write",
                    "cwd": str(d),
                    "tool_input": {"file_path": str(d / "src" / "app.py"), "content": "x = 1\n"},
                }
                env = {**self.env, "CLAUDE_PROJECT_DIR": str(d)}
                h = subprocess.run(
                    [sys.executable, SDLC, "hook", "pre-edit"],
                    cwd=d,
                    input=json.dumps(edit),
                    capture_output=True,
                    text=True,
                    env=env,
                )
                self.assertEqual(h.returncode, 2, h.stdout + h.stderr)
                self.assertIn("G-LOCK-01", h.stderr)

    def test_rerun_plans_nothing(self):
        d = self.fresh_repo("rerun")
        self.assertEqual(self.sdlc_in(d, "setup", "--profile", "solo", "--yes").returncode, 0)
        stamp = {p: p.stat().st_mtime_ns for p in d.rglob("*") if p.is_file() and ".git" not in p.parts}
        r = self.sdlc_in(d, "setup", "--profile", "solo", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotRegex(r.stdout, r"(?m)^  [+~] ")  # 0 writes planned
        self.assertIn("nothing to write", r.stdout)
        self.assertEqual(
            {p: p.stat().st_mtime_ns for p in d.rglob("*") if p.is_file() and ".git" not in p.parts}, stamp
        )


class Owned(SetupCase):
    CUSTOM = {
        "permissions": {"deny": ["Read(./.env)"], "allow": ["Bash(make *)"]},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]},
        "model": "opus",
    }

    def alpha1_repo(self):
        """A repo set up by 0.2.0-alpha.1: no profile in config.json, a customised .claude/settings.json."""
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
        cfg, settings = self.root / ".aiops" / "config.json", self.root / ".claude" / "settings.json"
        cfg.write_text(
            '{"lock_when_idle": true, "commit_approvals": true, "main_branch": "main",\n'
            ' "require_signed_approvals": true}\n'
        )
        settings.write_text(json.dumps(self.CUSTOM) + "\n")
        return cfg, settings

    def test_agent_never_writes_existing_owned_files(self):
        cfg, settings = self.alpha1_repo()
        before = (cfg.read_bytes(), settings.read_bytes())
        r = self.setup_run("--profile", "solo", "--yes", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((cfg.read_bytes(), settings.read_bytes()), before)  # untouched under the agent
        steps = r.stdout.split("Human steps\n", 1)[1]
        self.assertIn("Change .claude/settings.json yourself", steps)
        self.assertIn('"zouj-ai-sdlc@zouj": true', steps)  # the exact keys to add
        self.assertIn(
            "Choose the profile: type `/zouj-ai-sdlc:setup solo` as your whole prompt", steps
        )  # 0007: no profile yet
        self.assertIn('"profile": "solo"', steps)
        self.assertIn('"require_signed_approvals": false', steps)
        cfg.write_text('{"main_branch": "trunk", "require_signed_approvals": true}\n')  # edited: not the first profile
        r = self.setup_run("--profile", "solo", "--yes", env={"CLAUDECODE": "1"})
        steps = r.stdout.split("Human steps\n", 1)[1]
        self.assertIn("Apply profile solo in your own terminal", steps)
        self.assertNotIn("/zouj-ai-sdlc:setup solo", steps)
        self.assertIn('"profile": "solo"', steps)
        self.assertEqual(cfg.read_text(), '{"main_branch": "trunk", "require_signed_approvals": true}\n')

    def test_agent_creates_a_missing_config_with_init_defaults(self):
        """Round 4 MEDIUM: under the agent, a new config.json is what init writes (team); the profile is a human step."""
        scaffold = json.loads((cli.TEMPLATES / "scaffold" / ".aiops" / "config.json").read_text())
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
        (self.root / ".aiops" / "config.json").unlink()  # initialized, but no config
        for case in ("initialized repo", "fresh repo"):
            if case == "fresh repo":
                shutil.rmtree(self.root / ".aiops")
            r = self.setup_run("--profile", "solo", "--yes", env={"CLAUDECODE": "1"})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            cfg = json.loads((self.root / ".aiops" / "config.json").read_text())
            self.assertEqual(cfg, scaffold, case)  # no solo keys written
            steps = r.stdout.split("Human steps\n", 1)[1]
            self.assertIn("type `/zouj-ai-sdlc:setup solo` as your whole prompt", steps, case)  # 0007: first profile
            self.assertIn("bin/sdlc setup --profile solo", steps, case)  # the terminal way, still named
            self.assertIn('"require_signed_approvals": false', steps, case)
            (self.root / ".aiops" / "config.json").unlink()
        human = self.setup_run("--profile", "solo", "--yes")  # a human run still applies it
        self.assertEqual(
            json.loads((self.root / ".aiops" / "config.json").read_text())["profile"],
            "solo",
            human.stdout + human.stderr,
        )

    def test_agent_downgrade_is_labelled_and_the_commit_names_the_real_profile(self):
        """Round 7 LOW/MINOR: a weaker profile the agent asked for is called a downgrade, and the suggested commit
        message names the profile config.json actually has. 0007 review r3: with no profile set yet, nothing is a
        downgrade and the message names the profile the human is about to set."""
        r = self.setup_run("--profile", "solo", "--yes", env={"CLAUDECODE": "1"})  # fresh repo: the template
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        steps = r.stdout.split("Human steps\n", 1)[1]
        self.assertNotIn("Downgrade", steps)
        self.assertIn('"chore: adopt zouj-ai-sdlc (profile solo)"', steps)
        self.assertNotIn("(profile team)", steps)
        cfg = self.root / ".aiops" / "config.json"  # a profile already set: team
        cfg.write_text(json.dumps({**json.loads(cfg.read_text()), "profile": "team", "approval_key_policy": "human"}))
        r = self.setup_run("--profile", "solo", "--yes", env={"CLAUDECODE": "1"})
        steps = r.stdout.split("Human steps\n", 1)[1]
        self.assertIn("Downgrade requested by the agent's run (team to solo)", steps)
        self.assertIn('"chore: adopt zouj-ai-sdlc (profile team)"', steps)
        self.assertNotIn("(profile solo)", steps)
        r = self.setup_run("--profile", "strict", "--dry-run", env={"CLAUDECODE": "1"})  # stronger: no label
        self.assertNotIn("Downgrade", r.stdout)
        shutil.rmtree(self.root / ".aiops")
        human = self.setup_run("--profile", "solo", "--yes")  # the human's own choice
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
        again = self.setup_run("--profile", "solo", env={"CLAUDECODE": "1"})  # no --yes, no tty
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
        r = self.setup_run("--profile", "solo", "--dry-run")  # the dry run shows the diffs too
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for rel in (".aiops/config.json", ".claude/settings.json"):
            self.assertIn(f"--- a/{rel}", r.stdout)
            self.assertLess(r.stdout.index(f"--- a/{rel}"), r.stdout.index("dry run: nothing was written"))
        self.assertRegex(r.stdout, r'(?m)^\+.*"require_signed_approvals": false')
        seen = {}
        buf = io.StringIO()

        def confirm():  # what the human sees when asked
            seen["text"] = buf.getvalue()
            return False

        with (
            mock.patch.object(setup, "_is_tty", return_value=True),
            mock.patch.object(setup, "_confirm", confirm),
            mock.patch.object(setup, "preflight", return_value=[("✓", "git", "")]),
            contextlib.redirect_stdout(buf),
        ):
            code = setup.main(self.root, ["--profile", "solo"])
        self.assertEqual(code, 2)  # not confirmed: nothing written
        self.assertIn("--- a/.aiops/config.json", seen["text"])  # the diff came before the question
        self.assertIn("--- a/.claude/settings.json", seen["text"])
        self.assertEqual((cfg.read_bytes(), settings.read_bytes()), before)

    def test_stale_or_foreign_marketplace_is_proposed(self):
        from sdlc_engine import setup

        cfg, settings = self.alpha1_repo()
        for source in (
            {"source": "github", "repo": "zoujagger/zouj-ai-sdlc", "ref": "v0.2.0-alpha.1"},  # older
            {"source": "github", "repo": "someone/zouj-ai-sdlc-fork"},
        ):  # a fork
            with self.subTest(source=source):
                settings.write_text(
                    json.dumps(
                        {
                            **self.CUSTOM,
                            "extraKnownMarketplaces": {"zouj": {"source": source}},
                            "enabledPlugins": {"zouj-ai-sdlc@zouj": True},
                        }
                    )
                )
                self.assertIn(".claude/settings.json", setup.owned_changes(self.root, "team"))
                self.assertTrue(any(st == "!" for st, _, _ in setup.inventory(self.root)))

    def test_invalid_json_is_refused(self):
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
        for rel in (".aiops/config.json", ".claude/settings.json"):
            with self.subTest(file=rel):
                f = self.root / rel
                good = f.read_text()
                f.write_text('{"profile": "team",\n')  # truncated
                r = self.setup_run("--profile", "strict", "--yes")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(f"✗ {rel} isn't valid JSON", r.stdout)
                self.assertIn("nothing was written", r.stdout)
                self.assertNotIn("Already set up", r.stdout)
                self.assertEqual(f.read_text(), '{"profile": "team",\n')  # left for the human to fix
                self.assertEqual(self.setup_run("--profile", "strict", "--dry-run").returncode, 1)
                f.write_text(good)

    def test_json_that_isnt_an_object_is_refused(self):
        """Round 5: valid JSON of the wrong shape gets a ✗ row, never a traceback."""
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
        for rel, bad in (
            (".aiops/config.json", "1\n"),
            (".aiops/config.json", "[]\n"),
            (".claude/settings.json", "[]\n"),
            (".claude/settings.json", '{"extraKnownMarketplaces": "x"}\n'),
            (".claude/settings.json", '{"enabledPlugins": 1}\n'),
        ):
            with self.subTest(file=rel, content=bad):
                f = self.root / rel
                good = f.read_text()
                f.write_text(bad)
                for args in (("--profile", "strict", "--yes"), ("--dry-run",)):
                    r = self.setup_run(*args)
                    self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                    self.assertNotIn("Traceback", r.stderr)
                    self.assertIn(f"✗ {rel}", r.stdout)
                self.assertEqual(f.read_text(), bad)  # left for the human
                f.write_text(good)

    def test_human_merges_only_marketplace_keys(self):
        cfg, settings = self.alpha1_repo()
        r = self.setup_run("--profile", "solo", "--yes")  # a human, in a terminal
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        merged = json.loads(settings.read_text())
        self.assertEqual(
            merged["extraKnownMarketplaces"]["zouj"]["source"],
            {"source": "github", "repo": "zoujagger/zouj-ai-sdlc", "ref": f"v{cli.plugin_version()}"},
        )
        self.assertIs(merged["enabledPlugins"]["zouj-ai-sdlc@zouj"], True)
        for key, value in self.CUSTOM.items():  # permissions, hooks, the rest
            self.assertEqual(merged[key], value, key)
        self.assertEqual(set(merged) - set(self.CUSTOM), {"extraKnownMarketplaces", "enabledPlugins"})
        conf = json.loads(cfg.read_text())
        self.assertEqual(
            (conf["profile"], conf["require_signed_approvals"], conf["approval_key_policy"]), ("solo", False, "any")
        )
        self.assertEqual(conf["main_branch"], "main")  # other keys kept
        self.assertIn("--- a/.aiops/config.json", r.stdout)  # the change is shown as a diff
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
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "scaffold")
        return self.snapshot(), (self.root / ".claude" / "settings.json").read_bytes()

    def test_agent_force_through_a_link_to_a_human_owned_file(self):
        before, settings = self.scaffolded()
        (self.root / "REVIEW.md").unlink()
        (self.root / "REVIEW.md").symlink_to(".claude/settings.json")
        r = self.run_sdlc("init", "--with", "all", "--force", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("REVIEW.md", r.stderr)
        self.assertIn("symlink", r.stderr)
        self.assertEqual((self.root / ".claude" / "settings.json").read_bytes(), settings)
        self.assertTrue((self.root / "REVIEW.md").is_symlink())  # refused before any write

    def test_link_to_a_file_outside_the_repo(self):
        self.scaffolded()
        target = self.outside() / "gitconfig"
        target.write_text("[user]\n\tname = me\n")
        (self.root / "REVIEW.md").unlink()
        (self.root / "REVIEW.md").symlink_to(target)
        r = self.run_sdlc("init", "--with", "all", "--force")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(target.read_text(), "[user]\n\tname = me\n")

    def test_linked_directory_and_dangling_link_in_a_fresh_repo(self):
        out = self.outside()
        (self.root / "scripts").symlink_to(out)  # a directory on PATH, say
        (self.root / "ops").mkdir()
        (self.root / "ops" / "bands.yaml").symlink_to(out / "planted")  # dangling
        before = self.snapshot()
        for args in (("init", "--with", "all"), ("setup", "--profile", "solo", "--with", "maintain", "--yes")):
            r = self.run_sdlc(*args, env={"CLAUDECODE": "1", "PATH": str(self.bin_with())})
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("scripts", r.stdout + r.stderr)
            self.assertEqual(sorted(p.name for p in out.iterdir()), [])  # nothing created outside
            self.assertEqual(self.snapshot(), before)  # nor inside: refused up front

    def test_writer_refuses_a_link_that_appears_after_the_preview(self):
        out = self.outside()
        actions = cli.init_actions(self.root)  # previewed while still safe
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
        r = self.run_sdlc("init", "--with", "all", "--force")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(target.read_text(), "mine\n")
        self.assertIn("REVIEW.md", (self.root / "REVIEW.md").read_text())


class WriteErrors(SetupCase):
    """Round 5: a failed write is reported with what was already written, never as a traceback."""

    def test_init_force_over_a_directory(self):
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
        (self.root / "REVIEW.md").unlink()
        (self.root / "REVIEW.md").mkdir()
        r = self.run_sdlc("init", "--with", "all", "--force")
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
        with (
            mock.patch.object(cli, "write_file", flaky),
            mock.patch.object(setup, "preflight", return_value=[]),
            contextlib.redirect_stderr(err),
            contextlib.redirect_stdout(out),
        ):
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
        (outside / "gh").write_text(
            f'#!/bin/sh\ncat >> "{log}.stdin"\n'
            '[ "$1 $2" = "auth status" ] && echo "  - Token scopes: \'repo\', \'workflow\'"\nexit 0\n'
        )
        self.addCleanup(lambda: Path(f"{log}.stdin").unlink(missing_ok=True))
        r = self.run_sdlc(
            "setup", "--dry-run", "--profile", "team", stdin="my secret\n", env={"PATH": f"{planted}:{outside}"}
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(log.exists(), log.read_text() if log.exists() else "")  # nothing planted ran
        self.assertIn("✓ gh logged in", r.stdout)  # the real one did
        self.assertEqual(Path(f"{log}.stdin").read_text(), "")  # without the human's stdin


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
        for env in ({}, {"CLAUDECODE": "1"}):  # a human's run, the agent's run
            with self.subTest(agent=bool(env)):
                r = self.setup_run("--profile", "team", "--dry-run", env=env)
                self.assertIn("! .aiops/config/allowed-signers", r.stdout)
                self.assertIn("AAAAplantedByTheAgent", r.stdout)  # its content is shown
        r = self.setup_run("--profile", "team", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.root / ".aiops" / "config" / "allowed-signers").read_text(), self.PLANTED)
        commit, steps = self.commit_step(r.stdout)
        self.assertNotIn("git add -A", steps)
        self.assertIn("git add --", commit)
        self.assertIn(".aiops/config.json", commit)  # what setup wrote
        self.assertNotIn("allowed-signers", commit)  # never the unreviewed file
        self.assertIn("Review", steps)
        self.assertIn(".aiops/config/allowed-signers", steps)

    def test_setup_s_own_files_are_not_flagged_on_a_rerun(self):
        """Round 8 F2: before the commit, a second run (or the human's run after the agent's) recognises setup's own
        files and still prints the commit step."""
        flows = (
            (({"CLAUDECODE": "1"}, "solo"), ({}, "solo")),  # the documented agent -> human flow
            (({}, "team"), ({}, "team")),
        )  # a human rerun before committing
        for first, second in flows:
            with self.subTest(first=first, second=second):
                shutil.rmtree(self.root / ".aiops", ignore_errors=True)
                self.assertEqual(self.setup_run("--profile", first[1], "--yes", env=first[0]).returncode, 0)
                r = self.setup_run("--profile", second[1], "--yes", env=second[0])
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertNotRegex(r.stdout, r"(?m)^  ! \.(aiops|claude|github)/")  # none of setup's files flagged
                self.assertNotIn("Review before committing", r.stdout)
                commit, _ = self.commit_step(r.stdout)
                for rel in (".aiops/config.json", ".claude/settings.json", "CLAUDE.md", ".gitignore"):
                    self.assertIn(rel, commit, rel)

    def test_staged_trust_file_is_flagged_and_never_committed(self):
        """Round 8 MEDIUM: a key staged with git plumbing (the file on disk still equals HEAD) is flagged, and the
        printed commit step commits only setup's files, never the rest of the index."""
        self.assertEqual(self.setup_run("--profile", "team", "--yes").returncode, 0)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "scaffold")
        signers = self.root / ".aiops" / "config" / "allowed-signers"
        evil = signers.read_text() + 'agent@example.com namespaces="git" ssh-ed25519 AAAAagentStaged\n'
        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=self.root,
            input=evil,
            text=True,
            capture_output=True,
            env=self.env,
        ).stdout.strip()
        git(self.root, "update-index", "--cacheinfo", f"100644,{blob},.aiops/config/allowed-signers")
        r = self.setup_run("--profile", "solo", "--yes")  # a human changes the profile
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("! .aiops/config/allowed-signers", r.stdout)
        commit, _steps = self.commit_step(r.stdout)
        done = subprocess.run(
            ["bash", "-c", commit.strip()], cwd=self.root, capture_output=True, text=True, env=self.env
        )  # the human runs the step
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("AAAAagentStaged", git(self.root, "show", "HEAD:.aiops/config/allowed-signers"))
        self.assertIn('"solo"', git(self.root, "show", "HEAD:.aiops/config.json"))  # setup's own change is in

    def test_hostile_content_is_shown_safely(self):
        """Round 8: a planted file that isn't UTF-8, or carries terminal escapes, is shown escaped, never as a
        traceback or as live control sequences that could hide a line."""
        f = self.root / ".aiops" / "config" / "allowed-signers"
        f.parent.mkdir(parents=True)
        f.write_bytes(b'agent@example.com namespaces="git" ssh-ed25519 AAAAhidden\r\x1b[2K\x1b[1A\n\xff\xfe\n')
        r = self.setup_run("--profile", "team", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertNotIn("\x1b", r.stdout)
        self.assertIn("AAAAhidden", r.stdout)
        self.assertIn("\\x1b", r.stdout)  # visibly escaped

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
        d = self.root.parent / f"{self.root.name}.{name}"  # a sibling of the temp repo
        d.mkdir()
        self.addCleanup(shutil.rmtree, d, True)  # removes only what this test made
        if repo:
            git(d, "init", "-q", "-b", "main")
        return d

    def refused(self, cwd, home=None, says="", extra=None):
        env = {**self.env, "PATH": str(self.bin_with()), **(extra or {})}
        if home:
            env["HOME"] = str(home)
        for args in (("init",), ("setup", "--profile", "team", "--yes"), ("setup", "--dry-run", "--profile", "team")):
            before = sorted(p.name for p in cwd.iterdir())
            r = subprocess.run(
                [sys.executable, SDLC, *args], cwd=cwd, input="", capture_output=True, text=True, env=env
            )
            self.assertEqual(r.returncode, 1, (args, r.stdout + r.stderr))
            self.assertIn(says, r.stderr, args)
            self.assertIn("nothing was written", r.stderr.lower(), args)
            self.assertEqual(sorted(p.name for p in cwd.iterdir()), before, args)

    def test_not_a_git_repo(self):
        self.refused(self.side("plain"), says="git init")

    def test_home_and_claude_dir(self):
        home = self.side("home", repo=True)  # a dotfiles repo at $HOME
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
        target = self.side("redirected")  # not a repo
        dotgit = str(self.root / ".git")
        self.refused(target, says="GIT_DIR", extra={"GIT_DIR": dotgit})
        self.refused(target, says="GIT_DIR", extra={"GIT_DIR": dotgit, "GIT_WORK_TREE": str(target)})
        self.refused(self.root, says="GIT_WORK_TREE", extra={"GIT_WORK_TREE": str(target)})

    def test_guard_keeps_agent_scaffolding_in_the_session_repo(self):
        """Round 6 MEDIUM: the pre-bash guard (it knows the session's project) refuses the agent's init/setup elsewhere."""
        import os
        from sdlc_engine import guards

        other = self.side("other", repo=True)  # another of the user's repos
        sub = self.root / "pkg"
        sub.mkdir()

        def check(cwd, cmd):
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.root)}):
                return guards.check_bash({"tool_input": {"command": cmd}, "cwd": str(cwd)})

        for cwd, cmd in (
            (other, "sdlc setup --profile team --yes"),
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
            (self.root, f"find {other} -maxdepth 1 -name .git -execdir /opt/plugin/bin/sdlc init ;"),
            # round 8: `sdlc init` fed to a shell or behind an unlisted runner, anywhere on the line
            (self.root, f"cd {other} && echo 'sdlc init' | sh"),
            (self.root, f"cd {other} && bash <<< 'sdlc setup --yes'"),
            (self.root, f"cd {other} && setarch x86_64 /opt/plugin/bin/sdlc init"),
            (self.root, f"cd {other} && uv run sdlc init"),
            (other, "echo 'sdlc init' | sh"),
            # the price: a line that only mentions it, next to a relocation, is refused too (split it)
            (self.root, 'grep -n "sdlc setup" README.md; cd docs'),
            (self.root, 'git log --oneline -1; echo "run sdlc init -C later"'),
        ):
            self.assertIsNotNone(check(cwd, cmd), (cwd, cmd))
        for cwd, cmd in (
            (self.root, "sdlc setup --profile team --yes"),
            (sub, "/opt/plugin/bin/sdlc setup --dry-run --profile team"),
            (self.root, "sdlc status"),
            (other, "sdlc status"),
            (self.root, 'grep -n "sdlc setup" README.md'),
            (self.root, "echo 'sdlc init' | sh"),
        ):  # the session repo, no relocation
            self.assertIsNone(check(cwd, cmd), (cwd, cmd))

    def test_root_is_the_working_directorys_repo(self):
        """Round 7 MEDIUM: CLAUDE_PROJECT_DIR can't point init/setup at another repo than the one they run in."""
        other = self.side("elsewhere", repo=True)
        env = {**self.env, "PATH": str(self.bin_with()), "CLAUDE_PROJECT_DIR": str(other)}
        for args in (("init",), ("setup", "--profile", "team", "--yes")):
            r = subprocess.run(
                [sys.executable, SDLC, *args], cwd=self.root, input="", capture_output=True, text=True, env=env
            )
            self.assertEqual(r.returncode, 1, (args, r.stdout + r.stderr))
            self.assertIn("CLAUDE_PROJECT_DIR", r.stderr, args)
            self.assertEqual(sorted(p.name for p in other.iterdir()), [".git"], args)  # nothing written there

    def test_home_comes_from_the_account_too(self):
        """Round 7 LOW: a spoofed $HOME doesn't let init/setup scaffold the real home (or its ~/.claude)."""
        import os

        real_home = self.side("realhome", repo=True)
        account = mock.Mock(pw_dir=str(real_home))
        os.chdir(real_home)  # init/setup run from inside it (SetupCase restores the directory)
        with (
            mock.patch.dict(os.environ, {"HOME": str(self.side("fakehome"))}),
            mock.patch.object(cli.pwd, "getpwuid", return_value=account),
        ):
            self.assertIn("home directory", cli.scaffold_root_problem(real_home) or "")

    def test_no_passwd_entry(self):
        """Round 8 LOW: a uid with no passwd entry (a container run with --user N) falls back to $HOME, no traceback."""
        repo = self.side("nopasswd", repo=True)
        os.chdir(repo)
        with mock.patch.object(cli.pwd, "getpwuid", side_effect=KeyError("getpwuid(): uid not found")):
            with mock.patch.dict(os.environ, {"HOME": str(self.side("somehome"))}):
                self.assertIsNone(cli.scaffold_root_problem(repo))
            with mock.patch.dict(os.environ, {"HOME": str(repo)}):
                self.assertIn("home directory", cli.scaffold_root_problem(repo) or "")

    def test_git_ceiling_directories_is_allowed(self):
        """Round 7 MINOR: a ceiling only limits git's upward search; it can't fake the top of a repo."""
        r = self.run_sdlc(
            "setup",
            "--profile",
            "team",
            "--dry-run",
            env={"PATH": str(self.bin_with()), "GIT_CEILING_DIRECTORIES": "/nonexistent"},
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_subdirectory_of_a_repo_is_fine(self):
        sub = self.root / "pkg"
        sub.mkdir()
        r = subprocess.run(
            [sys.executable, SDLC, "setup", "--dry-run", "--profile", "team"],
            cwd=sub,
            input="",
            capture_output=True,
            text=True,
            env={**self.env, "PATH": str(self.bin_with())},
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)  # scaffolds the repo's top level


class NoSandbox(SetupCase):
    """The sandbox was removed (review round 3): setup writes only in the repo it runs in; the README has a recipe."""

    def test_unknown_option_refused(self):
        before = self.snapshot()
        box = self.root.parent / f"{self.root.name}.sandbox"
        for args in (("--sandbox", str(box)), ("--profile", "solo", "--yes", "--bogus")):
            r = self.setup_run(*args)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn(f"unknown option {args[0] if args[0] == '--sandbox' else '--bogus'!r}", r.stderr)
            self.assertIn("--profile", r.stderr)  # names the valid options
            self.assertEqual(r.stdout, "")  # refused before preflight
        self.assertFalse(box.exists())
        self.assertEqual(self.snapshot(), before)  # nothing written

    def test_docs_offer_the_recipe_not_a_sandbox(self):
        root = Path(cli.__file__).resolve().parents[2]
        self.assertFalse((cli.TEMPLATES / "sandbox").exists())
        for rel in (
            "README.md",
            "COMMANDS-QUICK-REF.md",
            "skills/setup/SKILL.md",
            "lib/sdlc_engine/cli.py",
            "lib/sdlc_engine/setup.py",
        ):
            text = (root / rel).read_text()
            self.assertNotIn("--sandbox", text, rel)
            self.assertNotIn("sandbox <dir>", text, rel)
        readme = (root / "README.md").read_text()
        recipe = readme.split("\n**Just looking?**", 1)[1].split("\n\n", 1)[0]
        for piece in ("git init", "/zouj-ai-sdlc:setup solo", "/zouj-ai-sdlc:intent"):
            self.assertIn(piece, recipe, piece)
        self.assertNotIn("Setup Profile", recipe)
        self.assertNotIn("<plugin>", recipe)  # 0007 AC-18: solo is reached by the phrase, no terminal path
        self.assertNotIn("setup --profile", recipe)


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
            with (
                mock.patch.object(socket, "socket", side_effect=AssertionError("feedback opened a socket")),
                mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")),
                contextlib.redirect_stdout(buf),
            ):
                code = cli.main(["feedback"])
        finally:
            os.chdir(cwd)
        text = buf.getvalue()
        self.assertEqual(code, 0, text)
        base = "https://github.com/zoujagger/zouj-ai-sdlc/issues/new"
        self.assertIn(f"{base}?template=install-problem.yml", text)
        self.assertIn(f"{base}?template=quick-feedback.yml", text)
        self.assertIn("doctor:", text)  # the summary to paste
        self.assertIn("nothing was sent", text.lower())
        self.assertNotIn(str(self.root.parent), text)  # no local paths beyond the repo name


STATE = ".aiops/install-state.json"


class Parts(SetupCase):
    """`sdlc setup` writes the core scaffold by default; `--with` adds opt-in parts (0007 S3: AC-11, 12, 20)."""

    def setUp(self):
        super().setUp()
        from sdlc_engine import lifecycle

        self.lc = lifecycle
        self.base = set(self.snapshot()[0])

    def files(self):
        return set(self.snapshot()[0])

    def part(self, name):
        return {rel for rel in self.lc.scaffold_paths() if self.lc.part_of(rel) == name}

    def parts(self):
        return json.loads((self.root / STATE).read_text()).get("parts")

    def ok(self, *args, env=None):
        r = self.setup_run(*args, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def test_default_is_core_with_no_schedule_or_secret(self):
        for env in (None, {"CLAUDECODE": "1"}):  # a human's run, and the agent's
            with self.subTest(env=env):
                self.ok("--profile", "team", "--yes", env=env)
                created = self.files() - self.base
                self.assertEqual(created, self.part("core") | {STATE, ".gitignore"})
                self.assertEqual(self.parts(), [])
                workflows = [rel for rel in created if rel.startswith(".github/workflows/")]
                self.assertEqual(sorted(workflows), [".github/workflows/aiops-gates.yml", ".github/workflows/ci.yml"])
                for rel in workflows:
                    text = (self.root / rel).read_text()
                    self.assertNotIn("schedule:", text, rel)
                    self.assertNotIn("secrets.", text, rel)
                for rel in created:
                    (self.root / rel).unlink()
                shutil.rmtree(self.root / ".aiops")

    def test_dry_run_names_parts_left_out(self):
        r = self.ok("--dry-run", "--profile", "team")
        self.assertIn("+ CLAUDE.md", r.stdout)
        self.assertNotIn("ops/bands.yaml", r.stdout)
        self.assertNotIn("claude-maintain.yml", r.stdout)
        line = next(ln for ln in r.stdout.splitlines() if "Not installed" in ln)
        for name in self.lc.PARTS:
            self.assertIn(name, line)
        self.assertIn("sdlc setup --with", line)
        self.assertEqual(self.files(), self.base)  # a dry run writes nothing
        r = self.ok("--dry-run", "--profile", "team", "--with", "maintain,deploy")
        self.assertIn("+ ops/bands.yaml", r.stdout)
        self.assertIn("+ .github/workflows/deploy.yml", r.stdout)
        line = next(ln for ln in r.stdout.splitlines() if "Not installed" in ln)
        self.assertNotIn("maintain", line)
        self.assertIn("review", line)
        self.assertNotIn("Not installed", self.ok("--dry-run", "--profile", "team", "--with", "all").stdout)

    def test_with_maintain_adds_only_maintain(self):
        self.ok("--profile", "solo", "--yes")
        before = self.files()
        self.ok("--profile", "solo", "--with", "maintain", "--yes")
        self.assertEqual(self.files() - before, self.part("maintain"))
        self.assertEqual(self.parts(), ["maintain"])
        before = self.files()
        r = self.ok("--profile", "solo", "--yes")  # no --with: nothing added or removed
        self.assertEqual(self.files(), before)
        self.assertEqual(self.parts(), ["maintain"])
        self.assertNotRegex(r.stdout, r"(?m)^  \+ ")  # no file to create in the plan
        self.ok("--profile", "solo", "--with", "all", "--yes")
        self.assertTrue(set(self.lc.scaffold_paths()) <= self.files())
        self.assertEqual(self.parts(), sorted(self.lc.PARTS))

    def test_bogus_part_refused(self):
        for args in (("--with", "bogus"), ("--with", "maintain,bogus"), ("--with",)):
            r = self.setup_run("--profile", "solo", "--yes", *args)
            self.assertEqual(r.returncode, 1, args)
            self.assertEqual(r.stdout, "", args)  # refused before preflight
            for name in self.lc.PARTS:
                self.assertIn(name, r.stderr)
            self.assertEqual(self.files(), self.base, args)

    def test_rerun_after_partial_setup_installs_what_the_first_run_chose(self):
        self.ok("--profile", "solo", "--with", "maintain", "--yes")  # a human's run: config has the profile
        (self.root / STATE).unlink()  # it stopped before recording
        for rel in ("CLAUDE.md", "ops/bands.yaml"):
            (self.root / rel).unlink()
        before = self.files()
        self.ok("--profile", "solo", "--yes")
        self.assertEqual(self.files() - before, {"CLAUDE.md", "ops/bands.yaml", STATE})
        self.assertEqual(self.parts(), ["maintain"])


CONFIG = ".aiops/config.json"


class FirstRun(SetupCase):
    """In a repo without .aiops/, the human's typed `/zouj-ai-sdlc:setup <p>` writes the core scaffold, then sets the
    first profile (0007 S16: spec R-2a, AC-8, AC-22, AC-23). Driven through the prompt hook, as Claude Code runs it."""

    def repo(self, name):
        d = self.root.parent / f"{self.root.name}.{name}"
        d.mkdir()
        git(d, "init", "-q", "-b", "main")
        for key, value in (("user.name", "Human Owner"), ("user.email", "owner@example.com")):
            git(d, "config", key, value)
        (d / "README.md").write_text("# app\n")
        git(d, "add", "README.md")
        git(d, "commit", "-qm", "init")
        return d

    def typed(self, text, d=None, env=None, cwd=None, full=False):
        d = d or self.root
        payload = {"prompt": text, "cwd": str(cwd or d), "hook_event_name": "UserPromptSubmit"}
        env = {"CLAUDECODE": "1", "CLAUDE_PROJECT_DIR": str(d), "PATH": str(self.bin_with()), **(env or {})}
        r = subprocess.run(
            [sys.executable, SDLC, "hook", "prompt"],
            cwd=d,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env={**self.env, **env},
        )
        self.assertEqual(r.returncode, 0, r.stderr)  # a prompt hook never blocks
        out = json.loads(r.stdout)
        return out if full else out["hookSpecificOutput"]["additionalContext"]

    def test_fresh_repo_gets_core_and_the_profile(self):
        from sdlc_engine import lifecycle, setup

        d = self.repo("fresh")
        head = git(d, "rev-parse", "HEAD")
        ctx = self.typed("/zouj-ai-sdlc:setup solo", d)
        self.assertIn("profile SET: solo", ctx)
        core = lifecycle.scaffold_paths([])
        self.assertEqual(len(core), 16)
        for rel in core:
            self.assertTrue((d / rel).is_file(), rel)
            self.assertIn(rel, ctx)  # every created file is listed
        for rel in set(lifecycle.scaffold_paths()) - set(core):
            self.assertFalse((d / rel).exists(), rel)  # no opt-in part
        self.assertIn(".aiops/state/", (d / ".gitignore").read_text())
        state = json.loads((d / ".aiops" / "install-state.json").read_text())
        self.assertEqual((state["parts"], state["profile"]), ([], "solo"))
        template = json.loads((cli.TEMPLATES / "scaffold" / CONFIG).read_text())
        self.assertEqual(json.loads((d / CONFIG).read_text()), {**template, **setup.PROFILE_CONFIG["solo"]})
        self.assertEqual(git(d, "rev-parse", "HEAD~1"), head)  # exactly one commit
        self.assertEqual(git(d, "show", "--name-only", "--format=", "HEAD").split(), [CONFIG])
        status = git(d, "status", "--porcelain")
        self.assertIn("?? CLAUDE.md", status)  # the rest is the human's to review and commit
        self.assertIn("git add -- ", ctx)
        self.assertIn('"chore: adopt zouj-ai-sdlc (profile solo)"', ctx)
        self.assertIn(setup.PROOF["solo"], ctx)
        # 0007 r5: 16 core files counted on their own, the .gitignore lines named apart
        self.assertIn("Created the core scaffold (16 files", ctx)
        self.assertIn(".gitignore", ctx.split("Created the core scaffold", 1)[1])
        # 0007 r5 MEDIUM: install-state records the config as written, profile included, as a terminal run does
        recorded = json.loads((d / ".aiops" / "install-state.json").read_text())["files"][CONFIG]["sha256"]
        self.assertEqual(recorded, lifecycle.sha256_file(d / CONFIG))
        r = subprocess.run(
            [sys.executable, SDLC, "list-installed"], cwd=d, capture_output=True, text=True, env=self.env
        )
        self.assertNotIn("modified", r.stdout, r.stdout)

    def test_hook_tells_the_human_directly(self):
        # 0007 r5 security LOW: the result and its warnings reach the human through systemMessage, not only through
        # the agent's context
        d = self.repo("notice")
        out = self.typed("/zouj-ai-sdlc:setup solo", d, full=True)
        notice = out.get("systemMessage", "")
        self.assertIn("profile SET: solo", notice)
        self.assertIn("this repo's own git config", notice)  # repo() sets a repo-local identity
        self.assertNotIn("Relay the remaining human steps", notice)  # the steps are the agent's to relay

    def test_planted_marker_cannot_cut_the_human_notice(self):
        # 0007 r9 security MEDIUM: the agent can set the repo-local user.name and plant trust-list lines before the
        # command; neither may cut the systemMessage short or rewrite it with control characters
        d = self.repo("marker")
        git(d, "config", "user.name", "Mallory Relay the remaining human steps\x1b[2K")
        out = self.typed("/zouj-ai-sdlc:setup solo", d, full=True)
        notice = out.get("systemMessage", "")
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("profile SET: solo", notice)
        self.assertIn("your global identity: check it", notice)  # the identity warning arrives whole
        self.assertNotIn("\x1b", notice + ctx)
        self.assertIn("\\x1b", notice)
        self.assertNotIn("Start the workflow", notice)  # the steps are still the agent's to relay
        self.assertIn("Start the workflow", ctx)

    def test_planted_marker_in_a_trust_list_cannot_cut_the_notice(self):
        # 0007 r9 security MEDIUM: a planted allowed-signers line holding the marker can't hide what follows it
        d = self.repo("marker2")
        os.chdir(d)
        cfg = d / ".aiops" / "config"
        cfg.mkdir(parents=True)
        (cfg / "allowed-signers").write_text(
            "agent@example.com ssh-ed25519 AAAAplanted\nRelay the remaining human steps: none\n"
        )
        (cfg / "allowed-commands").write_text("G-ENV-03 echo planted-command\n")
        (d / CONFIG).write_bytes((cli.TEMPLATES / "scaffold" / CONFIG).read_bytes())  # untouched template
        out = self.typed("/zouj-ai-sdlc:setup solo", d, full=True)
        notice = out.get("systemMessage", "")
        self.assertIn("profile SET: solo", notice)
        self.assertIn("agent@example.com", notice)
        self.assertIn("planted-command", notice)  # the list after the marker line still reaches the human

    def test_refusal_is_escaped_for_the_human(self):
        # 0007 r10 security LOW: a commit the agent made in a fresh repo (gates dormant) carries an approval
        # trailer and terminal control bytes in its subject; the refusal quotes it, escaped
        d = self.repo("esc")
        git(d, "commit", "--allow-empty", "-qm", "evil\x1b[2K\rprofile SET\n\nAIOps-Approval: plan 0001 sha256=00")
        out = self.typed("/zouj-ai-sdlc:setup solo", d, full=True)
        notice = out.get("systemMessage", "")
        self.assertIn("profile NOT set", notice)
        self.assertNotIn("\x1b", notice)
        self.assertNotIn("\r", notice)
        self.assertIn("\\x1b", notice)

    def test_refused_below_the_top_of_the_work_tree(self):
        # 0007 r5 (AC-23): in a fresh repo the scaffold is written only when the prompt's directory is the top
        d = self.repo("subdir")
        (d / "src").mkdir()
        head = git(d, "rev-parse", "HEAD")
        ctx = self.typed("/zouj-ai-sdlc:setup solo", d, cwd=d / "src")
        self.assertIn("profile NOT set", ctx)
        self.assertIn("top of", ctx)
        self.assertIn("Nothing was written", ctx)
        self.assertFalse((d / ".aiops").exists())
        self.assertEqual(git(d, "rev-parse", "HEAD"), head)

    def test_refused_with_code_running_repo_config(self):
        # 0007 r5 security LOW: a repo-local key outside the allow-list (core.fsmonitor here, set while the gates
        # were off) is refused before any git command that would run it
        d = self.repo("fsmonitor")
        marker = self.root.parent / f"{self.root.name}.fsmonitor-ran"
        script = self.root.parent / f"{self.root.name}.fsmonitor.sh"
        script.write_text(f"#!/bin/sh\ntouch {marker}\n")
        script.chmod(0o755)
        git(d, "config", "core.fsmonitor", str(script))
        marker.unlink(missing_ok=True)
        ctx = self.typed("/zouj-ai-sdlc:setup solo", d)
        self.assertIn("profile NOT set", ctx)
        self.assertIn("core.fsmonitor", ctx)
        self.assertFalse(marker.exists())
        self.assertFalse((d / ".aiops").exists())

    def test_existing_files_are_never_changed(self):
        d = self.repo("owned")
        (d / "CLAUDE.md").write_text("my own instructions\n")
        (d / ".claude").mkdir()
        (d / ".claude" / "settings.json").write_text('{"permissions": {"allow": ["Bash(ls)"]}}\n')
        before = {rel: (d / rel).read_bytes() for rel in ("CLAUDE.md", ".claude/settings.json", "README.md")}
        ctx = self.typed("/zouj-ai-sdlc:setup team", d)
        self.assertIn("profile SET: team", ctx)
        self.assertEqual({rel: (d / rel).read_bytes() for rel in before}, before)
        self.assertIn("Change .claude/settings.json yourself", ctx)  # the merge is the human's step
        self.assertTrue((d / "REVIEW.md").is_file())  # missing core files are still created

    def test_refused_where_setup_would_stop(self):
        plain = self.root.parent / f"{self.root.name}.plain"  # not a git repo
        plain.mkdir()
        nomake = self.root.parent / f"{self.root.name}.nomake"  # a PATH with git but no make: a Preflight ✗
        nomake.mkdir()
        (nomake / "git").symlink_to(shutil.which("git"))
        cases = {
            "not a git repo": (plain, {}, "not the top of a git repository"),
            "home": (self.repo("home"), {"HOME": str(self.root.parent / f"{self.root.name}.home")}, "home"),
            "GIT_DIR": (self.repo("gitdir"), {"GIT_DIR": str(self.root / ".git")}, "GIT_DIR"),
            "no make": (self.repo("nomakerepo"), {"PATH": str(nomake)}, "make"),
        }
        for case, (d, env, needle) in cases.items():
            head = git(d, "rev-parse", "HEAD") if (d / ".git").exists() else None
            ctx = self.typed("/zouj-ai-sdlc:setup solo", d, env)
            self.assertIn("profile NOT set", ctx, case)
            self.assertIn(needle, ctx, case)
            self.assertIn("Nothing was written", ctx, case)
            self.assertFalse((d / ".aiops").exists(), case)
            self.assertFalse((d / "CLAUDE.md").exists(), case)
            if head:
                self.assertEqual(git(d, "rev-parse", "HEAD"), head, case)

    def test_refused_when_an_approval_is_in_the_history(self):
        # 0007 r4 MEDIUM: a fresh repo with an approval commit on any ref refuses before anything is written
        from sdlc_engine import approvals

        d = self.repo("hist")
        git(d, "switch", "-qc", "elsewhere")
        git(
            d,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "chore(aiops): Intent Approved 0001",
            "-m",
            f"{approvals.TRAILER}: intent 0001 sha256=" + "0" * 64,
        )
        git(d, "switch", "-q", "main")
        head = git(d, "rev-parse", "HEAD")
        ctx = self.typed("/zouj-ai-sdlc:setup solo", d)
        self.assertIn("profile NOT set", ctx)
        self.assertIn("approval commit", ctx)
        self.assertIn("Nothing was written", ctx)
        self.assertFalse((d / ".aiops").exists())
        self.assertFalse((d / "CLAUDE.md").exists())
        self.assertEqual(git(d, "rev-parse", "HEAD"), head)

    def test_hook_skips_the_slow_preflight_checks(self):
        # 0007 r4 LOW: on the prompt path, Preflight runs only the rows that can stop setup (git, make, python):
        # not `gh auth status` (a network call) or `claude --version`
        d = self.repo("quick")
        log = self.bin_with() / "gh.log"
        log.unlink(missing_ok=True)
        self.assertIn("profile SET: solo", self.typed("/zouj-ai-sdlc:setup solo", d))
        self.assertFalse(log.exists(), log.read_text() if log.exists() else "")

    def test_a_write_that_failed_part_way_is_reported(self):
        # 0007 r4 LOW: "Nothing was written" only when nothing was
        d = self.repo("partial")
        os.chdir(d)

        def fail_after_one(root, actions, written=None):
            (root / "CLAUDE.md").write_text("x\n")
            written.append("CLAUDE.md")
            raise OSError("disk full")

        from sdlc_engine import setup

        with mock.patch.object(cli, "apply_init", fail_after_one):
            with mock.patch.dict(os.environ, {"PATH": f"{self.bin_with()}:/usr/bin:/bin"}):
                ok, msg = setup.set_first_profile(d, "solo")
        self.assertFalse(ok, msg)
        self.assertIn("CLAUDE.md", msg)
        self.assertNotIn("Nothing was written", msg)

    def test_config_write_failure_after_the_scaffold_is_reported(self):
        # 0007 r6 LOW: if the profile write fails after the scaffold was written, the reply says what was written
        from sdlc_engine import setup

        d = self.repo("cfgfail")
        os.chdir(d)
        real, seen = cli.write_file, []

        def second_config_write_fails(root, rel, *args, **kwargs):
            if rel == CONFIG:
                seen.append(rel)
                if len(seen) == 2:  # the first is the scaffold's template, the second the profile
                    raise OSError("disk full")
            return real(root, rel, *args, **kwargs)

        with mock.patch.object(cli, "write_file", second_config_write_fails):
            with mock.patch.dict(os.environ, {"PATH": f"{self.bin_with()}:/usr/bin:/bin"}):
                ok, msg = setup.set_first_profile(d, "solo")
        self.assertFalse(ok, msg)
        self.assertNotIn("Nothing changed", msg)
        self.assertIn("CLAUDE.md", msg)

    def test_failure_mid_scaffold_says_how_to_finish(self):
        # 0007 r12 MINOR: typed again, the command takes the initialized path, which doesn't finish the scaffold
        from sdlc_engine import setup

        d = self.repo("midfail")
        os.chdir(d)
        real, n = cli.write_file, []

        def fifth_write_fails(root, rel, *args, **kwargs):
            n.append(rel)
            if len(n) == 5:
                raise OSError("disk full")
            return real(root, rel, *args, **kwargs)

        with mock.patch.object(cli, "write_file", fifth_write_fails):
            with mock.patch.dict(os.environ, {"PATH": f"{self.bin_with()}:/usr/bin:/bin"}):
                ok, msg = setup.set_first_profile(d, "solo")
        self.assertFalse(ok, msg)
        self.assertIn("sdlc setup --yes", msg)
        self.assertIn("only the missing files", msg)

    def test_kept_scaffold_files_are_named(self):
        # 0007 r12 security MEDIUM: a neutered CI audit or CODEOWNERS committed while the gates were dormant is
        # kept, and the human is told so directly
        d = self.repo("kept")
        wf = d / ".github" / "workflows" / "aiops-gates.yml"
        wf.parent.mkdir(parents=True)
        wf.write_text(
            "on: pull_request\njobs:\n  audit:\n    runs-on: ubuntu-latest\n    steps:\n      - run: 'true'\n"
        )
        (d / ".github" / "CODEOWNERS").write_text("* @nobody\n")
        git(d, "add", "-A")
        git(d, "commit", "-qm", "ci")
        out = self.typed("/zouj-ai-sdlc:setup team", d, full=True)
        notice = out.get("systemMessage", "")
        self.assertIn("profile SET: team", notice)
        kept = notice.split("Kept existing", 1)[1]
        self.assertIn(".github/workflows/aiops-gates.yml", kept)
        self.assertIn(".github/CODEOWNERS", kept)
        self.assertNotIn("no existing file changed", notice)

    def test_kept_files_equal_to_the_template_are_not_flagged(self):
        # 0007 r13 MINOR: only a kept file that differs from the plugin's version is labelled as not the plugin's
        d = self.repo("kepteq")
        (d / "REVIEW.md").write_bytes((cli.TEMPLATES / "scaffold" / "REVIEW.md").read_bytes())
        (d / ".github").mkdir()
        (d / ".github" / "CODEOWNERS").write_text("* @nobody\n")
        out = self.typed("/zouj-ai-sdlc:setup solo", d, full=True)
        kept = out.get("systemMessage", "").split("Kept existing", 1)[1]
        self.assertIn(".github/CODEOWNERS", kept)
        self.assertNotIn("REVIEW.md", kept)

    def test_kept_file_equal_to_what_init_writes_is_not_flagged(self):
        # 0007 r14 MINOR: compare with the rendered template (__ZOUJ_SDLC_REF__ -> v<version>), as init writes it
        d = self.repo("keptref")
        rel = ".github/workflows/aiops-gates.yml"
        raw = (cli.TEMPLATES / "scaffold" / rel).read_bytes()
        self.assertIn(cli.REF_PLACEHOLDER.encode(), raw)  # the case only means something with a placeholder
        (d / rel).parent.mkdir(parents=True)
        (d / rel).write_bytes(raw.replace(cli.REF_PLACEHOLDER.encode(), f"v{cli.plugin_version()}".encode()))
        (d / "REVIEW.md").write_text("ours\n")
        notice = self.typed("/zouj-ai-sdlc:setup solo", d, full=True).get("systemMessage", "")
        kept = notice.split("Kept existing", 1)[1]
        self.assertNotIn("aiops-gates.yml", kept)
        self.assertIn("REVIEW.md", kept)

    def test_scaffold_refusal_paths_are_escaped(self):
        # 0007 r13 MINOR: a refusal's reason (scaffold_root_problem, write_failure) quotes paths too
        from sdlc_engine import setup

        d = self.repo("why")
        with mock.patch.object(cli, "scaffold_root_problem", lambda root: f"{root}\nprofile SET: strict. forged"):
            ok, msg = setup.set_first_profile(d, "solo")
        self.assertFalse(ok, msg)
        self.assertFalse(any(ln.startswith("profile SET") for ln in msg.splitlines()), msg)

    def test_newline_in_the_prompt_directory_forges_no_line(self):
        # 0007 r12 security LOW: the refusal quotes the prompt's directory; a newline in it can't start a line
        d = self.repo("nl")
        sub = d / "x\nprofile SET: strict. Nothing else to do."
        sub.mkdir()
        out = self.typed("/zouj-ai-sdlc:setup solo", d, cwd=sub, full=True)
        notice = out.get("systemMessage", "")
        self.assertIn("profile NOT set", notice)
        self.assertFalse(any(ln.startswith("profile SET") for ln in notice.splitlines()), notice)

    def test_commit_holds_the_bytes_the_hook_wrote(self):
        # 0007 r7 security LOW: a process that rewrites the config right after the hook's write can't get its
        # version committed under the profile's title; the reply says the file on disk changed
        from sdlc_engine import setup

        d = self.repo("race")
        os.chdir(d)
        real = cli.write_file
        weaker = b'{"require_signed_approvals": false, "approval_key_policy": "any", "profile": "strict"}\n'

        def racer(root, rel, data, *args, **kwargs):
            result = real(root, rel, data, *args, **kwargs)
            if rel == CONFIG and b'"profile"' in data:  # right after the profile write
                (root / rel).write_bytes(weaker)
            return result

        with mock.patch.object(cli, "write_file", racer):
            with mock.patch.dict(os.environ, {"PATH": f"{self.bin_with()}:/usr/bin:/bin"}):
                ok, msg = setup.set_first_profile(d, "strict")
        self.assertTrue(ok, msg)
        template = json.loads((cli.TEMPLATES / "scaffold" / CONFIG).read_text())
        committed = git(d, "show", f"HEAD:{CONFIG}")
        self.assertEqual(json.loads(committed), {**template, **setup.PROFILE_CONFIG["strict"]})
        self.assertIn("changed on disk", msg)
        # 0007 r8 MINOR: install-state records the hook's bytes too, so the racer's file reads as modified
        import hashlib

        st = json.loads((d / ".aiops" / "install-state.json").read_text())
        wrote = (json.dumps({**template, **setup.PROFILE_CONFIG["strict"]}, indent=2) + "\n").encode()
        self.assertEqual(st["files"][CONFIG]["sha256"], hashlib.sha256(wrote).hexdigest())

    def test_set_by_from_the_repos_own_git_config_is_flagged(self):
        # 0007 r4 security LOW: before .aiops/ exists the agent can set the repo-local identity that Set-By names
        d = self.repo("ident")
        ctx = self.typed("/zouj-ai-sdlc:setup solo", d)  # repo() sets user.name/email in the repo's own config
        self.assertIn("Set-By", ctx)
        self.assertIn("this repo's own git config", ctx)
        d2 = self.repo("ident-global")
        git(d2, "config", "--unset", "user.name")
        git(d2, "config", "--unset", "user.email")
        for key, value in (("user.name", "Human Owner"), ("user.email", "owner@example.com")):
            subprocess.run(["git", "config", "--file", self.env["GIT_CONFIG_GLOBAL"], key, value], check=True)
        ctx = self.typed("/zouj-ai-sdlc:setup solo", d2)
        self.assertIn("profile SET: solo", ctx)
        self.assertNotIn("this repo's own git config", ctx)

    def test_team_and_strict_steps(self):
        from sdlc_engine import setup

        for name, needles in (("team", ("ssh-keygen -t ed25519 ", "allowed-signers")), ("strict", ("CODEOWNERS",))):
            d = self.repo(f"steps-{name}")
            ctx = self.typed(f"/zouj-ai-sdlc:setup {name}", d)
            self.assertIn(f"profile SET: {name}", ctx)
            self.assertIn(setup.PROOF[name], ctx)
            for needle in needles:
                self.assertIn(needle, ctx, name)
            self.assertEqual(json.loads((d / CONFIG).read_text())["profile"], name)


class FirstProfile(SetupCase):
    """setup.set_first_profile: what the typed `/zouj-ai-sdlc:setup <name>` does in an initialized repo (0007 S5,
    S15: AC-1, AC-3, AC-8)."""

    def setUp(self):
        super().setUp()
        from sdlc_engine import setup

        self.S = setup
        r = self.setup_run(
            "--profile", "solo", "--yes", env={"CLAUDECODE": "1"}
        )  # the agent scaffolds: init's defaults
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.template = json.loads((cli.TEMPLATES / "scaffold" / CONFIG).read_text())
        self.assertEqual(self.cfg(), self.template)  # no profile chosen yet

    def cfg(self):
        return json.loads((self.root / CONFIG).read_text())

    def head(self):
        return git(self.root, "rev-parse", "HEAD")

    def refused(self, name, *needles):
        before = (self.head(), (self.root / CONFIG).read_bytes(), git(self.root, "status", "--porcelain"))
        ok, msg = self.S.set_first_profile(self.root, name)
        self.assertFalse(ok, msg)
        self.assertIn("profile NOT set", msg)
        self.assertIn(f"bin/sdlc setup --profile {name}", msg)  # the terminal command
        self.assertIn(" -I ", msg)
        for needle in needles:
            self.assertIn(needle, msg)
        self.assertEqual(
            (self.head(), (self.root / CONFIG).read_bytes(), git(self.root, "status", "--porcelain")), before
        )  # no file, no commit
        return msg

    def test_sets_and_commits_config_alone(self):
        before, state = self.head(), (self.root / STATE).read_bytes()
        ok, msg = self.S.set_first_profile(self.root, "solo")
        self.assertTrue(ok, msg)
        self.assertEqual(self.cfg(), {**self.template, **self.S.PROFILE_CONFIG["solo"]})
        self.assertEqual((self.root / CONFIG).read_text(), json.dumps(self.cfg(), indent=2) + "\n")
        self.assertEqual(git(self.root, "rev-parse", "HEAD~1"), before)  # exactly one new commit
        shown = git(self.root, "show", "--name-only", "--format=%s%n%b", "HEAD")
        self.assertEqual(shown.splitlines()[0], "chore(aiops): Setup Profile solo")
        self.assertIn("AIOps-Profile: solo", shown)
        self.assertIn("Set-By: Human Owner <owner@example.com>", shown)
        self.assertNotIn("Co-Authored-By", shown)
        self.assertEqual(git(self.root, "show", "--name-only", "--format=", "HEAD").split(), [CONFIG])
        self.assertEqual(git(self.root, "log", "-1", "--format=%G?"), "N")  # unsigned, in every profile
        self.assertEqual((self.root / STATE).read_bytes(), state)  # install-state untouched
        self.assertIn("?? CLAUDE.md", git(self.root, "status", "--porcelain"))  # the scaffold is still the human's
        for needle in (
            "profile SET: solo",
            self.S.PROOF["solo"],
            "chore(aiops): Setup Profile solo",
            "git add",
            "/zouj-ai-sdlc:intent",
        ):
            self.assertIn(needle, msg)
        self.assertNotIn("/plugin marketplace add", msg)  # the plugin is running: no install step
        self.assertNotIn(CONFIG, msg.split("git add", 1)[1].split("&&", 1)[0])  # already committed

    def test_staged_scaffold_stays_staged(self):
        git(self.root, "add", "--", "CLAUDE.md", "Makefile")
        ok, msg = self.S.set_first_profile(self.root, "solo")
        self.assertTrue(ok, msg)
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only").split(), ["CLAUDE.md", "Makefile"])
        self.assertEqual(git(self.root, "show", "--name-only", "--format=", "HEAD").split(), [CONFIG])
        self.assertEqual(git(self.root, "status", "--porcelain", "--", CONFIG), "")  # clean: the index followed

    def test_repo_with_no_commit_yet(self):
        d = self.root.parent / f"{self.root.name}.empty"
        d.mkdir()
        git(d, "init", "-q", "-b", "main")
        for key, value in (("user.name", "Human Owner"), ("user.email", "owner@example.com")):
            git(d, "config", key, value)
        cli.apply_init(d, cli.init_actions(d, parts=[]))
        ok, msg = self.S.set_first_profile(d, "solo")
        self.assertTrue(ok, msg)
        self.assertEqual(git(d, "rev-list", "--count", "HEAD"), "1")  # the root commit
        self.assertEqual(git(d, "show", "--name-only", "--format=", "HEAD").split(), [CONFIG])

    def test_refused_when_profile_set(self):
        self.assertTrue(self.S.set_first_profile(self.root, "solo")[0])
        self.refused("team", "already", "solo")
        self.refused("solo", "already")  # the same one too: nothing to do

    def test_refused_when_config_edited(self):
        (self.root / CONFIG).write_text(json.dumps({**self.template, "main_branch": "trunk"}))
        self.refused("solo", "edited")
        (self.root / CONFIG).write_text("{ not json")
        self.refused("solo", "edited")
        (self.root / CONFIG).unlink()
        ok, msg = self.S.set_first_profile(self.root, "solo")
        self.assertFalse(ok, msg)
        self.assertIn(CONFIG, msg)
        self.assertFalse((self.root / CONFIG).exists())  # not created either

    def test_refused_when_an_artifact_is_approved_or_closed(self):
        from helpers import INTENT

        d = self.root / ".aiops" / "0001-csv-export"
        d.mkdir()
        for status in ("Approved", "Closed"):
            (d / "intent.md").write_text(INTENT.format(id="0001").replace("status: Draft", f"status: {status}"))
            self.refused("solo", "0001-csv-export", status)
        (d / "intent.md").write_text(INTENT.format(id="0001"))  # a Draft opens nothing
        self.assertTrue(self.S.set_first_profile(self.root, "solo")[0])

    def test_refused_after_an_approval_set_back_to_draft(self):
        # 0007 review MEDIUM: the agent may set any artifact back to Draft (G-GATE-05), so the status on disk can't
        # prove "nothing approved". An approval commit in the history of any ref still refuses the phrase.
        from helpers import INTENT
        from sdlc_engine import approvals

        rel = ".aiops/0001-csv-export/intent.md"
        (self.root / rel).parent.mkdir()
        (self.root / rel).write_text(INTENT.format(id="0001").replace("status: Draft", "status: Approved"))
        git(self.root, "add", "--", rel)
        git(
            self.root,
            "commit",
            "-q",
            "-m",
            "chore(aiops): Intent Approved 0001",
            "-m",
            f"{approvals.TRAILER}: intent 0001 sha256=" + "0" * 64,
        )
        (self.root / rel).write_text(INTENT.format(id="0001"))  # set back to Draft on disk, uncommitted
        self.refused("solo", "approval commit", "history")
        git(self.root, "commit", "-q", "-m", "back to draft", "--", rel)
        self.refused("solo", "approval commit", "history")  # set back at HEAD too
        git(self.root, "checkout", "-q", "-b", "elsewhere", "HEAD~2")  # a branch without it: other refs still count
        self.assertFalse((self.root / rel).exists())
        self.refused("solo", "approval commit", "history")

    def test_without_aiops_scaffolds_unless_tracked(self):
        # 0007 S16 (R-2a): with no .aiops/ the command writes the core scaffold first. A .aiops/ that git tracks
        # but that was deleted still counts as initialized: the command refuses rather than recreating it.
        git(self.root, "add", "--", ".aiops")
        git(self.root, "commit", "-qm", "scaffold")
        shutil.rmtree(self.root / ".aiops")
        ok, msg = self.S.set_first_profile(self.root, "solo")
        self.assertFalse(ok, msg)
        self.assertIn(CONFIG, msg)
        self.assertFalse((self.root / ".aiops").exists())
        git(self.root, "rm", "-rq", "--cached", "--", ".aiops")
        git(self.root, "commit", "-qm", "unscaffold")
        ok, msg = self.S.set_first_profile(self.root, "solo")
        self.assertTrue(ok, msg)
        self.assertIn("Created the core scaffold", msg)
        self.assertEqual(self.cfg()["profile"], "solo")

    def test_planted_owned_file_is_named_before_the_steps(self):
        # 0007 r6 security MEDIUM: in a repo the agent scaffolded, a human-owned file changed before the command is
        # named in the part the human sees directly, and kept out of the suggested commit
        wf = self.root / ".github" / "workflows" / "aiops-gates.yml"
        wf.write_text(
            "on: pull_request\njobs:\n  audit:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"
        )
        ok, msg = self.S.set_first_profile(self.root, "team")
        self.assertTrue(ok, msg)
        notice, steps = msg.split("Relay the remaining human steps", 1)
        self.assertIn(".github/workflows/aiops-gates.yml", notice)
        commit = next(line for line in steps.splitlines() if "git add --" in line)
        self.assertNotIn("aiops-gates.yml", commit)

    def test_trust_list_lines_are_escaped(self):
        # 0007 r6 hardening: a planted line can't hide itself with terminal control characters
        signers = self.root / ".aiops" / "config" / "allowed-signers"
        signers.write_text(signers.read_text() + "x@example.com ssh-ed25519 AAAA\x1b[2K\x1b[1A\n")
        ok, msg = self.S.set_first_profile(self.root, "team")
        self.assertTrue(ok, msg)
        self.assertNotIn("\x1b", msg)
        self.assertIn("\\x1b", msg)

    def test_trust_lists_are_capped(self):
        # 0007 r8 security LOW: a huge planted list can't bury the warnings; the rest is counted and the file named
        allowed = self.root / ".aiops" / "config" / "allowed-commands"
        allowed.write_text("".join(f"G-ENV-03 echo planted-{i}\n" for i in range(500)))
        ok, msg = self.S.set_first_profile(self.root, "team")
        self.assertTrue(ok, msg)
        self.assertIn("planted-0", msg)
        self.assertNotIn("planted-499", msg)
        self.assertIn("(+480 more, see .aiops/config/allowed-commands)", msg)
        self.assertLess(msg.count("planted-"), 25)

    def test_reply_lists_the_trust_lists(self):
        # 0007 r4 security LOW: with no preview on this path, the reply shows what the human-owned trust lists hold
        # (an allowed-signers line committed before the command would otherwise never be seen)
        signers = self.root / ".aiops" / "config" / "allowed-signers"
        signers.write_text(signers.read_text() + 'agent@example.com namespaces="git" ssh-ed25519 AAAAplanted\n')
        git(self.root, "add", "--", ".aiops")
        git(self.root, "commit", "-qm", "scaffold")
        ok, msg = self.S.set_first_profile(self.root, "team")
        self.assertTrue(ok, msg)
        self.assertIn("allowed-signers", msg)
        self.assertIn("agent@example.com", msg)
        listed = msg.split(".aiops/config/allowed-signers", 1)[1].split("Relay the remaining human steps", 1)[0]
        self.assertNotIn("#", listed)  # comments left out
        self.assertNotIn("legacy-approvals", msg)  # an empty (comments only) list isn't shown

    def test_symlinked_config_refused(self):
        target = self.root.parent / f"{self.root.name}.target.json"
        target.write_text(json.dumps(self.template))
        self.addCleanup(target.unlink)
        (self.root / CONFIG).unlink()
        (self.root / CONFIG).symlink_to(target)
        self.refused("solo", "symlink")
        self.assertEqual(json.loads(target.read_text()), self.template)

    def test_commit_failure_leaves_the_change(self):
        from sdlc_engine import approvals

        before = self.head()
        with mock.patch.object(approvals, "_commit_alone", return_value=None):
            ok, msg = self.S.set_first_profile(self.root, "solo")
        self.assertTrue(ok, msg)
        self.assertEqual(self.cfg()["profile"], "solo")
        self.assertEqual(self.head(), before)
        self.assertIn("commit it yourself", msg.lower())
        self.assertIn(CONFIG, msg)

    def test_team_reply_has_signing_steps(self):
        ok, msg = self.S.set_first_profile(self.root, "team")  # the test key has no passphrase
        self.assertTrue(ok, msg)
        self.assertEqual(self.cfg()["approval_key_policy"], "human")
        for needle in ("profile SET: team", self.S.PROOF["team"], "ssh-keygen -t ed25519 ", "allowed-signers"):
            self.assertIn(needle, msg)

    def test_terminal_team_on_a_new_config_sets_the_profile(self):
        # 0007 review r2 L1: team's keys equal the engine defaults, so the human's terminal run used to write nothing,
        # and the repo kept counting as "no profile chosen". It must write what the phrase writes (spec R-3).
        from sdlc_engine import lifecycle

        for name in self.S.PROFILES:
            (self.root / CONFIG).write_text(json.dumps(self.template, indent=2) + "\n")
            r = self.setup_run("--profile", name, "--yes")  # the human's terminal: no session markers
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(self.cfg(), {**self.template, **self.S.PROFILE_CONFIG[name]}, name)
            self.assertEqual(  # AC-8: the same bytes as the typed command writes, not just the same JSON
                (self.root / CONFIG).read_text(),
                json.dumps({**self.template, **self.S.PROFILE_CONFIG[name]}, indent=2) + "\n",
                name,
            )
            self.assertEqual(lifecycle.config_written(self.root), name)
            self.assertFalse(self.S.no_profile_yet(self.root)[0], name)
            self.assertNotIn("Setup Profile", r.stdout, name)  # no step to set what was just set

    def test_strict_reply_has_codeowners_step(self):
        ok, msg = self.S.set_first_profile(self.root, "strict")
        self.assertTrue(ok, msg)
        self.assertEqual(self.cfg()["approval_key_policy"], "sk")
        for needle in ("profile SET: strict", "ed25519-sk", "CODEOWNERS", "/.aiops/ @"):
            self.assertIn(needle, msg)

    def test_unknown_name(self):
        ok, msg = self.S.set_first_profile(self.root, "fast")
        self.assertFalse(ok)
        for name in ("solo", "team", "strict"):
            self.assertIn(name, msg)
        self.assertEqual(self.cfg(), self.template)


SPRING_POM = """<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId></parent>
  <artifactId>demo</artifactId>
</project>
"""
JAVA_RECIPES = {
    "typecheck": "./mvnw -B -q compile",
    "test": "./mvnw -B -q test",
    "build": "./mvnw -B -q package -DskipTests",
}


class Stack(SetupCase):
    """0009 S5: setup and init detect the stack and wire the Makefile they create (AC-12 to AC-14, AC-17)."""

    def spring(self):
        (self.root / "pom.xml").write_text(SPRING_POM)
        (self.root / "mvnw").write_text("#!/bin/sh\n")
        (self.root / "mvnw").chmod(0o755)

    def state(self):
        return json.loads((self.root / ".aiops" / "install-state.json").read_text())

    def test_auto_wires_created_makefile(self):
        self.spring()
        r = self.setup_run("--profile", "solo", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        mk = (self.root / "Makefile").read_text()
        for cmd in JAVA_RECIPES.values():
            self.assertIn(f"\t{cmd}\n", mk)
        self.assertIn('[lint] not configured', mk)  # no Checkstyle: the stub stays
        st = self.state()
        self.assertEqual(st["stack"], "java")
        self.assertEqual(st["recipes"], JAVA_RECIPES)
        self.assertIn("detected Java · Spring Boot · Maven", r.stdout)

    def test_dry_run_shows_block(self):
        self.spring()
        before = self.snapshot()
        r = self.setup_run("--profile", "solo", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        block = r.stdout.split("\nStack\n", 1)[1]
        self.assertIn("detected Java · Spring Boot · Maven (from pom.xml, mvnw)", block)
        self.assertRegex(block, r"lint\s+not configured")
        self.assertRegex(block, r"test\s+\./mvnw -B -q test")
        self.assertEqual(self.snapshot(), before)

    def test_existing_makefile_untouched(self):
        mine = 'test:\n\t@echo "[test] not configured - edit Makefile"\n'
        (self.root / "Makefile").write_text(mine)
        (self.root / "package.json").write_text(json.dumps({"scripts": {"test": "ng test"}}))
        (self.root / "angular.json").write_text("{}")
        r = self.setup_run("--profile", "solo", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.root / "Makefile").read_text(), mine)
        self.assertIn("your Makefile is kept; copy what you want into it", r.stdout)
        self.assertIn("npm run test -- --watch=false", r.stdout)
        self.assertNotIn("recipes", self.state())
        self.assertIsNone(self.state()["stack"])
        doc = self.run_sdlc("doctor")
        self.assertIn("detected Angular", doc.stdout)
        self.assertIn("copy what you want into your Makefile", doc.stdout)
        self.assertIn("npm run test -- --watch=false", doc.stdout)

    def test_none_forced_and_unknown(self):
        self.spring()
        r = self.setup_run("--profile", "solo", "--stack", "none", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.root / "Makefile").read_text().count('] not configured - edit Makefile"'), 5)
        self.assertIn("--stack none", r.stdout)
        shutil.rmtree(self.root / ".aiops")
        (self.root / "Makefile").unlink()
        r = self.setup_run("--profile", "solo", "--stack", "react", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.root / "Makefile").read_text().count('] not configured - edit Makefile"'), 5)
        self.assertIn("--stack react needs package.json", r.stdout)
        shutil.rmtree(self.root / ".aiops")
        before = self.snapshot()
        for cmd in (("setup", "--profile", "solo", "--stack", "rust", "--yes"), ("init", "--stack", "rust")):
            r = self.run_sdlc(*cmd, env={"PATH": str(self.bin_with())})
            self.assertEqual(r.returncode, 1, cmd)
            self.assertIn("auto, none, python, node, go, java, react, angular", r.stdout + r.stderr, cmd)
            self.assertEqual(self.snapshot(), before, cmd)

    def test_untouched_stub_makefile_is_wired(self):
        """Review round 1: a Makefile that is still the plugin's untouched stub template (the typed setup command
        writes one) is wired by setup; install-state records its new bytes."""
        from sdlc_engine import cli as engine

        self.assertEqual(self.run_sdlc("init", "--stack", "none").returncode, 0)
        self.assertEqual((self.root / "Makefile").read_bytes(), engine.rendered_template("Makefile"))
        self.spring()
        doc = self.run_sdlc("doctor")
        self.assertIn("sdlc setup --stack auto --yes", doc.stdout)
        r = self.setup_run("--profile", "solo", "--stack", "auto", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("\t./mvnw -B -q test\n", (self.root / "Makefile").read_text())
        st = self.state()
        self.assertEqual(st["recipes"], JAVA_RECIPES)
        import hashlib

        self.assertEqual(st["files"]["Makefile"]["sha256"], hashlib.sha256((self.root / "Makefile").read_bytes()).hexdigest())
        (self.root / "Makefile").write_text((self.root / "Makefile").read_text() + "# mine\n")
        before = (self.root / "Makefile").read_bytes()
        self.assertEqual(self.setup_run("--profile", "solo", "--stack", "auto", "--yes").returncode, 0)
        self.assertEqual((self.root / "Makefile").read_bytes(), before)  # no longer the stub: never touched

    def test_agent_never_wires(self):
        """Review round 2 (the human's choice, amends AC-12): run by the agent, setup and init create the stub
        Makefile and name the human's terminal command; the repo's commands run only after the human wires them."""
        from sdlc_engine import cli as engine

        self.spring()
        agent = {"CLAUDECODE": "1", "CLAUDE_PROJECT_DIR": str(self.root)}
        for cmd in (("setup", "--profile", "solo", "--yes"), ("init",)):
            r = self.run_sdlc(*cmd, env={"PATH": str(self.bin_with()), **agent})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual((self.root / "Makefile").read_bytes(), engine.rendered_template("Makefile"), cmd)
            self.assertIn("detected Java · Spring Boot · Maven", r.stdout)
            self.assertIn("setup --stack auto --yes", r.stdout)
            self.assertIn("in your own terminal", r.stdout)
            self.assertNotIn("recipes", self.state())
            self.assertIsNone(self.state()["stack"])
            if cmd[0] == "setup":
                shutil.rmtree(self.root / ".aiops")
                (self.root / "Makefile").unlink()
        doc = self.run_sdlc("doctor", env=agent)
        self.assertIn("review them, then wire them by running in your own terminal", doc.stdout)  # not the signing row
        r = self.setup_run("--profile", "solo", "--stack", "auto", "--yes")  # the human: wires the untouched stub
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("\t./mvnw -B -q test\n", (self.root / "Makefile").read_text())

    def test_wiring_without_profile_changes_no_config(self):
        """Review round 2 (security LOW): `setup --stack auto --yes` with no --profile wires the stub and leaves a
        hand-tuned config as it is; its differences become steps."""
        from sdlc_engine import cli as engine

        self.assertEqual(self.run_sdlc("init", "--stack", "none").returncode, 0)
        cfg = self.root / ".aiops" / "config.json"
        tuned = {**json.loads(cfg.read_text()), "profile": "solo", "require_signed_approvals": True, "approval_key_policy": "human"}
        cfg.write_text(json.dumps(tuned, indent=2) + "\n")
        before = cfg.read_bytes()
        self.spring()
        self.assertEqual((self.root / "Makefile").read_bytes(), engine.rendered_template("Makefile"))
        r = self.setup_run("--stack", "auto", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(cfg.read_bytes(), before)
        self.assertIn("\t./mvnw -B -q test\n", (self.root / "Makefile").read_text())

    def test_interactive_profile_is_written(self):
        """Review round 3 MAJOR: a profile the human picks at setup's question is applied, as with --profile; only a
        profile taken from the config leaves human-owned files alone."""
        import contextlib
        import io

        from sdlc_engine import setup

        self.assertEqual(self.run_sdlc("init", "--stack", "none").returncode, 0)  # a config with no profile
        answers = iter(["strict", "y"])
        buf = io.StringIO()
        with (
            mock.patch.object(setup, "_is_tty", return_value=True),
            mock.patch("builtins.input", lambda *_: next(answers)),
            mock.patch.object(setup, "preflight", return_value=[("✓", "git", "")]),
            contextlib.redirect_stdout(buf),
        ):
            code = setup.main(self.root, [])
        self.assertEqual(code, 0, buf.getvalue())
        self.assertEqual(json.loads((self.root / ".aiops" / "config.json").read_text())["profile"], "strict")

    def test_profile_from_config_says_changes_are_steps(self):
        self.assertEqual(self.run_sdlc("init", "--stack", "none").returncode, 0)
        cfg = self.root / ".aiops" / "config.json"
        cfg.write_text(json.dumps({**json.loads(cfg.read_text()), "profile": "solo"}, indent=2) + "\n")
        r = self.setup_run("--dry-run")
        self.assertIn("not applied without --profile", r.stdout)

    def test_wiring_command_keeps_a_forced_stack(self):
        """Review round 3: the printed command repeats a forced --stack (auto would refuse an ambiguous repo)."""
        self.spring()
        (self.root / "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}))
        r = self.run_sdlc("init", "--stack", "java", env={"CLAUDECODE": "1", "CLAUDE_PROJECT_DIR": str(self.root)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("setup --stack java --yes", r.stdout)
        self.assertNotIn("setup --stack auto --yes", r.stdout)

    def test_unwired_rewrite_drops_stale_recipes(self):
        """Review round 3: a Makefile rewritten unwired forgets the old recipes, so upgrade can't wire it back."""
        self.spring()
        self.assertEqual(self.setup_run("--profile", "solo", "--yes").returncode, 0)
        self.assertEqual(self.state()["recipes"], JAVA_RECIPES)
        self.assertEqual(self.run_sdlc("init", "--force", "--stack", "none").returncode, 0)
        st = self.state()
        self.assertNotIn("recipes", st)
        self.assertIsNone(st["stack"])
        stub = (self.root / "Makefile").read_bytes()
        self.assertEqual(self.run_sdlc("upgrade", "--yes").returncode, 0)
        self.assertEqual((self.root / "Makefile").read_bytes(), stub)

    def test_init_wires_the_untouched_stub(self):
        self.assertEqual(self.run_sdlc("init", "--stack", "none").returncode, 0)
        self.spring()
        r = self.run_sdlc("init")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("\t./mvnw -B -q test\n", (self.root / "Makefile").read_text())
        self.assertEqual(self.state()["recipes"], JAVA_RECIPES)

    def test_init_survives_a_hostile_package_json(self):
        """Review round 1: detection runs before init writes anything, and a deeply nested package.json is absent."""
        (self.root / "package.json").write_text("[" * 200000 + "]" * 200000)
        r = self.run_sdlc("init")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("package.json", r.stdout)
        self.assertTrue((self.root / ".aiops" / "install-state.json").is_file())

    def test_init_detects_and_prints_block(self):
        self.spring()
        r = self.run_sdlc("init")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("detected Java · Spring Boot · Maven", r.stdout)
        self.assertIn("\t./mvnw -B -q test\n", (self.root / "Makefile").read_text())
        self.assertEqual(self.state()["recipes"], JAVA_RECIPES)
        self.assertNotIn("copy the recipes", r.stdout)


if __name__ == "__main__":
    unittest.main()
