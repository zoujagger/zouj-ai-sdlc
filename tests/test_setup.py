"""`sdlc setup`: guided, rerunnable onboarding that keeps the playbook workflow in every profile."""
import json
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


def stub(bindir, name, body):
    f = bindir / name
    f.write_text("#!/bin/sh\n" + body + "\n")
    f.chmod(0o755)


class SetupCase(RepoCase):
    """A fresh, uninitialized repo, and a PATH of stub tools so setup's output doesn't depend on the machine."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")

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
        self.assertIn("Change .aiops/config.json yourself", steps)
        self.assertIn('"profile": "solo"', steps)
        self.assertIn('"require_signed_approvals": false', steps)

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
