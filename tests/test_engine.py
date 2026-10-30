"""State engine: parsing, derived states, approvals, staleness, CI audit."""
import unittest

from helpers import INTENT, PLAN, REVIEW, SPEC, RepoCase, git

from sdlc_engine import approvals
from sdlc_engine import artifacts as A
from sdlc_engine.machine import evaluate, lock
from sdlc_engine.schema import validate


class Artifacts(unittest.TestCase):
    def test_front_matter_strips_trailing_comments_but_keeps_hash_values(self):
        a = A.parse("---\nstatus: Draft   # Draft | Approved\nsource: #12\n---\nbody")
        self.assertEqual(a.get("status"), "Draft")
        self.assertEqual(a.get("source"), "#12")
        self.assertEqual(a.body, "body")

    def test_set_fields_replaces_and_appends(self):
        text = A.set_fields("---\nstatus: Draft  # c\n---\nbody\n", {"status": "Approved", "approved-by": "me"})
        self.assertEqual(A.parse(text).front, {"status": "Approved", "approved-by": "me"})
        self.assertTrue(text.endswith("body\n"))

    def test_plan_hash_ignores_progress_and_deviation_log(self):
        plan = PLAN.format(id="0001")
        ticked = plan.replace("- [ ] **S1**", "- [x] **S1**") + "| 2026-10-30 | S1 | renamed | clarity | abc |\n"
        self.assertEqual(A.approval_hash("plan", plan), A.approval_hash("plan", ticked))
        self.assertNotEqual(A.approval_hash("plan", plan), A.approval_hash("plan", plan.replace("Small.", "Big.")))

    def test_spec_hash_changes_with_body_but_not_front_matter(self):
        spec = SPEC.format(id="0001")
        self.assertEqual(A.approval_hash("spec", spec), A.approval_hash("spec", A.set_fields(spec, {"x": "1"})))
        self.assertNotEqual(A.approval_hash("spec", spec), A.approval_hash("spec", spec + "\nmore"))


class States(RepoCase):
    def state(self):
        return evaluate(self.root, self.d)

    def test_walks_the_five_states(self):
        self.assertEqual(self.state().state, 1)
        self.write("intent", INTENT)
        st = self.state()
        self.assertEqual((st.state, st.waiting_on), (1, "human"))
        self.assertIn("Intent Approved 0001", st.next)
        self.approve("intent")
        self.assertEqual(self.state().state, 2)
        self.write("spec", SPEC)
        self.approve("spec")
        self.assertEqual(self.state().state, 3)
        self.write("plan", PLAN)
        self.approve("plan")
        st = self.state()
        self.assertEqual((st.state, st.steps_done, st.steps_total), (4, 0, 2))
        self.write("plan", (self.d / "plan.md").read_text().replace("- [ ]", "- [x]"))
        self.assertEqual(self.state().state, 5)
        self.assertIn("no review", self.state().detail)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "work")
        head = git(self.root, "rev-parse", "HEAD")
        self.write("review", REVIEW.format(id="0001", verdict="PASS", commit=head))
        st = self.state()
        self.assertEqual((st.state, st.waiting_on), (5, "human"))
        self.assertIn("merge", st.next)

    def test_review_goes_stale_when_code_changes(self):
        self.to_execution()
        self.write("plan", (self.d / "plan.md").read_text().replace("- [ ]", "- [x]"))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "work")
        self.write("review", REVIEW.format(id="0001", verdict="PASS", commit=git(self.root, "rev-parse", "HEAD")))
        (self.root / "src" / "app.py").write_text("x = 2\n")
        self.assertIn("changed after the review", self.state().detail)

    def test_done_once_review_is_on_main(self):
        self.to_execution()
        self.write("plan", (self.d / "plan.md").read_text().replace("- [ ]", "- [x]"))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "work")
        self.write("review", REVIEW.format(id="0001", verdict="PASS", commit=git(self.root, "rev-parse", "HEAD")))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "review")
        git(self.root, "switch", "-q", "main")
        git(self.root, "merge", "-q", "--no-ff", "-m", "merge", "feat/0001-csv-export")
        self.assertEqual(self.state().state, 6)

    def test_editing_an_approved_spec_reopens_the_gate(self):
        self.write("intent", INTENT)
        self.approve("intent")
        self.write("spec", SPEC)
        self.approve("spec")
        self.write("spec", (self.d / "spec.md").read_text().replace("Export contacts.", "Export everything."))
        st = self.state()
        self.assertEqual(st.state, 2)
        self.assertIn("changed after it was approved", st.detail)

    def test_lock_follows_state_and_idle(self):
        self.assertTrue(lock(self.root)[0])               # state 1
        self.to_execution()
        self.assertFalse(lock(self.root)[0])              # state 4
        git(self.root, "switch", "-qc", "chore/x")
        self.assertTrue(lock(self.root)[0])               # no active intent (state/active not set)
        (self.root / ".aiops" / "state" / "active").write_text("0001\n")
        self.assertFalse(lock(self.root)[0])

    def test_spike_profile_and_uninitialized_repo_do_not_lock(self):
        import os
        os.environ["SDLC_HOOK_PROFILE"] = "spike"
        self.assertFalse(lock(self.root)[0])
        del os.environ["SDLC_HOOK_PROFILE"]
        import shutil
        shutil.rmtree(self.root / ".aiops")
        self.assertFalse(lock(self.root)[0])


