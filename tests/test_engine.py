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

    def test_done_reported_on_feature_branch_after_merge(self):
        self.to_execution()
        self.write("plan", (self.d / "plan.md").read_text().replace("- [ ]", "- [x]"))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "work")
        self.write("review", REVIEW.format(id="0001", verdict="PASS", commit=git(self.root, "rev-parse", "HEAD")))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "review")
        self.assertEqual(self.state().state, 5)                 # before the merge: still waiting on the human
        git(self.root, "switch", "-q", "main")
        git(self.root, "merge", "-q", "--no-ff", "-m", "merge", "feat/0001-csv-export")
        git(self.root, "switch", "-q", "feat/0001-csv-export")
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

    def test_copied_folder_does_not_open_gates(self):
        import shutil
        from sdlc_engine.machine import gate
        self.write("intent", INTENT)
        self.approve("intent")
        copy = self.root / ".aiops" / "0002-copy"
        shutil.copytree(self.d, copy)
        self.assertTrue(gate(self.d, "intent")[0])
        ok, why = gate(copy, "intent")
        self.assertFalse(ok)
        self.assertIn("id", why)
        self.assertEqual(evaluate(self.root, copy).state, 1)

    def test_initialized_when_tracked_but_missing(self):
        import shutil
        from sdlc_engine.machine import initialized
        self.write("intent", INTENT)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "intent")
        shutil.rmtree(self.root / ".aiops")
        self.assertTrue(initialized(self.root))
        self.assertTrue(lock(self.root)[0])

    def test_spike_profile_and_uninitialized_repo_do_not_lock(self):
        import os
        os.environ["SDLC_HOOK_PROFILE"] = "spike"
        self.assertFalse(lock(self.root)[0])
        del os.environ["SDLC_HOOK_PROFILE"]
        import shutil
        shutil.rmtree(self.root / ".aiops")
        self.assertFalse(lock(self.root)[0])


