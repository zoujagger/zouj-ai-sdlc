"""The AI-Native SDLC Playbook workflow (docs/sdlc.md) holds in every setup profile.

Each profile repo is created by `sdlc setup --profile <p> --yes`, then walked from intent to DONE through the real
guards and hooks. Profiles differ only in how a human approval is proven: a weak (passphrase-less) key is refused by
`team` and `strict`. To walk those profiles, the test plays the human with an accepted key by patching only the
key-protection check (a passphrase prompt or an sk- touch can't run in a test). The approval commits are still
really signed and verified against allowed-signers.
"""
import json
import subprocess
import sys
import unittest
from contextlib import ExitStack
from unittest import mock

from helpers import INTENT, PLAN, REVIEW, ROOT, SDLC, SPEC, allowed_signer_line, git, signing_key
from test_setup import SetupCase

from sdlc_engine import approvals, guards
from sdlc_engine.machine import evaluate

HOOKS = ROOT / "hooks"


class Playbook(SetupCase):
    def repo(self, profile):
        d = self.root.parent / f"{self.root.name}.{profile}"
        d.mkdir()
        git(d, "init", "-q", "-b", "main")
        for key, value in (("user.name", "Human Owner"), ("user.email", "owner@example.com"),
                           ("commit.gpgsign", "false")):
            git(d, "config", key, value)
        (d / "src").mkdir()
        (d / "src" / "app.py").write_text("x = 1\n")
        git(d, "add", "-A")
        git(d, "commit", "-qm", "init")
        env = {**self.env, "PATH": str(self.bin_with()), "CLAUDE_PROJECT_DIR": str(d)}
        r = subprocess.run([sys.executable, SDLC, "setup", "--profile", profile, "--yes"], cwd=d, input="",
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # the human registers their key (human-owned) and commits the scaffold
        (d / ".aiops" / "config" / "allowed-signers").write_text(
            allowed_signer_line("owner@example.com", signing_key()))
        git(d, "add", "-A")
        git(d, "commit", "-qm", "chore: adopt zouj-ai-sdlc")
        git(d, "switch", "-qc", "feat/0001-csv-export")
        intent = d / ".aiops" / "0001-csv-export"
        intent.mkdir()
        return d, intent

    def human_key(self, profile):
        """The human's accepted key: a passphrase key (team) or an sk- touch key (strict)."""
        stack = ExitStack()
        if profile in ("team", "strict"):
            stack.enter_context(mock.patch.object(approvals, "key_protection", return_value=None))
        if profile == "strict":
            real = approvals._signing_key_files
            stack.enter_context(mock.patch.object(
                approvals, "_signing_key_files", lambda root: ("sk-" + real(root)[0], real(root)[1])))
        return stack

    def approve(self, d, intent, kind, profile):
        with self.human_key(profile):
            ok, msg = approvals.approve(d, intent, kind, via="test")
        self.assertTrue(ok, msg)

    def edit_blocked(self, d, rel):
        return guards.check_edit({"tool_name": "Write", "cwd": str(d),
                                  "tool_input": {"file_path": str(d / rel), "content": "x = 2\n"}}) is not None

    def shell(self, hook, d, cmd):
        env = {**self.env, "CLAUDE_PROJECT_DIR": str(d), "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(d)}
        return subprocess.run([str(HOOKS / hook)], input=json.dumps(payload), capture_output=True, text=True,
                              env=env, cwd=d).returncode

    def walk(self, profile):
        d, intent = self.repo(profile)
        (intent / "intent.md").write_text(INTENT.format(id="0001"))
        state = lambda: evaluate(d, intent).state  # noqa: E731
        self.assertEqual(state(), 1)
        # the proof differs by profile: the weak test key is refused by team and strict
        ok, msg = approvals.approve(d, intent, "intent", via="test")
        self.assertEqual(ok, profile == "solo", msg)
        if not ok:
            self.assertIn("passphrase" if profile == "team" else "sk-", msg)
        # states 1-3: code is read-only and the agent can't open a gate
        for kind, nxt in (("intent", "spec"), ("spec", "plan"), ("plan", None)):
            self.assertTrue(self.edit_blocked(d, "src/app.py"), (profile, kind))
            self.assertIsNotNone(guards.check_bash({"tool_input": {"command": f"sdlc approve 0001 {kind}"},
                                                    "cwd": str(d)}), (profile, kind))
            if not (profile == "solo" and kind == "intent"):            # solo already approved it above
                self.approve(d, intent, kind, profile)
            if nxt:
                (intent / f"{nxt}.md").write_text((SPEC if nxt == "spec" else PLAN).format(id="0001"))
        self.assertEqual(state(), 4)
        self.assertFalse(self.edit_blocked(d, "src/app.py"))             # state 4: code unlocked
        # the Stop hook requires `make check` green
        (d / "src" / "app.py").write_text("x = 2\n")
        makefile = (d / "Makefile").read_text()
        (d / "Makefile").write_text(makefile.replace("check: lint typecheck test", "check:\n\t@exit 1\n\nold-check: lint typecheck test"))
        self.assertEqual(self.shell("stop-verify.sh", d, ""), 2)
        (d / "Makefile").write_text(makefile)
        self.assertEqual(self.shell("stop-verify.sh", d, ""), 0)
        # the final gates stay human: no merge, no push to main, no production deploy
        self.assertEqual(self.shell("guard-bash.sh", d, "gh pr merge 1 --merge"), 2)
        self.assertEqual(self.shell("guard-bash.sh", d, "git push origin main"), 2)
        self.assertEqual(self.shell("guard-deploy.sh", d, "make deploy ENV=prod"), 2)
        # every plan step done, then review, then DONE only once the human has merged it into main
        plan = intent / "plan.md"
        plan.write_text(plan.read_text().replace("- [ ]", "- [x]"))
        self.assertEqual(state(), 5)
        git(d, "add", "-A")
        git(d, "commit", "-qm", "feat: csv export")
        (intent / "review.md").write_text(REVIEW.format(id="0001", verdict="PASS", commit=git(d, "rev-parse", "HEAD")))
        git(d, "add", "-A")
        git(d, "commit", "-qm", "docs(aiops): review 0001")
        self.assertEqual(state(), 5)
        git(d, "switch", "-q", "main")
        git(d, "merge", "-q", "--no-ff", "-m", "merge", "feat/0001-csv-export")      # the human merges
        self.assertEqual(state(), 6)

    def test_solo(self):
        self.walk("solo")

    def test_team(self):
        self.walk("team")

    def test_strict(self):
        self.walk("strict")


if __name__ == "__main__":
    unittest.main()
