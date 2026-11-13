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
        r = self.run_sdlc("init", "--with", "all")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.root / "Makefile").read_text(), "mine:\n\techo keep\n")
        self.assertIn("Kept existing", r.stdout)
        for rel in (
            ".aiops/README.md",
            ".aiops/config.json",
            ".aiops/state",
            "REVIEW.md",
            "CLAUDE.md",
            ".github/workflows/aiops-gates.yml",
            "ops/bands.yaml",
        ):
            self.assertTrue((self.root / rel).exists(), rel)
        self.assertIn(".aiops/state/", (self.root / ".gitignore").read_text())
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)  # idempotent
        self.assertEqual((self.root / ".gitignore").read_text().count(".aiops/state/"), 1)

    def test_stack_preset_wires_the_makefile(self):
        r = self.run_sdlc("init", "--with", "all", "--stack", "python")
        self.assertIn("wired format, lint, typecheck, test, build", r.stdout)
        self.assertIn("pytest -q", (self.root / "Makefile").read_text())

    def test_agent_init_force_keeps_human_owned_files(self):
        from helpers import ROOT

        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
        owned = {
            ".aiops/config.json": '{"profile": "strict", "approval_key_policy": "sk", "main_branch": "trunk"}\n',
            ".aiops/config/allowed-signers": 'owner@example.com namespaces="git" ssh-ed25519 AAAAkey\n',
            ".claude/settings.json": '{"permissions": {"deny": ["Read(./x)"]}}\n',
            ".github/CODEOWNERS": "/.aiops/ @owner\n",
            ".github/workflows/aiops-gates.yml": "# customised\n",
        }
        for rel, text in owned.items():
            (self.root / rel).write_text(text)
        (self.root / "docs" / "ai-usage-policy.md").write_text("mine\n")  # a doc the agent may write
        r = self.run_sdlc("init", "--with", "all", "--force", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        for rel, text in owned.items():
            self.assertEqual((self.root / rel).read_text(), text, rel)  # untouched under the agent
            self.assertIn(rel, r.stdout)  # listed for the human
        self.assertIn("your own terminal", r.stdout)
        self.assertNotEqual((self.root / "docs" / "ai-usage-policy.md").read_text(), "mine\n")  # the rest is reset
        r = self.run_sdlc("init", "--with", "all", "--force")  # a human: as before
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("strict", (self.root / ".aiops" / "config.json").read_text())
        # nothing tells the agent to run --force: doctor's Makefile fix and the docs
        (self.root / "Makefile").write_text('test:\n\t@echo "[test] not configured - edit Makefile"\n')
        self.assertNotIn("--force", self.run_sdlc("doctor").stdout)
        self.assertNotIn("--force", (ROOT / "TROUBLESHOOTING.md").read_text())

    def test_agent_init_force_never_writes_what_the_guard_blocks(self):
        """Review 0003 round 6 MEDIUM: under the agent, --force writes no more than the agent's own Write could."""
        self.assertEqual(self.run_sdlc("init", "--with", "all", "--stack", "python").returncode, 0)
        extra = self.root / ".aiops" / "config" / "protected-paths"
        extra.write_text(extra.read_text() + "Makefile the wired contract is human-owned here\n")
        kept = {
            "Makefile": (self.root / "Makefile").read_text(),  # repo-protected, wired
            "governance/managed-settings.example.json": '{"mine": true}\n',  # default protected-paths
            "CLAUDE.md": "mine\n",  # read-only lock (no intent)
            "scripts/check-bands.py": "# mine\n",
        }  # code under the lock
        for rel, text in kept.items():
            (self.root / rel).write_text(text)
        r = self.run_sdlc("init", "--with", "all", "--force", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        for rel, text in kept.items():
            self.assertEqual((self.root / rel).read_text(), text, rel)
            self.assertIn(rel, r.stdout)  # listed for the human
        self.assertIn("pytest -q", (self.root / "Makefile").read_text())  # still wired: make check is real

    def test_agent_init_force_keeps_protected_paths_when_unlocked(self):
        """Review 0003 round 7 MEDIUM: protected paths are kept by their own rule, not only through the lock."""
        self.assertEqual(self.run_sdlc("init", "--with", "all", "--stack", "python").returncode, 0)
        cfg = self.root / ".aiops" / "config.json"
        cfg.write_text(json.dumps({**json.loads(cfg.read_text()), "lock_when_idle": False}) + "\n")  # code unlocked
        extra = self.root / ".aiops" / "config" / "protected-paths"
        extra.write_text(extra.read_text() + "Makefile the wired contract is human-owned here\n")
        kept = {
            "Makefile": (self.root / "Makefile").read_text(),
            "governance/managed-settings.example.json": '{"mine": true}\n',
        }
        for rel, text in kept.items():
            (self.root / rel).write_text(text)
        (self.root / "CLAUDE.md").write_text("mine\n")  # unlocked, unprotected: reset
        r = self.run_sdlc("init", "--with", "all", "--force", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        for rel, text in kept.items():
            self.assertEqual((self.root / rel).read_text(), text, rel)
            self.assertIn(rel, r.stdout)
        self.assertNotEqual((self.root / "CLAUDE.md").read_text(), "mine\n")

    def test_scaffold_offers_the_plugin(self):
        before = json.loads(
            (Path(__file__).resolve().parents[1] / "templates" / "scaffold" / ".claude" / "settings.json").read_text()
        )["permissions"]["deny"]
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
        settings = json.loads((self.root / ".claude" / "settings.json").read_text())
        from helpers import ROOT

        version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
        self.assertEqual(
            settings["extraKnownMarketplaces"]["zouj"]["source"],  # pinned to this release
            {"source": "github", "repo": "zoujagger/zouj-ai-sdlc", "ref": f"v{version}"},
        )
        self.assertIs(settings["enabledPlugins"]["zouj-ai-sdlc@zouj"], True)
        self.assertEqual(settings["permissions"]["deny"], before)  # deny rules unchanged
        readme, security = (ROOT / "README.md").read_text(), (ROOT / "SECURITY.md").read_text()
        self.assertIn(f"/plugin marketplace add zoujagger/zouj-ai-sdlc@v{version}", readme)
        self.assertIn(f'"ref": "v{version}"', readme)
        for doc in (readme, security):  # the trust model, stated
            self.assertIn("trusts github.com/zoujagger/zouj-ai-sdlc at that ref", doc)
        self.assertNotIn("allow", settings["permissions"])  # no permission is granted

    def test_scaffold_pins_and_protects(self):
        from helpers import ROOT

        version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
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
        leftovers = [
            p
            for p in self.root.rglob("*")
            if p.is_file() and ".git/" not in str(p) and "__ZOUJ_SDLC_REF__" in p.read_text(errors="replace")
        ]
        self.assertEqual(leftovers, [])
        cfg = json.loads((self.root / ".aiops" / "config.json").read_text())
        self.assertIs(cfg["require_signed_approvals"], True)
        for name in ("allowed-signers", "legacy-approvals"):
            self.assertTrue((self.root / ".aiops" / "config" / name).is_file(), name)
        owners = (self.root / ".github" / "CODEOWNERS").read_text()
        self.assertRegex(owners, r"/\.aiops/config\.json\s+@your-org/maintainers")
        self.assertRegex(owners, r"(?m)^/\.github/\s+@")
        self.assertRegex(owners, r"(?m)^/\.claude/\s+@")

    def test_agent_force_ignores_lock_env(self):
        """0005 S3 (gap 5): an inline SDLC_HOOK_PROFILE / AIOPS_INTENT can't lift the lock for the agent's --force."""
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
        mk = self.root / "Makefile"
        mk.write_text(mk.read_text() + "# ours\n")  # no active intent: code is locked
        for env in ({"SDLC_HOOK_PROFILE": "spike"}, {"AIOPS_INTENT": "0009"}):
            r = self.run_sdlc("init", "--with", "all", "--force", env={"CLAUDECODE": "1", **env})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(mk.read_text().endswith("# ours\n"), env)
            self.assertIn("Makefile", r.stdout)

    def test_unknown_stack_fails(self):
        self.assertEqual(self.run_sdlc("init", "--with", "all", "--stack", "cobol").returncode, 1)

    def test_scaffold_gate_verifies_base(self):
        self.assertEqual(self.run_sdlc("init", "--with", "all").returncode, 0)
        gates = (self.root / ".github" / "workflows" / "aiops-gates.yml").read_text()
        self.assertIn('git rev-parse -q --verify "${BASE_SHA}^{commit}"', gates)
        self.assertIn("exit 1", gates)


class Lifecycle(RepoCase):
    def test_prompt_approval_explains_terminal_fallback(self):
        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "human"}')
        self.write("intent", INTENT)
        payload = json.dumps(
            {"prompt": "Intent Approved 0001", "cwd": str(self.root), "hook_event_name": "UserPromptSubmit"}
        )
        r = self.run_sdlc("hook", "prompt", stdin=payload, env={"CLAUDECODE": "1"})
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("NOT opened", ctx)
        self.assertIn("/bin/sdlc approve 0001 intent`", ctx)  # the exact command for the human's terminal

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
        self.approve("intent")  # unsigned, before signing is introduced
        sha = git(self.root, "log", "-1", "--format=%H")
        git(self.root, "add", ".aiops/config/allowed-signers")
        git(self.root, "commit", "-qm", "signers")
        git(self.root, "branch", "base")  # base: has a signer list, no legacy list
        git(self.root, "branch", "-f", "main", "HEAD")
        cfg.write_text('{"require_signed_approvals": true}')
        self.assertEqual(self.run_sdlc("validate", "--all", "--ci").returncode, 1)
        self.assertEqual(self.run_sdlc("legacy-approvals", "--write", "--yes", env={"CLAUDECODE": "1"}).returncode, 1)
        r = self.run_sdlc("legacy-approvals", "--write", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(sha, (self.root / ".aiops" / "config" / "legacy-approvals").read_text())
        self.assertEqual(self.run_sdlc("validate", "--all", "--ci").returncode, 0)
        r = self.run_sdlc("validate", "--all", "--ci", "--base", "base")
        self.assertEqual(r.returncode, 1, r.stdout)  # the base has no legacy list yet

    def test_strict_requires_codeowners(self):
        cfg = self.root / ".aiops" / "config.json"
        owners = self.root / ".github" / "CODEOWNERS"
        owners.parent.mkdir(parents=True, exist_ok=True)
        owners.write_text("/src/ @someone\n")  # doesn't cover /.aiops/
        cfg.write_text('{"profile": "strict", "require_signed_approvals": false}')
        r = self.run_sdlc("doctor")
        self.assertIn("✗ CODEOWNERS covers /.aiops/", r.stdout)
        self.assertIn("/.aiops/ @", r.stdout)  # the fix names the line to add
        self.assertEqual(r.returncode, 1)
        cfg.write_text('{"profile": "team", "require_signed_approvals": false}')
        r = self.run_sdlc("doctor")
        self.assertIn("! CODEOWNERS covers /.aiops/", r.stdout)  # team: a warning only
        self.assertEqual(r.returncode, 0, r.stdout)
        owners.write_text("/.aiops/ @owner\n")
        cfg.write_text('{"profile": "strict", "require_signed_approvals": false}')
        r = self.run_sdlc("doctor")
        self.assertIn("✓ CODEOWNERS covers /.aiops/", r.stdout)
        self.assertEqual(r.returncode, 0, r.stdout)
        owners.write_text("/.aiops/\n")  # a pattern without an owner covers nothing
        self.assertEqual(self.run_sdlc("doctor").returncode, 1)
        owners.write_text("/.aiops/ @your-org/product\n")  # the scaffold's placeholder isn't an owner
        self.assertEqual(self.run_sdlc("doctor").returncode, 1)
        # profile and key policy hand-edited to disagree: the CODEOWNERS row still appears exactly once
        for conf in (
            '{"profile": "team", "approval_key_policy": "sk", "require_signed_approvals": false}',
            '{"profile": "strict", "approval_key_policy": "human", "require_signed_approvals": false}',
        ):
            cfg.write_text(conf)
            self.assertEqual(self.run_sdlc("doctor").stdout.count("CODEOWNERS covers /.aiops/"), 1, conf)

    def test_doctor_checks_signing(self):
        from helpers import git

        out = self.run_sdlc("doctor").stdout
        self.assertIn("✓ approval signing configured (ssh)", out)
        self.assertIn("✓ signing key is in .aiops/config/allowed-signers", out)
        self.assertIn("! signing key has no passphrase", out)  # policy "any" (fixtures): warn, don't fail
        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "human"}')
        r = self.run_sdlc("doctor")  # the default policy: the same key fails
        self.assertIn("✗ approval signing: the signing key has no passphrase", r.stdout)
        self.assertEqual(r.returncode, 1)
        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "any"}')
        for key, value in (("gpg.format", "openpgp"), ("core.fsmonitor", "/tmp/x.sh")):  # repo-local overrides
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
        self.assertEqual(self.run_sdlc("draft", "0001", "spec").returncode, 1)  # intent not approved
        st = json.loads(self.run_sdlc("status", "--json").stdout)
        self.assertEqual((st["state"], st["waiting_on"]), (1, "human"))
        self.assertEqual(self.run_sdlc("validate").returncode, 0)  # template is structurally valid
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
        (self.d / "intent.md").write_text(
            A.set_fields(
                text, {"status": "Approved", "approved-by": "bot", "approved-sha256": A.approval_hash("intent", text)}
            )
        )
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
        self.allow("G-ENV-03 ls env\n")  # the PR's own copy is fine; the base's is not
        r = self.run_sdlc("validate", "--ci", "--base", "HEAD")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("G-SEC-06 is a secret rule", r.stdout)
        self.assertIn("HEAD:.aiops/config/allowed-commands", r.stdout)

    def test_validate_ci_fails_on_the_prs_own_entry(self):
        self.allow("G-ENV-03 ls env\nG-BASH-02 rm -rf /\n")
        r = self.run_sdlc("validate", "--ci", "--base", "main")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("G-BASH-02 is a safety rule", r.stdout)

    def test_symlinked_file_is_not_read(self):
        secret = self.root.parent / f"{self.root.name}.secret"
        secret.write_text("G-NOPE-99 top-secret-line\n")
        self.addCleanup(secret.unlink)
        (self.root / ".aiops" / "config" / "allowed-commands").symlink_to(secret)
        for args in (("doctor",), ("validate", "--ci", "--base", "main")):
            r = self.run_sdlc(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertNotIn("top-secret-line", r.stdout + r.stderr, args)
            self.assertNotIn("G-NOPE-99", r.stdout + r.stderr, args)
            self.assertIn("symlink", r.stdout + r.stderr, args)

    def test_valid_entries_pass(self):
        self.allow("# human-owned\nG-ENV-03 ls env\nG-BASH-07 sudo systemctl status docker\n")
        r = self.run_sdlc("validate", "--ci", "--base", "main")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


STATE = ".aiops/install-state.json"


class InitParts(RepoCase):
    """`sdlc init` writes the core scaffold by default; `--with` adds opt-in parts (0007 S2: AC-11, 12, 14, 20)."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")
        from sdlc_engine import lifecycle

        self.lc = lifecycle
        self.base = self.files()

    def files(self):
        return {
            str(p.relative_to(self.root))
            for p in self.root.rglob("*")
            if p.is_file() and p.relative_to(self.root).parts[0] != ".git"
        }

    def part(self, name):
        return {rel for rel in self.lc.scaffold_paths() if self.lc.part_of(rel) == name}

    def parts(self):
        return json.loads((self.root / STATE).read_text()).get("parts")

    def init(self, *args):
        r = self.run_sdlc("init", *args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def test_fresh_init_writes_core(self):
        r = self.init()
        self.assertEqual(self.files() - self.base, self.part("core") | {STATE, ".gitignore"})
        self.assertEqual(len(self.part("core")), 16)
        self.assertEqual(self.parts(), [])
        self.assertIn("--with", r.stdout)  # says how to add the rest
        for name in self.lc.PARTS:
            self.assertIn(name, r.stdout)

    def test_with_adds_only_that_part(self):
        self.init()
        before = self.files()
        self.init("--with", "maintain")
        self.assertEqual(self.files() - before, self.part("maintain"))
        self.assertEqual(len(self.part("maintain")), 7)
        self.assertEqual(self.parts(), ["maintain"])
        self.init("--with", "review,deploy")
        self.assertEqual(self.parts(), ["deploy", "maintain", "review"])  # --with only adds

    def test_with_all(self):
        self.init("--with", "all")
        self.assertEqual(self.files() - self.base, set(self.lc.scaffold_paths()) | {STATE, ".gitignore"})
        self.assertEqual(self.parts(), sorted(self.lc.PARTS))

    def test_unknown_part_refused_before_writing(self):
        for value in ("bogus", "maintain,bogus", "core"):
            r = self.run_sdlc("init", "--with", value)
            self.assertEqual(r.returncode, 1, value)
            for name in self.lc.PARTS:
                self.assertIn(name, r.stderr)
            self.assertEqual(self.files(), self.base, value)  # nothing written
        r = self.run_sdlc("init", "--with")  # no value
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.files(), self.base)

    def test_rerun_without_with_keeps_parts(self):
        self.init("--with", "maintain")
        before = self.files()
        self.init()
        self.assertEqual(self.files(), before)  # adds nothing, removes nothing
        self.assertEqual(self.parts(), ["maintain"])

    def test_edited_config_without_state_gets_every_part(self):
        (self.root / ".aiops").mkdir()  # initialized before install-state
        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "any"}')
        self.init()
        self.assertTrue(set(self.lc.scaffold_paths()) <= self.files())
        self.assertEqual(self.parts(), sorted(self.lc.PARTS))

    def test_template_config_with_full_scaffold_gets_every_part(self):
        self.init("--with", "all")
        (self.root / STATE).unlink()  # as 0.2.0-alpha.2 left it
        (self.root / "ops" / "bands.yaml").unlink()
        (self.root / ".github" / "workflows" / "deploy.yml").unlink()
        self.init()
        self.assertTrue(set(self.lc.scaffold_paths()) <= self.files())  # both restored: every part counts
        self.assertEqual(self.parts(), sorted(self.lc.PARTS))

    def test_rerun_after_partial_core_setup_stays_core(self):
        self.init()
        (self.root / STATE).unlink()  # the first run stopped part-way
        for rel in ("CLAUDE.md", "REVIEW.md", ".github/workflows/ci.yml"):
            (self.root / rel).unlink()
        before = self.files()
        self.init()
        self.assertEqual(self.files() - before, {"CLAUDE.md", "REVIEW.md", ".github/workflows/ci.yml", STATE})
        self.assertEqual(self.parts(), [])
        shutil.rmtree(self.root / ".aiops")  # it stopped before config.json
        (self.root / ".aiops").mkdir()
        (self.root / ".aiops" / "README.md").write_text("x\n")
        self.init()
        self.assertEqual(self.parts(), [])

    def test_rerun_after_partial_with_maintain_completes_it(self):
        self.init("--with", "maintain")
        (self.root / STATE).unlink()
        for rel in ("CLAUDE.md", "ops/bands.yaml"):
            (self.root / rel).unlink()
        before = self.files()
        self.init()
        self.assertEqual(self.files() - before, {"CLAUDE.md", "ops/bands.yaml", STATE})
        self.assertEqual(self.parts(), ["maintain"])

    def test_the_users_own_files_do_not_count_as_a_part(self):
        (self.root / ".github").mkdir()
        (self.root / ".github" / "dependabot.yml").write_text("version: 2\nupdates: []\n")  # theirs, not the scaffold's
        (self.root / "docs" / "adr").mkdir(parents=True)
        (self.root / "docs" / "adr" / "0001-record-architecture-decisions.md").write_text("# ours\n")
        self.init()
        self.assertFalse((self.root / "docs" / "ai-usage-policy.md").exists())  # governance was not inferred
        self.assertEqual(self.parts(), [])


CONFIG = ".aiops/config.json"


class ProfilePhrase(RepoCase):
    """The human types `Setup Profile <name>` as the whole prompt; the prompt hook sets the repo's first profile
    (0007 S6: AC-1, AC-4, AC-5, AC-6, AC-7)."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.run_sdlc("init", env={"CLAUDECODE": "1"}).returncode, 0)  # the agent scaffolds
        self.before = (self.root / CONFIG).read_bytes()  # the template: no profile yet

    def prompt(self, text, env=None):
        payload = {"prompt": text, "cwd": str(self.root), "hook_event_name": "UserPromptSubmit"}
        r = self.hook("prompt", payload, env={"CLAUDECODE": "1", **(env or {})})  # hooks always run with the marker
        self.assertEqual(r.returncode, 0, r.stderr)  # a prompt hook never blocks
        return r.stdout

    def context(self, text, env=None):
        return json.loads(self.prompt(text, env))["hookSpecificOutput"]["additionalContext"]

    def profile(self):
        return json.loads((self.root / CONFIG).read_text()).get("profile")

    def test_whole_prompt_sets_the_profile(self):
        head = git(self.root, "rev-parse", "HEAD")
        ctx = self.context("Setup Profile solo")
        self.assertIn("zouj-ai-sdlc profile SET: solo", ctx)
        self.assertEqual(self.profile(), "solo")
        self.assertEqual(git(self.root, "log", "-1", "--format=%s"), "chore(aiops): Setup Profile solo")
        self.assertEqual(git(self.root, "rev-parse", "HEAD~1"), head)
        self.assertEqual(git(self.root, "show", "--name-only", "--format=", "HEAD").split(), [CONFIG])
        from sdlc_engine import cli

        for text in ("setup profile TEAM", "  Setup  Profile strict.  ", "Setup Profile solo!\n"):
            self.assertTrue(cli.PROFILE_RE.match(text), text)  # as lenient as the approval phrases

    def test_phrase_inside_other_text_is_ignored(self):
        for text in (
            "please Setup Profile solo",
            "Setup Profile solo now",
            "ok\nSetup Profile solo",
            "Setup Profile solo\nand start the intent",
            "`Setup Profile solo`",
            "Setup Profiles solo",
        ):
            self.assertEqual(self.prompt(text), "", text)  # an ordinary prompt: no output
        self.assertEqual((self.root / CONFIG).read_bytes(), self.before)

    def test_unknown_or_missing_name_lists_profiles(self):
        for text in ("Setup Profile fast", "Setup Profile", "setup profile"):
            ctx = self.context(text)
            self.assertIn("profile NOT set", ctx, text)
            for name in ("solo", "team", "strict"):
                self.assertIn(f"Setup Profile {name}", ctx)
        self.assertEqual((self.root / CONFIG).read_bytes(), self.before)

    def test_dormant_without_aiops(self):
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.prompt("Setup Profile solo"), "")
        self.assertFalse((self.root / ".aiops").exists())

    def test_works_with_the_session_markers_set(self):
        """Claude Code sets both markers for the hooks of every session, a human's included (0007 spec R-2)."""
        ctx = self.context("Setup Profile solo", env={"CLAUDECODE": "1", "CLAUDE_CODE_CHILD_SESSION": "1"})
        self.assertIn("profile SET: solo", ctx)
        self.assertEqual(self.profile(), "solo")

    def test_second_phrase_changes_nothing(self):
        self.context("Setup Profile team")
        head = git(self.root, "rev-parse", "HEAD")
        ctx = self.context("Setup Profile solo")  # a downgrade: a terminal run only
        self.assertIn("profile NOT set", ctx)
        self.assertIn("bin/sdlc setup --profile solo", ctx)
        self.assertEqual((self.profile(), git(self.root, "rev-parse", "HEAD")), ("team", head))

    def test_approval_phrases_unchanged(self):
        self.d.mkdir()
        self.write("intent", INTENT)
        self.assertIn("NOT opened", self.context("Intent Approved 0001"))  # the default: a signature per approval
        self.assertIn("profile SET: solo", self.context("Setup Profile solo"))
        self.assertIn("gate OPENED", self.context("Intent Approved 0001"))  # solo: the typed phrase is the proof
        self.assertIn("profile NOT set", self.context("Setup Profile team"))  # a gate has been opened since

    def test_agent_setup_and_writes_still_cannot_change_config(self):
        r = self.run_sdlc("setup", "--profile", "solo", "--yes", env={"CLAUDECODE": "1"})
        self.assertEqual((self.root / CONFIG).read_bytes(), self.before, r.stdout + r.stderr)
        self.assertIn("Setup Profile solo", r.stdout)  # the human step is the phrase
        edit = self.hook("pre-edit", self.hook_input("Write", file_path=str(self.root / CONFIG), content="{}"))
        self.assertEqual(edit.returncode, 2, edit.stderr)
        bash = self.hook("pre-bash", self.hook_input("Bash", command=f"echo '{{}}' > {CONFIG}"))
        self.assertEqual(bash.returncode, 2, bash.stderr)
        self.assertEqual((self.root / CONFIG).read_bytes(), self.before)

    def test_through_the_shell_hook(self):
        import subprocess
        from helpers import ROOT

        payload = json.dumps(
            {"prompt": "Setup Profile solo", "cwd": str(self.root), "hook_event_name": "UserPromptSubmit"}
        )
        env = {**self.env, "CLAUDECODE": "1", "CLAUDE_PROJECT_DIR": str(self.root), "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        r = subprocess.run(
            [str(ROOT / "hooks" / "engine.sh"), "prompt"],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            cwd=self.root,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("profile SET: solo", r.stdout)
        self.assertEqual(self.profile(), "solo")


def terminal_command():
    import shlex
    from helpers import ROOT
    from sdlc_engine import approvals

    return f"{approvals.PYTHON} -I {shlex.quote(str(ROOT / 'bin' / 'sdlc'))}"


class Where(RepoCase):
    """`sdlc where` prints the command for the human's own terminal (0007 S8, AC-9)."""

    def snapshot(self):
        return (
            {
                str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*")
                if p.is_file() and p.relative_to(self.root).parts[0] != ".git"
            },
            git(self.root, "status", "--porcelain"),
        )

    def test_first_line_is_the_terminal_command(self):
        import subprocess
        import sys
        from helpers import SDLC

        before = self.snapshot()
        for case in ("initialized", "no .aiops/"):
            if case == "no .aiops/":
                shutil.rmtree(self.root / ".aiops")
                before = self.snapshot()
            for env in ({}, {"CLAUDECODE": "1", "CLAUDE_CODE_CHILD_SESSION": "1"}):  # the human, the agent
                r = self.run_sdlc("where", env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                lines = r.stdout.splitlines()
                self.assertEqual(lines[0], terminal_command(), (case, env))
                rest = "\n".join(lines[1:])
                for sub in (
                    "setup --profile",
                    "approve <id> intent|spec|plan",
                    "uninstall",
                    "legacy-approvals",
                    "close <id>",
                    "unlock",
                ):
                    self.assertIn(sub, rest)
                self.assertEqual(self.snapshot(), before, (case, env))  # writes nothing
        outside = subprocess.run(
            [sys.executable, SDLC, "where"], cwd=self.root.parent, capture_output=True, text=True, env=self.env
        )  # not even a git repo
        self.assertEqual((outside.returncode, outside.stdout.splitlines()[0]), (0, terminal_command()))
        r = self.run_sdlc("where", "approve")  # it takes no arguments
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertIn("where", self.run_sdlc("help").stdout)


class Card(RepoCase):
    """The state card names the human's terminal command when a human step is pending (0007 S8, AC-10)."""

    def card(self):
        r = self.run_sdlc("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def session(self):
        return self.hook("session-start", {"cwd": str(self.root), "source": "startup"}).stdout

    def test_terminal_line_when_no_profile_chosen(self):
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.run_sdlc("init").returncode, 0)  # the template config: no profile
        for text in (self.session(),):  # no active intent yet
            self.assertIn(f"- Your terminal: {terminal_command()}", text)
            self.assertIn("Setup Profile solo|team|strict", text)
        self.d.mkdir()
        self.write("intent", INTENT)
        for text in (self.card(), self.session()):
            self.assertIn(f"- Your terminal: {terminal_command()}", text)
            self.assertIn("Setup Profile solo|team|strict", text)
        payload = {"prompt": "Setup Profile solo", "cwd": str(self.root), "hook_event_name": "UserPromptSubmit"}
        self.assertIn("profile SET", self.hook("prompt", payload).stdout)
        for text in (self.card(), self.session()):  # chosen: solo needs no terminal
            self.assertNotIn("Your terminal", text)
            self.assertNotIn("Setup Profile", text.split("## zouj-ai-sdlc", 1)[1].split("\n\n", 1)[0])

    def test_terminal_line_when_a_gate_needs_the_terminal(self):
        (self.root / ".aiops" / "config.json").write_text(
            '{"approval_key_policy": "human"}'
        )  # a signature per approval
        self.write("intent", INTENT)  # waiting on the human at the gate
        for text in (self.card(), self.session()):
            self.assertIn(f"- Your terminal: {terminal_command()} approve 0001 intent", text)
            self.assertNotIn("Setup Profile", text.split("## zouj-ai-sdlc", 1)[1].split("\n\n", 1)[0])

    def test_no_terminal_line_otherwise(self):
        self.assertNotIn("Your terminal", self.session())  # no intent.md yet: waiting on the agent
        self.write("intent", INTENT)
        self.assertNotIn("Your terminal", self.card())  # policy any: the phrase is enough
        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "human"}')
        (self.d / "intent.md").unlink()
        self.assertNotIn("Your terminal", self.card())  # a signature is needed, but not yet
        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "any"}')
        self.to_execution()
        self.assertNotIn("Your terminal", self.card())  # state 4: the agent's turn


class Docs(unittest.TestCase):
    """What the shipped text must say about the first run (0007 S9-S13: AC-17, AC-18, AC-19, AC-21)."""

    def setUp(self):
        from helpers import ROOT

        self.root = ROOT

    def text(self, rel):
        return (self.root / rel).read_text()

    def test_scaffold_explains_auto_mode(self):
        readme = self.text("templates/scaffold/.aiops/README.md")
        section = readme.split("## Unattended execution", 1)[1]
        self.assertIn("--permission-mode auto", section)
        self.assertIn('"defaultMode": "auto"', section)
        self.assertIn("user settings", section)  # where that key works
        self.assertRegex(section, r"ignore[sd]?\b.*\bproject settings|project settings\b.*\bignore")
        self.assertRegex(section, r"guards? still")  # auto mode doesn't lift them
        settings = json.loads(self.text("templates/scaffold/.claude/settings.json"))
        self.assertNotIn("defaultMode", json.dumps(settings))  # the plugin sets no permission mode
        self.assertNotIn("allow", settings["permissions"])

    def test_setup_skill_asks_for_the_phrase(self):
        skill = self.text("skills/setup/SKILL.md")
        self.assertIn("`Setup Profile <profile>`", skill)
        self.assertIn("whole prompt", skill)
        self.assertIn("`team` included", skill)  # every profile is recorded
        self.assertLess(skill.index("--yes"), skill.index("`Setup Profile <profile>`"))  # scaffold, then the phrase
        self.assertNotIn("For `solo` or `strict`, the printed human step is", skill)  # no terminal step for solo
        self.assertNotIn("run `<plugin>/bin/sdlc setup --profile solo` in their own terminal", skill)
        self.assertRegex(skill, r"(?i)never.*(type|typing|simulat)")  # the agent doesn't type it
        using = self.text("skills/using-zouj-ai-sdlc/SKILL.md")
        self.assertIn("Setup Profile", using)  # the bootstrap knows the phrase

    def test_skills_name_where_and_with(self):
        for rel in ("skills/setup/SKILL.md", "skills/configure/SKILL.md", "skills/using-zouj-ai-sdlc/SKILL.md"):
            self.assertIn("sdlc where", self.text(rel), rel)
        for rel in ("skills/setup/SKILL.md", "skills/init/SKILL.md"):
            self.assertIn("--with", self.text(rel), rel)
        setup = self.text("skills/setup/SKILL.md")
        for part in ("review", "maintain", "deploy", "governance", "issues"):
            self.assertIn(part, setup, part)
        self.assertIn("Setup Profile", self.text("skills/configure/SKILL.md"))  # the first profile is the phrase
        self.assertIn("Setup Profile", self.text("skills/onboard/SKILL.md"))

    def test_docs_document_where_and_with(self):
        """0007 AC-18, spec R-22: the user docs name `sdlc where`, `--with` and the phrase; the ADR and the threat
        model record the decision and its gap."""
        for rel in ("README.md", "COMMANDS-QUICK-REF.md", "TROUBLESHOOTING.md"):
            text = self.text(rel)
            self.assertIn("sdlc where", text, rel)
            self.assertIn("--with", text, rel)
            self.assertIn("Setup Profile", text, rel)
        readme = self.text("README.md")
        install = readme.split("\n## Install", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("Where is `<plugin>`?", install)  # `sdlc where` answers it
        for part in ("review", "maintain", "deploy", "governance", "issues"):
            self.assertIn(f"`{part}`", install, part)
        lifecycle = readme.split("\n## Lifecycle", 1)[1].split("\n## ", 1)[0]
        self.assertIn("parts", lifecycle)  # install-state records them
        quick = self.text("COMMANDS-QUICK-REF.md")
        self.assertIn("| `sdlc where` |", quick)
        self.assertNotIn("`team` default", quick)  # the agent's setup sets no profile
        adr = self.text("docs/adr/0003-first-profile-by-typed-phrase.md")
        for piece in ("Status: Accepted", "Setup Profile", "chore(aiops): Setup Profile", "AIOps-Profile:", "unsigned"):
            self.assertIn(piece, adr, piece)
        arch = self.text("docs/architecture.md")
        model = arch.split("\n## Threat model", 1)[1].split("\n## ", 1)[0]
        rows = [line for line in model.splitlines() if "Setup Profile" in line]
        self.assertTrue(any(line.startswith("| The first profile") for line in rows), rows)  # the phrase's own row
        self.assertTrue(any("`sdlc setup`" in line.split("|")[1] for line in rows), rows)  # the setup row names it
        gaps = arch.split("\n## Known gaps", 1)[1].split("\n## ", 1)[0]
        self.assertIn("claude -p", gaps)  # a phrase typed into a session the agent starts
        self.assertIn("Setup Profile", gaps)
        self.assertIn("0003-first-profile-by-typed-phrase", arch)
        for rel in ("docs/adoption.md", "docs/roadmap.md"):  # on main since PR #17
            self.assertIn("Setup Profile", self.text(rel), rel)
        self.assertNotIn("<plugin>/bin/sdlc setup --profile solo", self.text("docs/adoption.md"))

    def test_changelog_has_the_release(self):
        """0007 AC-19: the release section names both intents, and every pin in the shipped docs matches plugin.json."""
        import re

        version = json.loads(self.text(".claude-plugin/plugin.json"))["version"]
        self.assertEqual(version, "0.2.0-alpha.4")
        log = self.text("CHANGELOG.md")
        section = log.split(f"## [{version}]", 1)[1].split("\n## [", 1)[0]
        for piece in (
            ".aiops/0005-guard-gaps/",
            ".aiops/0007-first-run/",
            "Setup Profile",
            "sdlc where",
            "--with",
            "G-FILE-05",
            "G-FILE-06",
            "### Upgrading from 0.2.0-alpha.3",
        ):
            self.assertIn(piece, section, piece)
        unreleased = log.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
        self.assertNotIn("Planned as", unreleased)  # nothing is left waiting there
        self.assertIn(f"[Unreleased]: https://github.com/zoujagger/zouj-ai-sdlc/compare/v{version}...HEAD", log)
        readme = self.text("README.md")
        self.assertEqual(set(re.findall(r"0\.2\.0-alpha\.\d+", readme.split("\n## Lifecycle", 1)[0])), {version})
        self.assertEqual(readme.count(f"@v{version}"), 2)  # both marketplace commands
        self.assertIn(f'"ref": "v{version}"', readme)
        history = json.loads(self.text("defaults/scaffold-history.json"))
        self.assertIn(version, history)
        self.assertNotIn("unreleased", history)  # the tree is the release now

    def test_profile_eval_case_is_complete(self):
        """0007 AC-21: the behavioural case exists, is listed, and its fixture is a scaffolded repo with no profile."""
        import os
        import subprocess
        import tempfile

        case = self.root / "evals" / "profile-by-phrase"
        for rel in (
            "case.yaml",
            "fixture.sh",
            "prompt.md",
            "graders/asks-for-phrase.md",
            "graders/config-unchanged.md",
        ):
            self.assertTrue((case / rel).is_file(), rel)
        self.assertIn("name: profile-by-phrase", (case / "case.yaml").read_text())
        self.assertIn("scaffold_script: fixture.sh", (case / "case.yaml").read_text())
        self.assertIn("solo", (case / "prompt.md").read_text())
        self.assertIn("Setup Profile solo", (case / "graders" / "asks-for-phrase.md").read_text())
        unchanged = (case / "graders" / "config-unchanged.md").read_text()
        self.assertIn(".aiops/config.json", unchanged)
        self.assertIn("require_signed_approvals", unchanged)  # solo would set it to false
        self.assertIn("| profile-by-phrase |", self.text("evals/README.md"))
        with tempfile.TemporaryDirectory() as tmp:
            work, home = os.path.join(tmp, "work"), os.path.join(tmp, "home")
            os.mkdir(work)
            os.mkdir(home)
            env = {
                k: v
                for k, v in os.environ.items()
                if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_PROJECT_DIR", "GIT_CONFIG_GLOBAL")
            }
            r = subprocess.run(
                ["bash", str(case / "fixture.sh")], cwd=work, capture_output=True, text=True, env={**env, "HOME": home}
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            template = json.loads(self.text("templates/scaffold/.aiops/config.json"))
            with open(os.path.join(work, ".aiops", "config.json")) as f:
                self.assertEqual(json.load(f), template)
            self.assertFalse(os.path.exists(os.path.join(work, "ops", "bands.yaml")))  # the default: core only
            self.assertEqual(os.listdir(home), [])  # nothing written to the operator's home
            status = subprocess.run(["git", "status", "--porcelain"], cwd=work, capture_output=True, text=True, env=env)
            self.assertEqual(status.stdout, "")  # the scaffold is committed

    def test_skills_name_the_part_they_need(self):
        for rel, part in (
            ("skills/intent/SKILL.md", "maintain"),
            ("skills/triage/SKILL.md", "maintain"),
            ("skills/deploy/SKILL.md", "deploy"),
        ):
            self.assertIn(f"sdlc setup --with {part}", self.text(rel), rel)


if __name__ == "__main__":
    unittest.main()