class Approvals(RepoCase):
    def test_refuses_invalid_artifact(self):
        self.write("intent", INTENT.replace("## Out of scope", "## Nope"))
        ok, msg = approvals.approve(self.root, self.d, "intent", via="test")
        self.assertFalse(ok)
        self.assertIn("missing section `## Out of scope`", msg)

    def test_refuses_when_upstream_gate_closed(self):
        self.write("intent", INTENT)
        self.write("spec", SPEC)
        ok, msg = approvals.approve(self.root, self.d, "spec", via="test")
        self.assertFalse(ok)
        self.assertIn("intent.md for 0001 is not approved", msg)

    def test_plan_must_cover_every_spec_ac(self):
        self.write("intent", INTENT)
        self.approve("intent")
        self.write("spec", SPEC)
        self.approve("spec")
        self.write("plan", PLAN.replace("AC-2", "AC-1"))
        errors, _ = validate(self.d, "plan")
        self.assertTrue(any("AC-2" in e for e in errors), errors)

    def test_approval_is_stamped_and_committed_alone(self):
        self.write("intent", INTENT)
        (self.root / "src" / "app.py").write_text("dirty\n")
        self.approve("intent")
        a = A.parse((self.d / "intent.md").read_text())
        self.assertEqual(a.get("status"), "Approved")
        self.assertEqual(a.get("approved-by"), "Human Owner <owner@example.com>")
        msg = git(self.root, "log", "-1", "--format=%B")
        self.assertIn("AIOps-Approval: intent 0001", msg)
        self.assertEqual(git(self.root, "show", "--name-only", "--format=", "HEAD"), ".aiops/0001-csv-export/intent.md")
        self.assertIn("src/app.py", git(self.root, "status", "--porcelain"))

    def test_ci_audit_accepts_human_and_rejects_agent_approvals(self):
        self.write("intent", INTENT)
        self.approve("intent")
        self.assertEqual(approvals.audit(self.root, self.d, "intent"), [])
        # forge: an agent writes the stamp itself and commits with its co-author trailer
        self.write("spec", SPEC)
        text = (self.d / "spec.md").read_text()
        (self.d / "spec.md").write_text(A.set_fields(text, {
            "status": "Approved", "approved-by": "bot", "approved-sha256": A.approval_hash("spec", text)}))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "spec", "-m", "Co-Authored-By: Claude <noreply@anthropic.com>")
        errors = approvals.audit(self.root, self.d, "spec")
        self.assertTrue(errors and "not an approval commit" in errors[0], errors)

    def test_ci_audit_rejects_forged_trailer_commits(self):
        self.write("intent", INTENT)
        self.approve("intent")
        self.write("spec", SPEC)
        text = (self.d / "spec.md").read_text()
        h = A.approval_hash("spec", text)
        (self.d / "spec.md").write_text(A.set_fields(text, {"status": "Approved", "approved-by": "bot",
                                                             "approved-sha256": h}))
        (self.root / "src" / "app.py").write_text("sneaky\n")
        git(self.root, "add", "-A")    # forged: right trailer, but bundled with code and the wrong digest
        git(self.root, "commit", "-qm", "chore(aiops): Spec Approved 0001", "-m", "AIOps-Approval: spec 0001 sha256=deadbeef")
        errors = approvals.audit(self.root, self.d, "spec")
        self.assertTrue(any("only" in e or "sha256" in e for e in errors), errors)

    def test_ci_audit_can_require_signed_approval_commits(self):
        (self.root / ".aiops" / "config.json").write_text('{"require_signed_approvals": true}')
        self.write("intent", INTENT)
        self.approve("intent")                       # the test repo can't sign
        errors = approvals.audit(self.root, self.d, "intent")
        self.assertTrue(errors and "not signed" in errors[0], errors)

    def test_closed_intent(self):
        self.write("intent", INTENT.replace("status: Draft", "status: Closed"))
        self.assertEqual(evaluate(self.root, self.d).state, 0)


if __name__ == "__main__":
    unittest.main()
