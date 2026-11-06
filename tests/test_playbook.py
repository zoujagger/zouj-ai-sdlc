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


def snapshot(d, intent):
    """What the playbook protects, as it stands: the state, the gates, the artifacts, whether code is locked, and
    every file outside .aiops/ (the code the lock guards)."""
    import hashlib
    st = evaluate(d, intent)
    code = {}
    for p in sorted(d.rglob("*")):
        rel = p.relative_to(d).as_posix()
        if p.is_file() and not rel.startswith((".git/", ".aiops/")):
            code[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    locked = guards.check_edit({"tool_name": "Write", "cwd": str(d),
                                "tool_input": {"file_path": str(d / "src" / "app.py"), "content": "x = 2\n"}})
    return {"state": st.state, "gates": dict(st.gates), "locked": locked is not None, "code": code,
            "artifacts": {p.name: p.read_bytes() for p in sorted(intent.glob("*.md"))}}


def playbook_violations(d, intent, before):
    """[] if nothing the playbook protects changed since `before` (a snapshot()), else one line per break."""
    after, found = snapshot(d, intent), []
    if after["state"] != before["state"]:
        found.append(f"state changed: {before['state']} -> {after['state']}")
    for gate, was in before["gates"].items():
        if after["gates"].get(gate) != was:
            found.append(f"gate {gate} changed: {was} -> {after['gates'].get(gate)}")
    for name in sorted(set(before["artifacts"]) | set(after["artifacts"])):
        if name not in after["artifacts"]:
            found.append(f"artifact removed: {name}")
        elif name not in before["artifacts"]:
            found.append(f"artifact added: {name}")
        elif after["artifacts"][name] != before["artifacts"][name]:
            found.append(f"artifact rewritten: {name}")
    if before["locked"] and not after["locked"]:
        found.append("the read-only lock no longer holds")
    if before["locked"]:
        changed = sorted(rel for rel in set(before["code"]) | set(after["code"])
                         if before["code"].get(rel) != after["code"].get(rel))
        found += [f"code changed under the read-only lock: {rel}" for rel in changed]
    return found


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

    def lifecycle_as_agent(self, d, intent, where):
        """The agent runs upgrade and repair mid-walk: no gate, artifact, lock or locked code may change."""
        before = snapshot(d, intent)
        env = {**self.env, "PATH": str(self.bin_with()), "CLAUDE_PROJECT_DIR": str(d), "CLAUDECODE": "1"}
        for args in (("upgrade", "--yes"), ("repair", "--yes")):
            r = subprocess.run([sys.executable, SDLC, *args], cwd=d, input="", capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, f"{where} {args}: {r.stdout}{r.stderr}")
        self.assertEqual(playbook_violations(d, intent, before), [], where)

    def gate_allowances_rejected(self, d):
        """An allowed-commands entry for a gate rule lifts nothing (only heuristic rules are allowable)."""
        (d / ".aiops" / "config" / "allowed-commands").write_text(
            "G-MERGE-03 git push origin main\nG-ART-05 rm -rf .aiops/0001-csv-export\nG-MERGE-04 gh pr merge 1\n")
        self.assertEqual(self.shell("guard-bash.sh", d, "git push origin main"), 2)
        self.assertEqual(self.shell("guard-bash.sh", d, "gh pr merge 1"), 2)
        self.assertIsNotNone(guards.check_bash({"tool_input": {"command": "rm -rf .aiops/0001-csv-export"},
                                                "cwd": str(d)}))
        doctor = subprocess.run([sys.executable, SDLC, "doctor"], cwd=d, capture_output=True, text=True,
                                env={**self.env, "PATH": str(self.bin_with())})
        self.assertIn("G-MERGE-03 is a gate rule", doctor.stdout)
        (d / ".aiops" / "config" / "allowed-commands").unlink()

    def walk(self, profile):
        d, intent = self.repo(profile)
        (intent / "intent.md").write_text(INTENT.format(id="0001"))
        state = lambda: evaluate(d, intent).state  # noqa: E731
        self.assertEqual(state(), 1)
        self.lifecycle_as_agent(d, intent, f"{profile} state 1")
        self.gate_allowances_rejected(d)
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
        self.lifecycle_as_agent(d, intent, f"{profile} state 4")
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
        self.lifecycle_as_agent(d, intent, f"{profile} state 5")
        git(d, "add", "-A")
        git(d, "commit", "-qm", "feat: csv export")
        # a failing review keeps it at state 5, even once that review reaches main
        (intent / "review.md").write_text(REVIEW.format(id="0001", verdict="CHANGES_REQUESTED",
                                                        commit=git(d, "rev-parse", "HEAD")))
        git(d, "add", "-A")
        git(d, "commit", "-qm", "docs(aiops): review 0001 (changes requested)")
        self.assertEqual(state(), 5)
        base = git(d, "rev-parse", "main")
        git(d, "switch", "-q", "main")
        git(d, "merge", "-q", "--no-ff", "-m", "merge", "feat/0001-csv-export")
        self.assertEqual(state(), 5, profile)                            # FAIL on main is not DONE
        git(d, "reset", "-q", "--hard", base)                            # undo that merge (test only)
        git(d, "switch", "-q", "feat/0001-csv-export")
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



class Mutation(Playbook):
    """A permanent test that the conformance checker catches an upgrade that breaks the playbook (0004 S16, plan gate
    decision): upgrade runs for real, then a planted break happens; playbook_violations must report each one."""
    test_solo = test_team = test_strict = None                          # the walks run once, in Playbook

    def test_conformance_catches_broken_upgrade(self):
        import os
        from sdlc_engine import lifecycle
        d, intent = self.repo("solo")
        (intent / "intent.md").write_text(INTENT.format(id="0001"))
        self.assertEqual(evaluate(d, intent).state, 1)
        os.chdir(d)
        st_file = d / ".aiops" / "install-state.json"
        pristine = {p: p.read_bytes() for p in (intent / "intent.md", d / "src" / "app.py", st_file)}

        def stamp_approval(d, intent):
            f = intent / "intent.md"
            f.write_text(f.read_text().replace("status: Draft", "status: Approved\napproved-sha256: " + "0" * 64))

        breaks = {"opens a gate": stamp_approval,
                  "deletes an artifact": lambda d, intent: (intent / "intent.md").unlink(),
                  "writes code under the lock": lambda d, intent: (d / "src" / "app.py").write_text("x = 99\n")}
        real_save = lifecycle.save
        for name, plant in [("control", None), *breaks.items()]:
            with self.subTest(name):
                for p, data in pristine.items():
                    p.write_bytes(data)
                st = json.loads(st_file.read_text())
                st["plugin_version"] = "0.1.0"                         # so upgrade has something to record
                st_file.write_text(json.dumps(st))
                before = snapshot(d, intent)

                def broken_save(root, state, plant=plant):
                    real_save(root, state)
                    if plant:
                        plant(d, intent)
                with mock.patch.object(lifecycle, "save", broken_save), \
                        mock.patch.object(lifecycle, "resolve_ref", return_value=(f"v{lifecycle.cli.plugin_version()}", None)), \
                        mock.patch("sdlc_engine.cli.out"):
                    self.assertEqual(lifecycle.cmd_upgrade(d, ["--yes"]), 0)
                found = playbook_violations(d, intent, before)
                if plant is None:
                    self.assertEqual(found, [])
                else:
                    self.assertNotEqual(found, [], name)
        os.chdir(self.root)


if __name__ == "__main__":
    unittest.main()
