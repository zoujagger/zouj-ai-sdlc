"""`sdlc` CLI: init (non-destructive scaffold), new/draft/use/status/validate, lock/unlock."""
import json
import shutil
import unittest
from pathlib import Path

from helpers import INTENT, RepoCase, git


class Init(RepoCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")

    def test_scaffolds_without_overwriting(self):
        (self.root / "Makefile").write_text("mine:\n\techo keep\n")
        r = self.run_sdlc("init")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.root / "Makefile").read_text(), "mine:\n\techo keep\n")
        self.assertIn("Kept existing", r.stdout)
        for rel in (".aiops/README.md", ".aiops/config.json", ".aiops/state", "REVIEW.md", "CLAUDE.md",
                    ".github/workflows/aiops-gates.yml", "ops/bands.yaml"):
            self.assertTrue((self.root / rel).exists(), rel)
        self.assertIn(".aiops/state/", (self.root / ".gitignore").read_text())
        self.assertEqual(self.run_sdlc("init").returncode, 0)   # idempotent
        self.assertEqual((self.root / ".gitignore").read_text().count(".aiops/state/"), 1)

    def test_stack_preset_wires_the_makefile(self):
        r = self.run_sdlc("init", "--stack", "python")
        self.assertIn("wired format, lint, typecheck, test, build", r.stdout)
        self.assertIn("pytest -q", (self.root / "Makefile").read_text())

    def test_agent_init_force_keeps_human_owned_files(self):
        from helpers import ROOT
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        owned = {".aiops/config.json": '{"profile": "strict", "approval_key_policy": "sk", "main_branch": "trunk"}\n',
                 ".aiops/config/allowed-signers": "owner@example.com namespaces=\"git\" ssh-ed25519 AAAAkey\n",
                 ".claude/settings.json": '{"permissions": {"deny": ["Read(./x)"]}}\n',
                 ".github/CODEOWNERS": "/.aiops/ @owner\n",
                 ".github/workflows/aiops-gates.yml": "# customised\n"}
        for rel, text in owned.items():
            (self.root / rel).write_text(text)
        (self.root / "docs" / "ai-usage-policy.md").write_text("mine\n")          # a doc the agent may write
        r = self.run_sdlc("init", "--force", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        for rel, text in owned.items():
            self.assertEqual((self.root / rel).read_text(), text, rel)           # untouched under the agent
            self.assertIn(rel, r.stdout)                                          # listed for the human
        self.assertIn("your own terminal", r.stdout)
        self.assertNotEqual((self.root / "docs" / "ai-usage-policy.md").read_text(), "mine\n")   # the rest is reset
        r = self.run_sdlc("init", "--force")                                      # a human: as before
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("strict", (self.root / ".aiops" / "config.json").read_text())
        # nothing tells the agent to run --force: doctor's Makefile fix and the docs
        (self.root / "Makefile").write_text('test:\n\t@echo "[test] not configured - edit Makefile"\n')
        self.assertNotIn("--force", self.run_sdlc("doctor").stdout)
        self.assertNotIn("--force", (ROOT / "TROUBLESHOOTING.md").read_text())

    def test_agent_init_force_never_writes_what_the_guard_blocks(self):
        """Review 0003 round 6 MEDIUM: under the agent, --force writes no more than the agent's own Write could."""
        self.assertEqual(self.run_sdlc("init", "--stack", "python").returncode, 0)
        extra = self.root / ".aiops" / "config" / "protected-paths"
        extra.write_text(extra.read_text() + "Makefile the wired contract is human-owned here\n")
        kept = {"Makefile": (self.root / "Makefile").read_text(),                 # repo-protected, wired
                "governance/managed-settings.example.json": '{"mine": true}\n',  # default protected-paths
                "CLAUDE.md": "mine\n",                                           # read-only lock (no intent)
                "scripts/check-bands.py": "# mine\n"}                             # code under the lock
        for rel, text in kept.items():
            (self.root / rel).write_text(text)
        r = self.run_sdlc("init", "--force", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        for rel, text in kept.items():
            self.assertEqual((self.root / rel).read_text(), text, rel)
            self.assertIn(rel, r.stdout)                                          # listed for the human
        self.assertIn("pytest -q", (self.root / "Makefile").read_text())         # still wired: make check is real

    def test_agent_init_force_keeps_protected_paths_when_unlocked(self):
        """Review 0003 round 7 MEDIUM: protected paths are kept by their own rule, not only through the lock."""
        self.assertEqual(self.run_sdlc("init", "--stack", "python").returncode, 0)
        cfg = self.root / ".aiops" / "config.json"
        cfg.write_text(json.dumps({**json.loads(cfg.read_text()), "lock_when_idle": False}) + "\n")   # code unlocked
        extra = self.root / ".aiops" / "config" / "protected-paths"
        extra.write_text(extra.read_text() + "Makefile the wired contract is human-owned here\n")
        kept = {"Makefile": (self.root / "Makefile").read_text(),
                "governance/managed-settings.example.json": '{"mine": true}\n'}
        for rel, text in kept.items():
            (self.root / rel).write_text(text)
        (self.root / "CLAUDE.md").write_text("mine\n")                           # unlocked, unprotected: reset
        r = self.run_sdlc("init", "--force", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        for rel, text in kept.items():
            self.assertEqual((self.root / rel).read_text(), text, rel)
            self.assertIn(rel, r.stdout)
        self.assertNotEqual((self.root / "CLAUDE.md").read_text(), "mine\n")

    def test_scaffold_offers_the_plugin(self):
        before = json.loads((Path(__file__).resolve().parents[1] / "templates" / "scaffold" / ".claude" /
                             "settings.json").read_text())["permissions"]["deny"]
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        settings = json.loads((self.root / ".claude" / "settings.json").read_text())
        from helpers import ROOT
        version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
        self.assertEqual(settings["extraKnownMarketplaces"]["zouj"]["source"],      # pinned to this release
                         {"source": "github", "repo": "zoujagger/zouj-ai-sdlc", "ref": f"v{version}"})
        self.assertIs(settings["enabledPlugins"]["zouj-ai-sdlc@zouj"], True)
        self.assertEqual(settings["permissions"]["deny"], before)                # deny rules unchanged
        readme, security = (ROOT / "README.md").read_text(), (ROOT / "SECURITY.md").read_text()
        self.assertIn(f"/plugin marketplace add zoujagger/zouj-ai-sdlc@v{version}", readme)
        self.assertIn(f'"ref": "v{version}"', readme)
        for doc in (readme, security):                                            # the trust model, stated
            self.assertIn("trusts github.com/zoujagger/zouj-ai-sdlc at that ref", doc)
        self.assertNotIn("allow", settings["permissions"])                        # no permission is granted

    def test_scaffold_pins_and_protects(self):
        from helpers import ROOT
        version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        settings = json.loads((self.root / ".claude" / "settings.json").read_text())
        self.assertIn("Read(./.env)", settings["permissions"]["deny"])
        self.assertIn("Read(./**/*.pem)", settings["permissions"]["deny"])
        gates = (self.root / ".github" / "workflows" / "aiops-gates.yml").read_text()
        self.assertIn(f"ZOUJ_SDLC_REF: v{version}", gates)
        self.assertIn("--base", gates)
        for wf in sorted((self.root / ".github" / "workflows").glob("claude*.yml")):
            text = wf.read_text()
            self.assertIn(f"ZOUJ_SDLC_REF: v{version}", text, wf.name)
            self.assertIn("--plugin-dir", text, wf.name)
            self.assertNotIn("plugin_marketplaces", text, wf.name)
        leftovers = [p for p in self.root.rglob("*") if p.is_file() and ".git/" not in str(p)
                     and "__ZOUJ_SDLC_REF__" in p.read_text(errors="replace")]
        self.assertEqual(leftovers, [])
        cfg = json.loads((self.root / ".aiops" / "config.json").read_text())
        self.assertIs(cfg["require_signed_approvals"], True)
        for name in ("allowed-signers", "legacy-approvals"):
            self.assertTrue((self.root / ".aiops" / "config" / name).is_file(), name)
        owners = (self.root / ".github" / "CODEOWNERS").read_text()
        self.assertRegex(owners, r"/\.aiops/config\.json\s+@your-org/maintainers")
        self.assertRegex(owners, r"(?m)^/\.github/\s+@")
        self.assertRegex(owners, r"(?m)^/\.claude/\s+@")

    def test_unknown_stack_fails(self):
        self.assertEqual(self.run_sdlc("init", "--stack", "cobol").returncode, 1)

    def test_scaffold_gate_verifies_base(self):
        self.assertEqual(self.run_sdlc("init").returncode, 0)
        gates = (self.root / ".github" / "workflows" / "aiops-gates.yml").read_text()
        self.assertIn('git rev-parse -q --verify "${BASE_SHA}^{commit}"', gates)
        self.assertIn("exit 1", gates)


class Lifecycle(RepoCase):
    def test_prompt_approval_explains_terminal_fallback(self):
        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "human"}')
        self.write("intent", INTENT)
        payload = json.dumps({"prompt": "Intent Approved 0001", "cwd": str(self.root),
                              "hook_event_name": "UserPromptSubmit"})
        r = self.run_sdlc("hook", "prompt", stdin=payload, env={"CLAUDECODE": "1"})
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("NOT opened", ctx)
        self.assertIn("/bin/sdlc approve 0001 intent`", ctx)      # the exact command for the human's terminal

    def test_validate_rejects_empty_base(self):
        self.write("intent", INTENT)
        for args in (["--base", ""], ["--base"]):
            r = self.run_sdlc("validate", "--all", "--ci", *args)
            self.assertEqual(r.returncode, 1, (args, r.stdout, r.stderr))
            self.assertIn("--base", r.stdout + r.stderr)

    def test_legacy_approvals_is_human_only(self):
        from helpers import git
        cfg = self.root / ".aiops" / "config.json"
        cfg.write_text('{"require_signed_approvals": false}')
        self.write("intent", INTENT)
        self.approve("intent")                               # unsigned, before signing is introduced
        sha = git(self.root, "log", "-1", "--format=%H")
        git(self.root, "add", ".aiops/config/allowed-signers")
        git(self.root, "commit", "-qm", "signers")
        git(self.root, "branch", "base")                     # base: has a signer list, no legacy list
        git(self.root, "branch", "-f", "main", "HEAD")
        cfg.write_text('{"require_signed_approvals": true}')
        self.assertEqual(self.run_sdlc("validate", "--all", "--ci").returncode, 1)
        self.assertEqual(self.run_sdlc("legacy-approvals", "--write", "--yes", env={"CLAUDECODE": "1"}).returncode, 1)
        r = self.run_sdlc("legacy-approvals", "--write", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(sha, (self.root / ".aiops" / "config" / "legacy-approvals").read_text())
        self.assertEqual(self.run_sdlc("validate", "--all", "--ci").returncode, 0)
        r = self.run_sdlc("validate", "--all", "--ci", "--base", "base")
        self.assertEqual(r.returncode, 1, r.stdout)          # the base has no legacy list yet

    def test_strict_requires_codeowners(self):
        cfg = self.root / ".aiops" / "config.json"
        owners = self.root / ".github" / "CODEOWNERS"
        owners.parent.mkdir(parents=True, exist_ok=True)
        owners.write_text("/src/ @someone\n")                          # doesn't cover /.aiops/
        cfg.write_text('{"profile": "strict", "require_signed_approvals": false}')
        r = self.run_sdlc("doctor")
        self.assertIn("✗ CODEOWNERS covers /.aiops/", r.stdout)
        self.assertIn("/.aiops/ @", r.stdout)                            # the fix names the line to add
        self.assertEqual(r.returncode, 1)
        cfg.write_text('{"profile": "team", "require_signed_approvals": false}')
        r = self.run_sdlc("doctor")
        self.assertIn("! CODEOWNERS covers /.aiops/", r.stdout)         # team: a warning only
        self.assertEqual(r.returncode, 0, r.stdout)
        owners.write_text("/.aiops/ @owner\n")
        cfg.write_text('{"profile": "strict", "require_signed_approvals": false}')
        r = self.run_sdlc("doctor")
        self.assertIn("✓ CODEOWNERS covers /.aiops/", r.stdout)
        self.assertEqual(r.returncode, 0, r.stdout)
        owners.write_text("/.aiops/\n")                                 # a pattern without an owner covers nothing
        self.assertEqual(self.run_sdlc("doctor").returncode, 1)
        owners.write_text("/.aiops/ @your-org/product\n")              # the scaffold's placeholder isn't an owner
        self.assertEqual(self.run_sdlc("doctor").returncode, 1)
        # profile and key policy hand-edited to disagree: the CODEOWNERS row still appears exactly once
        for conf in ('{"profile": "team", "approval_key_policy": "sk", "require_signed_approvals": false}',
                     '{"profile": "strict", "approval_key_policy": "human", "require_signed_approvals": false}'):
            cfg.write_text(conf)
            self.assertEqual(self.run_sdlc("doctor").stdout.count("CODEOWNERS covers /.aiops/"), 1, conf)

    def test_doctor_checks_signing(self):
        from helpers import git
        out = self.run_sdlc("doctor").stdout
        self.assertIn("✓ approval signing configured (ssh)", out)
        self.assertIn("✓ signing key is in .aiops/config/allowed-signers", out)
        self.assertIn("! signing key has no passphrase", out)        # policy "any" (fixtures): warn, don't fail
        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "human"}')
        r = self.run_sdlc("doctor")                                   # the default policy: the same key fails
        self.assertIn("✗ approval signing: the signing key has no passphrase", r.stdout)
        self.assertEqual(r.returncode, 1)
        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "any"}')
        for key, value in (("gpg.format", "openpgp"), ("core.fsmonitor", "/tmp/x.sh")):   # repo-local overrides
            git(self.root, "config", "--local", key, value)
            r = self.run_sdlc("doctor")
            self.assertIn(f"✗ approval signing: repo-local git config sets {key}", r.stdout)
            self.assertEqual(r.returncode, 1)
            git(self.root, "config", "--local", "--unset", key)
        git(self.root, "config", "--global", "--unset", "user.signingkey")
        r = self.run_sdlc("doctor")
        self.assertIn("✗ approval signing", r.stdout)
        self.assertEqual(r.returncode, 1)

    def test_new_draft_status_validate(self):
        shutil.rmtree(self.d)
        r = self.run_sdlc("new", "csv-export", "--title", "CSV export")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("feat/0001-csv-export", r.stdout)
        self.assertTrue((self.d / "intent.md").is_file())
        self.assertEqual(self.run_sdlc("draft", "0001", "spec").returncode, 1)     # intent not approved
        st = json.loads(self.run_sdlc("status", "--json").stdout)
        self.assertEqual((st["state"], st["waiting_on"]), (1, "human"))
        self.assertEqual(self.run_sdlc("validate").returncode, 0)                   # template is structurally valid
        self.write("intent", INTENT)
        self.assertEqual(self.run_sdlc("approve", "1", "intent").returncode, 0)
        self.assertEqual(self.run_sdlc("draft", "0001", "spec").returncode, 0)
        self.assertIn("2 SPECIFICATION", self.run_sdlc("status").stdout)

    def test_status_table_without_active_intent(self):
        self.write("intent", INTENT)
        self.run_sdlc("new", "other")
        (self.root / ".aiops" / "state" / "active").unlink()
        from helpers import git
        git(self.root, "switch", "-qc", "chore/x")
        out = self.run_sdlc("status").stdout
        self.assertIn("| 0001-csv-export | 1 BRAINSTORMING", out)
        self.assertIn("| 0002-other |", out)

    def test_validate_ci_fails_on_agent_authored_approval(self):
        from helpers import git
        from sdlc_engine import artifacts as A
        self.write("intent", INTENT)
        text = (self.d / "intent.md").read_text()
        (self.d / "intent.md").write_text(A.set_fields(text, {
            "status": "Approved", "approved-by": "bot", "approved-sha256": A.approval_hash("intent", text)}))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "intent", "-m", "Co-Authored-By: Claude <noreply@anthropic.com>")
        self.assertEqual(self.run_sdlc("validate", "--all").returncode, 0)
        r = self.run_sdlc("validate", "--all", "--ci")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not an approval commit", r.stdout)

    def test_lock_is_agent_settable_but_only_human_releasable(self):
        self.assertEqual(self.run_sdlc("lock", env={"CLAUDECODE": "1"}).returncode, 0)
        self.assertTrue((self.root / ".aiops" / "state" / "test-lock").exists())
        self.assertEqual(self.run_sdlc("unlock", env={"CLAUDECODE": "1"}).returncode, 1)
        self.assertEqual(self.run_sdlc("unlock").returncode, 0)
        self.assertFalse((self.root / ".aiops" / "state" / "test-lock").exists())