class Approvals(RepoCase):
    def test_signing_toolchain_is_pinned(self):
        from sdlc_engine import approvals as ap
        self.write("intent", INTENT)
        for key, value in (("gpg.ssh.program", "/tmp/evil-signer"), ("core.hooksPath", "/tmp/hooks"),
                           ("user.signingkey", "/tmp/k.pub")):
            git(self.root, "config", "--local", key, value)
            ok, msg = ap.approve(self.root, self.d, "intent", via="test")
            self.assertFalse(ok, key)
            self.assertIn("repo-local", msg)
            git(self.root, "config", "--local", "--unset", key)
        hook = self.root / ".git" / "hooks" / "post-commit"            # a planted hook must not run
        hook.write_text(f"#!/bin/sh\ntouch {self.root}/hook-ran\n")
        hook.chmod(0o755)
        calls, real = [], ap.subprocess.run

        def spy(cmd, *args, **kw):
            calls.append((cmd, kw))
            return real(cmd, *args, **kw)
        ap.subprocess.run = spy
        try:
            self.approve("intent")
        finally:
            ap.subprocess.run = real
        args, kw = next(c for c in calls if "commit-tree" in c[0])     # plumbing: commit-tree runs no hooks at all
        self.assertTrue(args[0].startswith("/"), args[0])               # git by absolute path, not via PATH
        for pinned in ("core.hooksPath=/dev/null", "core.fsmonitor=false", "core.attributesFile=/dev/null"):
            self.assertIn(pinned, args)
        self.assertTrue(any(a.startswith("gpg.ssh.program=/") and a.endswith("ssh-keygen") for a in args), args)
        self.assertIsNone(kw.get("timeout"))                           # a slow passphrase or touch isn't killed
        self.assertFalse((self.root / "hook-ran").exists())

    def test_repo_local_config_is_allow_listed(self):
        from sdlc_engine import approvals as ap
        self.write("intent", INTENT)
        inc = self.root.parent / f"{self.root.name}.inc"
        inc.write_text('[gpg "ssh"]\n\tprogram = /tmp/evil-signer\n')
        for key, value in (("core.fsmonitor", "/tmp/x.sh"), ("core.attributesFile", "/tmp/attrs"),
                           ("filter.x.clean", "/tmp/x.sh"), ("include.path", str(inc)), ("alias.ci", "!sh")):
            git(self.root, "config", "--local", key, value)
            problem = ap.signing_problem(self.root)
            self.assertTrue(problem and "repo-local" in problem, (key, problem))
            git(self.root, "config", "--local", "--unset", key)
        self.assertIsNone(ap.signing_problem(self.root))           # name, email, core.* basics stay allowed

    def test_approval_runs_no_monitor_or_filter(self):
        marker = self.root.parent / f"{self.root.name}.ran"
        monitor, clean = (self.root.parent / f"{self.root.name}.{n}" for n in ("monitor", "clean"))
        monitor.write_text(f"#!/bin/sh\nps -o args= $PPID >> {marker}\n")
        clean.write_text(f"#!/bin/sh\nps -o args= $PPID >> {marker}\ncat\n")
        monitor.chmod(0o755)
        clean.chmod(0o755)
        # global config is out of the repo-local allow-list's reach, so the commit itself must not run them
        git(self.root, "config", "--global", "core.fsmonitor", str(monitor))
        git(self.root, "config", "--global", "filter.x.clean", str(clean))
        (self.root / ".gitattributes").write_text("* filter=x\n")
        self.write("intent", INTENT)
        self.approve("intent")
        self.assertFalse(marker.exists(), marker.read_text() if marker.exists() else "")
        sha = git(self.root, "log", "-1", "--format=%H")
        self.assertEqual(git(self.root, "show", "--name-only", "--format=", sha), ".aiops/0001-csv-export/intent.md")
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only"), "")    # the index follows the commit

    def test_approval_reports_a_stuck_index_and_refuses_symlinks(self):
        import os
        self.write("intent", INTENT)
        lock = self.root / ".git" / "index.lock"
        lock.write_text("")                                          # an IDE holds the index
        try:
            ok, msg = approvals.approve(self.root, self.d, "intent", via="test")
        finally:
            lock.unlink()
        self.assertTrue(ok, msg)
        self.assertIn("git reset -q -- .aiops/0001-csv-export/intent.md", msg)
        self.write("spec", SPEC)
        real = self.root / "spec-real.md"
        (self.d / "spec.md").rename(real)
        os.symlink(real, self.d / "spec.md")
        ok, msg = approvals.approve(self.root, self.d, "spec", via="test")
        self.assertFalse(ok)
        self.assertIn("symlink", msg)

    def test_engine_runs_git_by_absolute_path(self):
        from sdlc_engine import machine
        self.assertTrue(machine.GIT.startswith("/"), machine.GIT)
        calls, real = [], machine.subprocess.run

        def spy(cmd, *a, **kw):
            calls.append(cmd)
            return real(cmd, *a, **kw)
        machine.subprocess.run = spy
        try:
            machine.git(self.root, "status")
        finally:
            machine.subprocess.run = real
        self.assertEqual(calls[0][0], machine.GIT)

    def test_key_policy_requires_a_human_per_signature(self):
        import os
        import subprocess
        from helpers import signing_key
        from sdlc_engine import approvals as ap
        cfg = self.root / ".aiops" / "config.json"
        cfg.write_text('{"approval_key_policy": "human"}')
        # 1. an unprotected key: refused before stamping
        self.write("intent", INTENT)
        ok, msg = approvals.approve(self.root, self.d, "intent", via="test")
        self.assertFalse(ok)
        self.assertIn("passphrase", msg)
        self.assertEqual(A.parse((self.d / "intent.md").read_text()).get("status"), "Draft")
        # 2. a passphrase key that is NOT in ssh-agent: passes the precheck (git will ask the human)
        protected = signing_key("protected", passphrase="s3cret-pass")
        git(self.root, "config", "--global", "user.signingkey", f"{protected}.pub")
        self.assertIsNone(ap.signing_problem(self.root))
        # 3. the same key loaded in ssh-agent: refused (it would sign without asking)
        agent = subprocess.run(["ssh-agent", "-s"], capture_output=True, text=True, check=True).stdout
        env = dict(line.split(";")[0].split("=", 1) for line in agent.splitlines() if "=" in line.split(";")[0])
        askpass = self.root / "askpass.sh"
        askpass.write_text("#!/bin/sh\necho s3cret-pass\n")
        askpass.chmod(0o700)
        try:
            os.environ.update(env)
            subprocess.run(["ssh-add", "-q", str(protected)], check=True, capture_output=True,
                           env={**os.environ, "SSH_ASKPASS": str(askpass), "SSH_ASKPASS_REQUIRE": "force", "DISPLAY": ":0"})
            problem = ap.signing_problem(self.root)
            self.assertTrue(problem and "ssh-agent" in problem, problem)
        finally:
            subprocess.run(["ssh-agent", "-k"], capture_output=True, env={**os.environ})
            for k in env:
                os.environ.pop(k, None)
        # 4. a FIDO sk- key: a touch per signature, accepted
        sk = self.root / "sk.pub"
        sk.write_text("sk-ssh-ed25519@openssh.com AAAAGnNrLXNzaC1lZDI1NTE5QG9wZW5zc2guY29t owner\n")
        git(self.root, "config", "--global", "user.signingkey", str(sk))
        self.assertIsNone(ap.signing_problem(self.root))
        # 5. the human-owned escape hatch restores the old behaviour for an unprotected key
        git(self.root, "config", "--global", "user.signingkey", f"{signing_key()}.pub")
        cfg.write_text('{"approval_key_policy": "any"}')
        self.assertIsNone(ap.signing_problem(self.root))

    def test_refuses_without_signing_key_before_stamping(self):
        git(self.root, "config", "--global", "--unset", "user.signingkey")
        self.write("intent", INTENT)
        ok, msg = approvals.approve(self.root, self.d, "intent", via="test")
        self.assertFalse(ok)
        self.assertIn("user.signingkey", msg)
        self.assertEqual(A.parse((self.d / "intent.md").read_text()).get("status"), "Draft")

    def test_approval_commit_is_signed(self):
        self.write("intent", INTENT)
        self.approve("intent")
        sig = git(self.root, "-c", f"gpg.ssh.allowedSignersFile={self.signers}", "log", "-1", "--format=%G?")
        self.assertEqual(sig, "G")

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
        cfg = self.root / ".aiops" / "config.json"
        cfg.write_text('{"require_signed_approvals": false}')
        self.write("intent", INTENT)
        self.approve("intent")                       # unsigned while signing was off
        cfg.write_text('{"require_signed_approvals": true}')
        errors = approvals.audit(self.root, self.d, "intent")
        self.assertTrue(errors and "not signed" in errors[0], errors)

    def test_audit_rejects_multi_file_approval_commit(self):
        self.write("intent", INTENT)
        self.approve("intent")
        self.write("spec", SPEC)
        text = (self.d / "spec.md").read_text()
        digest = A.approval_hash("spec", text)
        (self.d / "spec.md").write_text(A.set_fields(text, {"status": "Approved", "approved-by": "bot",
                                                             "approved-sha256": digest}))
        (self.root / "src" / "app.py").write_text("sneaky\n")
        git(self.root, "add", "-A")    # right trailer and digest, but bundled with code
        git(self.root, "commit", "-qm", "chore(aiops): Spec Approved 0001", "-m", f"AIOps-Approval: spec 0001 sha256={digest}")
        errors = approvals.audit(self.root, self.d, "spec")
        self.assertTrue(errors and "must change only" in errors[0], errors)

    def test_audit_requires_allow_listed_signer(self):
        from helpers import allowed_signer_line, signing_key
        cfg = self.root / ".aiops" / "config.json"
        # 1. unlisted key: signed, but not by an allow-listed signer
        git(self.root, "config", "--global", "user.signingkey", f"{signing_key('intruder')}.pub")
        self.write("intent", INTENT)
        self.approve("intent")
        errors = approvals.audit(self.root, self.d, "intent")
        self.assertTrue(errors and "allow-listed" in errors[0], errors)
        # 2. the PR adds its own key: trusted from the working tree, rejected against the base ref
        git(self.root, "add", ".aiops/config/allowed-signers")
        git(self.root, "commit", "-qm", "signers (owner only)")
        git(self.root, "branch", "base")
        with self.signers.open("a") as f:
            f.write(allowed_signer_line("owner@example.com", signing_key("intruder")))
        self.assertEqual(approvals.audit(self.root, self.d, "intent"), [])
        errors = approvals.audit(self.root, self.d, "intent", base="base")
        self.assertTrue(errors and "allow-listed" in errors[0], errors)
        # 3. unsigned, then listed in legacy-approvals (read from base) → accepted
        cfg.write_text('{"require_signed_approvals": false}')
        self.write("spec", SPEC)
        self.approve("spec")
        cfg.write_text('{"require_signed_approvals": true}')
        sha = git(self.root, "log", "-1", "--format=%H")
        self.assertTrue(approvals.audit(self.root, self.d, "spec"))
        (self.root / ".aiops" / "config" / "legacy-approvals").write_text(f"# pre-signing approvals\n{sha}\n")
        self.assertEqual(approvals.audit(self.root, self.d, "spec"), [])
        self.assertTrue(approvals.audit(self.root, self.d, "spec", base="base"))   # not in the base's legacy list

    def test_legacy_needs_full_sha_and_clean_commit(self):
        cfg = self.root / ".aiops" / "config.json"
        legacy = self.root / ".aiops" / "config" / "legacy-approvals"
        cfg.write_text('{"require_signed_approvals": false}')
        self.write("intent", INTENT)
        self.approve("intent")                                   # clean, unsigned
        sha = git(self.root, "log", "-1", "--format=%H")
        # a forged spec approval: right fields, but co-authored by Claude
        self.write("spec", SPEC)
        text = (self.d / "spec.md").read_text()
        digest = A.approval_hash("spec", text)
        (self.d / "spec.md").write_text(A.set_fields(text, {"status": "Approved", "approved-by": "bot",
                                                             "approved-sha256": digest}))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "spec", "-m", f"AIOps-Approval: spec 0001 sha256={digest}",
            "-m", "Co-Authored-By: Claude <noreply@anthropic.com>")
        forged = git(self.root, "log", "-1", "--format=%H")
        cfg.write_text('{"require_signed_approvals": true}')
        legacy.write_text(f"{sha[:7]}\n")                        # a short sha no longer counts
        self.assertTrue(approvals.audit(self.root, self.d, "intent"))
        legacy.write_text(f"{sha}\n")
        self.assertEqual(approvals.audit(self.root, self.d, "intent"), [])
        git(self.root, "branch", "-f", "main", "HEAD")           # legacy candidates are on main
        found = [s for s, _ in approvals.unsigned_approvals(self.root)]
        self.assertIn(sha, found)
        self.assertNotIn(forged, found)                          # --write never legitimises a forged approval

    def test_legacy_write_only_pre_signing_on_main(self):
        cfg = self.root / ".aiops" / "config.json"
        legacy = self.root / ".aiops" / "config" / "legacy-approvals"
        cfg.write_text('{"require_signed_approvals": false, "approval_key_policy": "any"}')
        self.write("intent", INTENT)
        self.approve("intent")                                   # unsigned, on the feature branch only
        intent_sha = git(self.root, "log", "-1", "--format=%H")
        self.assertEqual(approvals.unsigned_approvals(self.root), [])
        git(self.root, "switch", "-q", "main")
        git(self.root, "merge", "-q", "--ff-only", "feat/0001-csv-export")
        self.assertEqual([s for s, _ in approvals.unsigned_approvals(self.root)], [intent_sha])
        git(self.root, "add", ".aiops/config/allowed-signers")
        git(self.root, "commit", "-qm", "chore(aiops): approver keys")      # signing is introduced here
        self.write("spec", SPEC)
        self.approve("spec")                                     # unsigned, but after signing was introduced
        found = [s for s, _ in approvals.unsigned_approvals(self.root)]
        self.assertEqual(found, [intent_sha])
        # --write confirms each entry; --yes skips the question
        r = self.run_sdlc("legacy-approvals", "--write", stdin="n\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(legacy.is_file() and intent_sha in legacy.read_text())
        r = self.run_sdlc("legacy-approvals", "--write", stdin="y\n")
        self.assertIn(intent_sha, legacy.read_text())
        legacy.unlink()
        r = self.run_sdlc("legacy-approvals", "--write", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(intent_sha, legacy.read_text())

    def test_sk_key_without_touch_rejected(self):
        from sdlc_engine import approvals as ap
        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "human"}')
        blob = "AAAAGnNrLXNzaC1lZDI1NTE5QG9wZW5zc2guY29t"
        sk = self.root / "sk.pub"
        sk.write_text(f"sk-ssh-ed25519@openssh.com {blob} owner\n")
        git(self.root, "config", "--global", "user.signingkey", str(sk))
        self.signers.write_text(f'owner@example.com namespaces="git" sk-ssh-ed25519@openssh.com {blob}\n')
        self.assertIsNone(ap.signing_problem(self.root))
        self.signers.write_text(f'owner@example.com namespaces="git",no-touch-required sk-ssh-ed25519@openssh.com {blob}\n')
        problem = ap.signing_problem(self.root)
        self.assertTrue(problem and "no-touch-required" in problem, problem)

    def test_audit_fails_closed_on_unresolvable_base(self):
        self.write("intent", INTENT)
        self.approve("intent")
        for base in ("does-not-exist", "0" * 40):
            errors = approvals.audit(self.root, self.d, "intent", base=base, warnings=[])
            self.assertTrue(errors and "does not resolve" in errors[0], (base, errors))

    def test_audit_accepts_allow_listed_signer_against_base(self):
        git(self.root, "add", ".aiops/config/allowed-signers")
        git(self.root, "commit", "-qm", "signers")
        git(self.root, "branch", "base")
        self.write("intent", INTENT)
        self.approve("intent")                                   # signed by the owner key, which the base lists
        self.signers.write_text("")                              # the PR even empties its own list
        warnings = []
        self.assertEqual(approvals.audit(self.root, self.d, "intent", base="base", warnings=warnings), [])
        self.assertEqual(warnings, [])

    def test_audit_bootstraps_when_base_has_no_signer_list(self):
        git(self.root, "branch", "base")                       # base predates allowed-signers
        self.write("intent", INTENT)
        self.approve("intent")
        warnings = []
        self.assertEqual(approvals.audit(self.root, self.d, "intent", base="base", warnings=warnings), [])
        self.assertTrue(warnings and "bootstrap" in warnings[0], warnings)

    def test_closed_intent(self):
        self.write("intent", INTENT.replace("status: Draft", "status: Closed"))
        self.assertEqual(evaluate(self.root, self.d).state, 0)


if __name__ == "__main__":
    unittest.main()
