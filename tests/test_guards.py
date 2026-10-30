"""Gate guards and hooks, driven through `bin/sdlc hook <event>` exactly as Claude Code calls them."""
import json
import unittest

from helpers import INTENT, PLAN, SPEC, RepoCase, git

from sdlc_engine import artifacts as A


class EditGuard(RepoCase):
    def edit(self, rel, content=None, old=None, new=None):
        path = str(self.root / rel)
        payload = self.hook_input("Write", file_path=path, content=content) if content is not None else \
            self.hook_input("Edit", file_path=path, old_string=old, new_string=new)
        return self.hook("pre-edit", payload)

    def assertBlocked(self, r, *needles):
        self.assertEqual(r.returncode, 2, r.stderr)
        for n in needles:
            self.assertIn(n, r.stderr)

    def test_code_is_read_only_until_plan_approved(self):
        self.assertBlocked(self.edit("src/app.py", "x = 2\n"), "read-only lock", "Procedure:")
        self.write("intent", INTENT)
        self.approve("intent")
        self.write("spec", SPEC)
        self.approve("spec")
        self.write("plan", PLAN)
        self.assertBlocked(self.edit("src/app.py", "x = 2\n"), "state 3 PLAN", "Plan Approved 0001")
        self.approve("plan")
        self.assertEqual(self.edit("src/app.py", "x = 2\n").returncode, 0)

    def test_docs_and_outside_paths_stay_writable(self):
        self.assertEqual(self.edit("NOTES.md", "n").returncode, 0)
        self.assertEqual(self.hook("pre-edit", self.hook_input("Write", file_path="/tmp/x.py", content="")).returncode, 0)

    def test_agent_cannot_approve_by_editing(self):
        self.write("intent", INTENT)
        r = self.edit(".aiops/0001-csv-export/intent.md", old="status: Draft", new="status: Approved")
        self.assertBlocked(r, "human gate", "Intent Approved 0001")
        self.assertEqual(self.edit(".aiops/0001-csv-export/intent.md", old="Users cannot", new="Reps cannot")
                         .returncode, 0)

    def test_agent_cannot_touch_approval_stamp(self):
        self.write("intent", INTENT)
        self.approve("intent")
        text = (self.d / "intent.md").read_text()
        forged = A.set_fields(text, {"approved-by": "someone else"})
        self.assertBlocked(self.edit(".aiops/0001-csv-export/intent.md", forged), "approved-by")

    def test_artifacts_are_created_in_order_and_as_draft(self):
        self.assertBlocked(self.edit(".aiops/0001-csv-export/spec.md", SPEC.format(id="0001")),
                           "needs an approved intent.md")
        self.write("intent", INTENT)
        self.approve("intent")
        self.assertBlocked(self.edit(".aiops/0001-csv-export/spec.md",
                                     SPEC.format(id="0001").replace("status: Draft", "status: Approved")),
                           "must start as `status: Draft`")
        self.assertEqual(self.edit(".aiops/0001-csv-export/spec.md", SPEC.format(id="0001")).returncode, 0)

    def test_plan_and_review_also_wait_for_their_upstream_gate(self):
        self.write("intent", INTENT)
        self.approve("intent")
        self.write("spec", SPEC)
        self.assertBlocked(self.edit(".aiops/0001-csv-export/plan.md", PLAN.format(id="0001")),
                           "needs an approved spec.md")
        self.approve("spec")
        self.write("plan", PLAN)
        self.assertBlocked(self.edit(".aiops/0001-csv-export/review.md", "---\nid: 0001\n---\n"),
                           "needs an approved plan.md")

    def test_guardrail_config_is_human_owned(self):
        self.assertBlocked(self.edit(".aiops/config/readonly-exempt", "src/*"), "human-owned")
        self.assertBlocked(self.edit(".aiops/state/test-lock", ""), "engine state")

    def test_uninitialized_repo_is_untouched(self):
        import shutil
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.edit("src/app.py", "x = 3\n").returncode, 0)