class Allowances(RepoCase):
    """doctor and `validate --ci` report allowed-commands entries the hooks ignore (0004 S7)."""
    def allow(self, text):
        (self.root / ".aiops" / "config" / "allowed-commands").write_text(text)

    def test_doctor_flags_gate_entry(self):
        self.allow("G-ENV-03 ls env\n")
        self.assertNotIn("allowed-commands", self.run_sdlc("doctor").stdout.replace("allowed-commands: ok", ""))
        self.allow("G-ENV-03 ls env\nG-MERGE-03 git push origin main\n")
        r = self.run_sdlc("doctor")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertRegex(r.stdout, r"✗ \.aiops/config/allowed-commands line 2: G-MERGE-03 is a gate rule")

    def test_validate_ci_fails_on_base_entry(self):
        self.allow("G-SEC-06 cat .env\n")
        git(self.root, "add", ".aiops/config/allowed-commands")
        git(self.root, "commit", "-qm", "allowance")
        self.allow("G-ENV-03 ls env\n")                       # the PR's own copy is fine; the base's is not
        r = self.run_sdlc("validate", "--ci", "--base", "HEAD")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("G-SEC-06 is a secret rule", r.stdout)
        self.assertIn("HEAD:.aiops/config/allowed-commands", r.stdout)

    def test_validate_ci_fails_on_the_prs_own_entry(self):
        self.allow("G-ENV-03 ls env\nG-BASH-02 rm -rf /\n")
        r = self.run_sdlc("validate", "--ci", "--base", "main")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("G-BASH-02 is a safety rule", r.stdout)

    def test_valid_entries_pass(self):
        self.allow("# human-owned\nG-ENV-03 ls env\nG-BASH-07 sudo systemctl status docker\n")
        r = self.run_sdlc("validate", "--ci", "--base", "main")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