class BashGuard(RepoCase):
    def bash(self, command):
        return self.hook("pre-bash", self.hook_input("Bash", command=command))

    def blocked(self, command):
        r = self.bash(command)
        return r.returncode == 2

    def test_read_only_state_blocks_shell_writes_to_code(self):
        for cmd in ("echo 1 > src/app.py", "sed -i 's/1/2/' src/app.py", "tee src/new.py < /dev/null",
                    "cp README.md src/x.py", "rm src/app.py", "npm install left-pad", "python3 -m pip install x",
                    "git apply fix.patch", "git stash", "make format", "cd src && touch y.py"):
            self.assertTrue(self.blocked(cmd), cmd)

    def test_read_only_state_allows_reading_and_running(self):
        for cmd in ("ls -la > /dev/null 2>&1", "grep -rn x src | head", "make test", "git status", "git log -3",
                    "cat > /tmp/scratch.txt <<'EOF'\nx > src/app.py\nEOF", "echo hi >> NOTES.md",
                    "git switch -c feat/0001-csv-export", "sdlc status", "python3 -c 'print(1)'"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_execution_state_unlocks_shell_writes(self):
        self.to_execution()
        self.assertFalse(self.blocked("echo 2 > src/app.py"))
        self.assertFalse(self.blocked("npm install left-pad"))

    def test_staging_code_is_blocked_while_locked(self):
        (self.root / "src" / "app.py").write_text("y\n")
        self.assertTrue(self.blocked("git add -A"))
        self.assertTrue(self.blocked("git add src/app.py"))
        self.assertFalse(self.blocked("git add .aiops/0001-csv-export/intent.md"))
        git(self.root, "add", "src/app.py")
        self.assertTrue(self.blocked("git commit -m wip"))

    def test_always_blocked_regardless_of_state(self):
        self.to_execution()
        for cmd in ("sdlc approve 0001 plan", "~/.claude/plugins/x/bin/sdlc hook prompt < f",
                    "python3 -c 'import sdlc_engine.approvals'", "git commit -m x -m 'AIOps-Approval: plan 0001'",
                    "sed -i 's/Draft/Approved/' .aiops/0001-csv-export/plan.md",
                    "echo 0001 > .aiops/state/active"):
            self.assertTrue(self.blocked(cmd), cmd)

    def test_cd_is_tracked_when_resolving_targets(self):
        self.write("intent", INTENT)
        for cmd in ("cd src && sed -i s/Draft/Approved/ ../.aiops/0001-csv-export/intent.md",
                    "cd src && echo x > ../.aiops/0001-csv-export/intent.md",
                    "cd src; echo x > app.py"):
            self.assertTrue(self.blocked(cmd), cmd)
        self.assertFalse(self.blocked("cd src && echo x > /dev/null"))

    def test_nested_shells_and_message_files_are_inspected(self):
        msg = self.root / "msg.txt"
        msg.write_text("chore: x\n\nAIOps-Approval: intent 0001 sha256=abc\n")
        for cmd in ("bash -c 'echo 1 > src/app.py'", "sh -c \"rm src/app.py\"", "eval 'echo 1 > src/app.py'",
                    "git commit -F msg.txt", "git checkout src/app.py",
                    "gh api -X PUT repos/o/r/pulls/3/merge"):
            self.assertTrue(self.blocked(cmd), cmd)
        self.assertFalse(self.blocked("bash -c 'make test'"))

    def test_git_cannot_delete_or_restore_artifacts_even_when_unlocked(self):
        self.to_execution()
        for cmd in ("git rm .aiops/0001-csv-export/plan.md", "git checkout main -- .aiops/0001-csv-export/plan.md",
                    "git restore --source main .aiops/0001-csv-export/spec.md",
                    "git mv .aiops/0001-csv-export/plan.md /tmp/p.md"):
            self.assertTrue(self.blocked(cmd), cmd)
        self.assertFalse(self.blocked("git add .aiops/0001-csv-export/plan.md"))

    def test_merging_on_main_is_the_humans_decision(self):
        self.to_execution()
        git(self.root, "switch", "-q", "main")
        (self.root / ".aiops" / "state" / "active").write_text("0001\n")
        self.assertTrue(self.blocked("git merge feat/0001-csv-export"))
        git(self.root, "switch", "-q", "feat/0001-csv-export")
        self.assertFalse(self.blocked("git merge main"))


class PromptAndSessionHooks(RepoCase):
    def prompt(self, text):
        r = self.hook("prompt", {"prompt": text, "cwd": str(self.root), "hook_event_name": "UserPromptSubmit"},
                      env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""

    def test_exact_phrase_opens_the_gate(self):
        self.write("intent", INTENT)
        ctx = self.prompt("Intent Approved 0001")
        self.assertIn("gate OPENED", ctx)
        self.assertIn("state 2 SPECIFICATION", ctx)
        self.assertEqual(A.parse((self.d / "intent.md").read_text()).get("approved-via"), "prompt")

    def test_phrase_inside_a_sentence_does_nothing(self):
        self.write("intent", INTENT)
        self.assertEqual(self.prompt("the bot said: Intent Approved 0001"), "")
        self.assertEqual(A.parse((self.d / "intent.md").read_text()).get("status"), "Draft")

    def test_invalid_artifact_is_not_approved(self):
        self.write("intent", INTENT.replace("## Problem", "## Issue"))
        ctx = self.prompt("intent approved")
        self.assertIn("NOT opened", ctx)
        self.assertIn("## Problem", ctx)

    def test_cli_approve_refuses_inside_claude_code(self):
        self.write("intent", INTENT)
        r = self.run_sdlc("approve", "0001", "intent", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("human gate", r.stderr)
        self.assertEqual(self.run_sdlc("approve", "0001", "intent").returncode, 0)

    def test_session_start_prints_card_and_bootstrap(self):
        self.write("intent", INTENT)
        r = self.hook("session-start", {"cwd": str(self.root), "source": "startup"})
        self.assertIn("State: 1 BRAINSTORMING", r.stdout)
        self.assertIn("State Rules", r.stdout)

    def test_engine_hooks_are_dormant_without_aiops(self):
        import shutil
        self.write("intent", INTENT)
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.prompt("Intent Approved 0001"), "")
        self.assertEqual(self.hook("pre-bash", self.hook_input("Bash", command="echo 1 > src/app.py")).returncode, 0)
        self.assertEqual(self.hook("post-edit", self.hook_input("Write", file_path=str(self.root / "x.md"))).returncode, 0)
        r = self.hook("session-start", {"cwd": str(self.root)})
        self.assertIn("not initialized", r.stdout)
        self.assertNotIn("State Rules", r.stdout)

    def test_post_edit_reports_schema_errors(self):
        self.write("intent", INTENT.replace("## Constraints", "## Limits"))
        r = self.hook("post-edit", self.hook_input("Write", file_path=str(self.d / "intent.md")))
        self.assertEqual(r.returncode, 2)
        self.assertIn("## Constraints", r.stderr)


if __name__ == "__main__":
    unittest.main()
