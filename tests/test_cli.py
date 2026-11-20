"""`sdlc` CLI: init (non-destructive scaffold), new/draft/use/status/validate, lock/unlock."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import INTENT, RepoCase, git


class Init(RepoCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")

    def test_wire_refuses_unsafe_recipes(self):
        """0009 S4 (AC-19): wire takes a {target: command} dict and refuses any value that could break out of
        its recipe line, whatever its source."""
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
        from sdlc_engine import cli

        stub = '\t@echo "[test] not configured - edit Makefile"\n'
        src, wired = cli.wire(stub, {"test": "npm run test"})
        self.assertEqual((src, wired), ("\tnpm run test\n", ["test"]))
        for bad in ("npm test\n\trm -rf ~", "\tnpm test", "@npm test", "-npm test", "npm\x1btest", "", "a\rb"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                cli.wire(stub, {"test": bad})
        with self.assertRaises(ValueError):
            cli.wire(stub, {"deploy": "make it so"})  # only the five contract targets

    def test_preset_wiring_bytes_unchanged(self):
        """0009 S4 (AC-20): a preset wired through the new API hashes as the released Makefile+<stack> entries, so
        repos wired by beta.1 stay `current`."""
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
        from sdlc_engine import cli, lifecycle

        entry = lifecycle.history()[lifecycle.history_key()]
        template = (cli.TEMPLATES / "scaffold" / "Makefile").read_text()
        for stack in cli.STACKS:
            wired = cli.wire(template, cli.preset_recipes(stack))[0].encode()
            self.assertEqual(lifecycle.sha256_bytes(lifecycle.normalize(wired)), entry[f"Makefile+{stack}"], stack)
            text = (cli.TEMPLATES / "stacks" / f"{stack}.recipes").read_text()
            self.assertEqual(cli.parse_recipes(text), cli.preset_recipes(stack))

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

    def test_validate_scope_size_exit_codes(self):
        """0011 S1: 6 ACs warn (exit 0), 9 ACs in a Draft spec fail (exit 1)."""
        from helpers import SPEC

        two = (
            "- **AC-1**: Given contacts, when exporting, then a CSV is returned.\n"
            "- **AC-2**: Given another tenant, when exporting, then 403."
        )
        for n, code, line in (
            (6, 0, "! .aiops/0001-csv-export/spec.md: `## Acceptance criteria` has 6 criteria"),
            (9, 1, "✗ .aiops/0001-csv-export/spec.md: Spec exceeds maximum of 8 acceptance criteria"),
        ):
            acs = "\n".join(f"- **AC-{i}**: Given case {i}, when acting, then outcome {i}." for i in range(1, n + 1))
            self.write("spec", SPEC.replace(two, acs))
            r = self.run_sdlc("validate", "0001")
            self.assertEqual(r.returncode, code, r.stdout)
            self.assertIn(line, r.stdout)

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
        self.init("--with", "all")  # every part but dsl (0012)
        self.assertEqual(
            self.files() - self.base, set(self.lc.scaffold_paths(self.lc.LEGACY_PARTS)) | {STATE, ".gitignore"}
        )
        self.assertEqual(self.parts(), sorted(self.lc.LEGACY_PARTS))

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
        self.assertTrue(set(self.lc.scaffold_paths(self.lc.LEGACY_PARTS)) <= self.files())
        self.assertEqual(self.parts(), sorted(self.lc.LEGACY_PARTS))  # never dsl (0012)

    def test_template_config_with_full_scaffold_gets_every_part(self):
        self.init("--with", "all")
        (self.root / STATE).unlink()  # as 0.2.0-alpha.2 left it
        (self.root / "ops" / "bands.yaml").unlink()
        (self.root / ".github" / "workflows" / "deploy.yml").unlink()
        self.init()
        self.assertTrue(set(self.lc.scaffold_paths(self.lc.LEGACY_PARTS)) <= self.files())  # both restored
        self.assertEqual(self.parts(), sorted(self.lc.LEGACY_PARTS))  # every part but dsl (0012)

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


class SetupCommand(RepoCase):
    """The human types `/zouj-ai-sdlc:setup <name>` as the whole prompt; the prompt hook sets the repo's first profile
    (0007 S15: AC-1, AC-3, AC-4, AC-6, AC-7). The `Setup Profile` phrase is gone."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.run_sdlc("init", env={"CLAUDECODE": "1"}).returncode, 0)  # the agent scaffolds
        self.before = (self.root / CONFIG).read_bytes()  # the template: no profile yet

    def prompt(self, text, env=None, cwd=None):
        payload = {"prompt": text, "cwd": str(cwd or self.root), "hook_event_name": "UserPromptSubmit"}
        # hooks always run with the marker, and Claude Code names the session's repo
        r = self.hook("prompt", payload, env={"CLAUDECODE": "1", "CLAUDE_PROJECT_DIR": str(self.root), **(env or {})})
        self.assertEqual(r.returncode, 0, r.stderr)  # a prompt hook never blocks
        return r.stdout

    def context(self, text, env=None, cwd=None):
        return json.loads(self.prompt(text, env, cwd))["hookSpecificOutput"]["additionalContext"]

    def profile(self):
        return json.loads((self.root / CONFIG).read_text()).get("profile")

    def fresh(self, package):
        """The repo back to its first commit (no .aiops/, no scaffold), with a package.json at the top."""
        git(self.root, "clean", "-fdxq")
        (self.root / "package.json").write_text(json.dumps(package))

    def engine_prompt(self, text):
        """The prompt through hooks/engine.sh, as Claude Code runs it (the pre-python match included)."""
        from helpers import ROOT

        payload = json.dumps({"prompt": text, "cwd": str(self.root), "hook_event_name": "UserPromptSubmit"})
        env = {**self.env, "CLAUDECODE": "1", "CLAUDE_PROJECT_DIR": str(self.root), "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        r = subprocess.run(
            [str(ROOT / "hooks" / "engine.sh"), "prompt"], input=payload, capture_output=True, text=True, env=env,
            cwd=self.root,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_typed_setup_suggests_detected_stack(self):
        """0009 S6, revised in review round 1 (the human's choice): through hooks/engine.sh the typed command writes
        the stub Makefile and lists the detected recipes as a suggestion, so no repo command runs before the human
        has seen them (AC-15). The agent's `sdlc setup --stack auto --yes` then wires the untouched stub (AC-12)."""
        from sdlc_engine import cli as engine

        self.fresh({"dependencies": {"react": "^18.3.1"}, "scripts": {"test": "react-scripts test", "build": "vite build"}})
        (self.root / "yarn.lock").write_text("")
        out = self.engine_prompt("/zouj-ai-sdlc:setup solo")
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("profile SET: solo", context)
        self.assertEqual((self.root / "Makefile").read_bytes(), engine.rendered_template("Makefile"))  # stubs only
        for text in (context, out["systemMessage"]):
            self.assertIn("Makefile: detected React (from package.json, yarn.lock), not wired yet", text)
            self.assertIn("test: CI=true yarn run test", text)
            self.assertIn("lint: not configured", text)
            self.assertIn("setup --stack auto --yes`", text)
            self.assertIn("in your own terminal", text)
        self.assertEqual(git(self.root, "show", "--name-only", "--format=", "HEAD").split(), [CONFIG])
        self.assertEqual(git(self.root, "log", "-1", "--format=%s"), "chore(aiops): Setup Profile solo")
        self.assertEqual(git(self.root, "ls-files", "Makefile"), "")  # left for the human's review
        self.assertNotIn("recipes", json.loads((self.root / ".aiops" / "install-state.json").read_text()))
        agent = {"CLAUDECODE": "1", "CLAUDE_PROJECT_DIR": str(self.root)}
        r = self.run_sdlc("setup", "--stack", "auto", "--yes", env=agent)
        self.assertIn("in your own terminal", r.stdout)  # run by the agent, setup never wires
        self.assertEqual((self.root / "Makefile").read_bytes(), engine.rendered_template("Makefile"))
        r = self.run_sdlc("setup", "--stack", "auto", "--yes")  # the human, in their own terminal
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        mk = (self.root / "Makefile").read_text()
        self.assertIn("\tCI=true yarn run test\n", mk)
        self.assertIn("\tyarn run build\n", mk)
        st = json.loads((self.root / ".aiops" / "install-state.json").read_text())
        self.assertEqual((st["stack"], st["recipes"]), ("react", {"test": "CI=true yarn run test", "build": "yarn run build"}))
        self.assertEqual(self.profile(), "solo")  # rerunning setup keeps the profile the config names

    def test_makefile_block_escapes(self):
        """Review round 1: `printable` is exercised with values that survive into the block."""
        from sdlc_engine import setup as engine_setup
        from sdlc_engine.stacks import Detection

        det = Detection("node", "Bad\x1b[2J", {"test": "npm run test\x07"}, ["package.json\x1b]0;x\x07"], "")
        block = engine_setup.makefile_block(det)
        self.assertNotIn("\x1b", block)
        self.assertNotIn("\x07", block)
        self.assertIn("\\x1b", block)

    def test_typed_setup_without_a_stack_says_so(self):
        git(self.root, "clean", "-fdxq")
        context = self.context("/zouj-ai-sdlc:setup solo")
        self.assertIn("Makefile: no stack detected", context)
        self.assertNotIn("not wired yet", context)
        self.assertIn("sdlc doctor", context)

    def test_typed_setup_escapes_detected_text(self):
        """0009 S6 (AC-16): repo text with control characters never reaches the reply raw."""
        self.fresh({"scripts": {"lint\u001b[2J": "x", "test\u0007": "y", "build": "\u001b]0;pwn\u0007 tsc"}})
        (self.root / "angular.json").write_text(json.dumps({"projects": {"\u001b[31m": {}}}))
        out = json.loads(self.prompt("/zouj-ai-sdlc:setup solo"))
        for text in (out["hookSpecificOutput"]["additionalContext"], out["systemMessage"]):
            self.assertIn("Makefile: detected Angular", text)
            self.assertIn("build: npm run build", text)
            self.assertNotIn("\x1b", text)
            self.assertNotIn("\x07", text)
            self.assertNotIn("pwn", text)  # a script body never appears

    def test_whole_prompt_sets_the_profile(self):
        head = git(self.root, "rev-parse", "HEAD")
        ctx = self.context("/zouj-ai-sdlc:setup solo")
        self.assertIn("zouj-ai-sdlc profile SET: solo", ctx)
        self.assertEqual(self.profile(), "solo")
        self.assertEqual(git(self.root, "log", "-1", "--format=%s"), "chore(aiops): Setup Profile solo")
        self.assertEqual(git(self.root, "rev-parse", "HEAD~1"), head)
        self.assertEqual(git(self.root, "show", "--name-only", "--format=", "HEAD").split(), [CONFIG])
        from sdlc_engine import cli

        for text in ("/zouj-ai-sdlc:setup TEAM", "  /zouj-ai-sdlc:setup  strict  "):
            self.assertTrue(cli.PROFILE_RE.match(text), text)  # spaces around it; the name in any case
        # 0007 r4/r5: only what engine.sh can see in the raw JSON (a newline or a tab arrives escaped there)
        for text in ("/zouj-ai-sdlc:setup solo\n", "\n/zouj-ai-sdlc:setup solo", "\t/zouj-ai-sdlc:setup solo"):
            self.assertFalse(cli.PROFILE_RE.match(text), repr(text))  # a fresh repo never sees a newline form

    def test_command_with_other_text_is_ignored(self):
        for text in (
            "please /zouj-ai-sdlc:setup solo",
            "/zouj-ai-sdlc:setup solo now",
            "/zouj-ai-sdlc:setup solo team",
            "ok\n/zouj-ai-sdlc:setup solo",
            "/zouj-ai-sdlc:setup solo\nand start the intent",
            "`/zouj-ai-sdlc:setup solo`",
            "/zouj-ai-sdlc:setup",  # bare: the skill asks for the profile
            "/setup solo",  # not qualified: another plugin's setup may be the one that runs
            "/ZOUJ-AI-SDLC:SETUP solo",
            "Setup Profile solo",  # the removed phrase
            "setup profile solo",
        ):
            self.assertEqual(self.prompt(text), "", text)  # an ordinary prompt: no output
        self.assertEqual((self.root / CONFIG).read_bytes(), self.before)

    def test_unknown_name_lists_profiles(self):
        for text in ("/zouj-ai-sdlc:setup fast", "/zouj-ai-sdlc:setup none"):
            ctx = self.context(text)
            self.assertIn("profile NOT set", ctx, text)
            for name in ("solo", "team", "strict"):
                self.assertIn(f"/zouj-ai-sdlc:setup {name}", ctx)
            self.assertNotIn("Setup Profile", ctx)
        self.assertEqual((self.root / CONFIG).read_bytes(), self.before)
        # r7 NIT: the name is checked first, so R-6's list comes back even when the session's repo is unknown
        ctx = self.context("/zouj-ai-sdlc:setup fast", env={"CLAUDE_PROJECT_DIR": ""})
        for name in ("solo", "team", "strict"):
            self.assertIn(f"/zouj-ai-sdlc:setup {name}", ctx)
        self.assertNotIn("--profile fast", ctx)

    def test_refused_outside_the_session_repo(self):
        nested = self.root / "vendor" / "other"  # a repo of its own, with the template config
        nested.mkdir(parents=True)
        git(nested, "init", "-q", "-b", "main")
        for key, value in (("user.name", "Human Owner"), ("user.email", "owner@example.com")):
            git(nested, "config", key, value)
        shutil.copytree(self.root / ".aiops", nested / ".aiops")
        nested_before = (nested / CONFIG).read_bytes()
        ctx = self.context("/zouj-ai-sdlc:setup solo", cwd=nested)
        self.assertIn("profile NOT set", ctx)
        self.assertIn("session", ctx)
        self.assertIn(str(nested), ctx)
        self.assertEqual((nested / CONFIG).read_bytes(), nested_before)
        self.assertEqual((self.root / CONFIG).read_bytes(), self.before)
        ctx = self.context("/zouj-ai-sdlc:setup solo", env={"CLAUDE_PROJECT_DIR": ""})  # unknown: fail closed
        self.assertIn("profile NOT set", ctx)
        self.assertEqual((self.root / CONFIG).read_bytes(), self.before)
        sub = self.root / "src"  # a subdirectory of the session's repo is the same repo
        sub.mkdir(exist_ok=True)
        self.assertIn("profile SET: solo", self.context("/zouj-ai-sdlc:setup solo", cwd=sub))

    def test_worktree_redirect_is_refused(self):
        # 0007 r9 security LOW: core.worktree (allowed in repo-local config) makes git resolve the session's repo to
        # another one, so both sides of the session check would name that other repo
        other = Path(tempfile.mkdtemp(dir=self.root.parent))
        self.addCleanup(shutil.rmtree, other, True)
        git(other, "init", "-q", "-b", "main")
        for key, value in (("user.name", "Human Owner"), ("user.email", "owner@example.com")):
            git(other, "config", key, value)
        shutil.copytree(self.root / ".aiops", other / ".aiops")
        other_before = (other / CONFIG).read_bytes()
        git(self.root, "config", "core.worktree", str(other))
        ctx = self.context("/zouj-ai-sdlc:setup solo")
        self.assertIn("profile NOT set", ctx)
        self.assertIn("core.worktree", ctx)
        self.assertIn(f"session's repo {self.root}", ctx)  # r10 NIT: named, not only the redirected directory
        self.assertEqual((other / CONFIG).read_bytes(), other_before)
        self.assertEqual((self.root / CONFIG).read_bytes(), self.before)
        git(self.root, "config", "--unset", "core.worktree")
        self.assertIn(f"profile SET: solo in {self.root.resolve()}", self.context("/zouj-ai-sdlc:setup solo"))

    def test_works_with_the_session_markers_set(self):
        """Claude Code sets both markers for the hooks of every session, a human's included (0007 spec R-2)."""
        ctx = self.context("/zouj-ai-sdlc:setup solo", env={"CLAUDECODE": "1", "CLAUDE_CODE_CHILD_SESSION": "1"})
        self.assertIn("profile SET: solo", ctx)
        self.assertEqual(self.profile(), "solo")

    def test_second_command_changes_nothing(self):
        self.context("/zouj-ai-sdlc:setup team")
        head = git(self.root, "rev-parse", "HEAD")
        ctx = self.context("/zouj-ai-sdlc:setup solo")  # a downgrade: a terminal run only
        self.assertIn("profile NOT set", ctx)
        self.assertIn("bin/sdlc setup --profile solo", ctx)
        self.assertEqual((self.profile(), git(self.root, "rev-parse", "HEAD")), ("team", head))

    def test_approval_phrases_unchanged(self):
        self.d.mkdir()
        self.write("intent", INTENT)
        self.assertIn("NOT opened", self.context("Intent Approved 0001"))  # the default: a signature per approval
        self.assertIn("profile SET: solo", self.context("/zouj-ai-sdlc:setup solo"))
        self.assertIn("gate OPENED", self.context("Intent Approved 0001"))  # solo: the typed phrase is the proof
        self.assertIn("profile NOT set", self.context("/zouj-ai-sdlc:setup team"))  # a gate has been opened since

    def test_agent_setup_and_writes_still_cannot_change_config(self):
        r = self.run_sdlc("setup", "--profile", "solo", "--yes", env={"CLAUDECODE": "1"})
        self.assertEqual((self.root / CONFIG).read_bytes(), self.before, r.stdout + r.stderr)
        self.assertIn("/zouj-ai-sdlc:setup solo", r.stdout)  # the human step is the typed command
        self.assertNotIn("Setup Profile", r.stdout)
        self.assertIn('(profile solo)" --', r.stdout)  # the scaffold commit names the chosen profile, not the default
        edit = self.hook("pre-edit", self.hook_input("Write", file_path=str(self.root / CONFIG), content="{}"))
        self.assertEqual(edit.returncode, 2, edit.stderr)
        bash = self.hook("pre-bash", self.hook_input("Bash", command=f"echo '{{}}' > {CONFIG}"))
        self.assertEqual(bash.returncode, 2, bash.stderr)
        self.assertEqual((self.root / CONFIG).read_bytes(), self.before)

    def test_through_the_shell_hook(self):
        import subprocess
        from helpers import ROOT

        payload = json.dumps(
            {"prompt": "/zouj-ai-sdlc:setup solo", "cwd": str(self.root), "hook_event_name": "UserPromptSubmit"}
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
        for text in (self.card(), self.session()):  # no intent yet: `sdlc status` says it too (0007 r6, AC-10)
            self.assertIn(f"- Your terminal: {terminal_command()}", text)
            self.assertIn("types `/zouj-ai-sdlc:setup solo|team|strict`", text)
        self.d.mkdir()
        self.write("intent", INTENT)
        for text in (self.card(), self.session()):
            self.assertIn(f"- Your terminal: {terminal_command()}", text)
            self.assertIn("types `/zouj-ai-sdlc:setup solo|team|strict`", text)
        payload = {"prompt": "/zouj-ai-sdlc:setup solo", "cwd": str(self.root), "hook_event_name": "UserPromptSubmit"}
        self.assertIn("profile SET", self.hook("prompt", payload, env={"CLAUDE_PROJECT_DIR": str(self.root)}).stdout)
        for text in (self.card(), self.session()):  # chosen: solo needs no terminal
            self.assertNotIn("Your terminal", text)
            self.assertNotIn("/zouj-ai-sdlc:setup solo|", text.split("## zouj-ai-sdlc", 1)[1].split("\n\n", 1)[0])

    def test_terminal_line_when_a_gate_needs_the_terminal(self):
        (self.root / ".aiops" / "config.json").write_text(
            '{"approval_key_policy": "human"}'
        )  # a signature per approval
        self.write("intent", INTENT)  # waiting on the human at the gate
        for text in (self.card(), self.session()):
            self.assertIn(f"- Your terminal: {terminal_command()} approve 0001 intent", text)
            self.assertNotIn("/zouj-ai-sdlc:setup solo|", text.split("## zouj-ai-sdlc", 1)[1].split("\n\n", 1)[0])

    def test_terminal_line_when_a_passphrase_key_signs(self):
        # 0007 review r2 M1: the recommended team key (a passphrase, kept out of ssh-agent) has no signing problem, yet
        # the prompt hook has no terminal to ask for the passphrase, so the gate still needs the human's terminal.
        from unittest import mock

        from sdlc_engine import approvals, cli
        from sdlc_engine.machine import evaluate

        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "human"}')
        self.write("intent", INTENT)
        with mock.patch.object(approvals, "signing_problem", return_value=None):
            lines = cli.terminal_lines(self.root, evaluate(self.root, self.d))
        self.assertEqual(lines, [f"- Your terminal: {approvals.approve_command('0001', 'intent')}"])
        (self.root / ".aiops" / "config.json").write_text('{"approval_key_policy": "any"}')
        with mock.patch.object(approvals, "signing_problem", return_value=None):
            self.assertEqual(cli.terminal_lines(self.root, evaluate(self.root, self.d)), [])  # the phrase signs

    def test_card_runs_no_history_walk(self):
        # 0007 r6 LOW: the card's no-profile check reads files only; the `git log --all` walk is the command's
        from unittest import mock

        from sdlc_engine import cli, setup

        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.run_sdlc("init").returncode, 0)  # the template config: no profile
        with mock.patch.object(setup, "approval_in_history", side_effect=AssertionError("history walked")):
            lines = cli.terminal_lines(self.root)
        self.assertTrue(any("/zouj-ai-sdlc:setup solo|team|strict" in line for line in lines), lines)
        # r7: the hint says the command may still refuse (the card skips the history walk the command makes)
        self.assertTrue(any("refuses" in line for line in lines), lines)

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

    def test_scope_sizing_guidance(self):
        """0011 S2 (AC-5): the scope check before intent.md, the 3-5 caps, and the epic callout ship in the text."""
        intent = self.text("skills/intent/SKILL.md")
        step3, step4 = intent.split("\n3. ", 1)[1], intent.split("\n4. ", 1)[1]
        self.assertIn("Scope check", step3.split("\n4. ", 1)[0])  # before step 4 creates anything
        self.assertIn("split", step3.split("\n4. ", 1)[0])
        self.assertIn("3 to 5", step4.split("\n5. ", 1)[0])
        spec = self.text("skills/spec/SKILL.md")
        self.assertIn("3 to 5", spec)
        self.assertRegex(spec, r"more than 5.*warn|warn.*more than 5")
        self.assertIn("more than 8", spec)
        analyst = self.text("agents/product-analyst.md")
        for phrase in ("Intent cap", "Strict cap", "never more than 7", "user-observable", "**Scope:**"):
            self.assertIn(phrase, analyst)
        template = self.text("templates/artifacts/intent.md")
        self.assertIn("3 to 5", template)
        self.assertIn("**Scope:**", template)
        self.assertIn("3 to 5", self.text("templates/artifacts/spec.md"))
        self.assertIn("`scope_size`", self.text("docs/state-machine.md"))
        unreleased = self.text("CHANGELOG.md").split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
        self.assertIn(".aiops/0011-scope-sizing/", unreleased)

    def test_setup_skill_asks_for_the_command(self):
        """0007 S18 (R-21): the skill reads the hook's reminder first; with none, it asks for the typed command."""
        skill = self.text("skills/setup/SKILL.md")
        self.assertIn("`/zouj-ai-sdlc:setup <profile>`", skill)
        self.assertIn("whole prompt", skill)
        self.assertIn("`team` included", skill)  # every profile is recorded
        for reminder in ("profile SET", "profile NOT set"):
            self.assertIn(reminder, skill)
        self.assertLess(skill.index("profile SET"), skill.index("--dry-run"))  # the reminder first, then a preview
        self.assertIn("`/setup", skill)  # a bare /setup sets nothing: the skill names the qualified form
        self.assertNotIn("For `solo` or `strict`, the printed human step is", skill)  # no terminal step for solo
        self.assertNotIn("run `<plugin>/bin/sdlc setup --profile solo` in their own terminal", skill)
        self.assertRegex(skill, r"(?i)never.*(type|typing|simulat)")  # the agent doesn't type it
        self.assertNotRegex(skill, r"sdlc setup --profile <profile> --yes")  # the agent never applies a profile
        for rel in ("skills/using-zouj-ai-sdlc/SKILL.md", "skills/configure/SKILL.md", "skills/init/SKILL.md"):
            self.assertIn("/zouj-ai-sdlc:setup solo|team|strict", self.text(rel), rel)

    def test_no_shipped_file_names_the_phrase(self):
        """0007 S18-S20 (AC-18): the `Setup Profile <name>` phrase is gone from everything that ships, except the
        profile commit's title in the engine (`chore(aiops): Setup Profile <name>`)."""
        found = []
        files = [self.root / rel for rel in ("README.md", "COMMANDS-QUICK-REF.md", "TROUBLESHOOTING.md", "SECURITY.md")]
        for top in ("skills", "templates", "lib", "evals", "docs"):
            files += sorted((self.root / top).rglob("*"))
        for f in files:
            if "results" in f.relative_to(self.root).parts:  # local eval runs, git-ignored
                continue
            if f.is_file() and f.suffix in (".md", ".py", ".json", ".yml", ".yaml", ".sh", ""):
                for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    if "Setup Profile" in line and "chore(aiops): Setup Profile" not in line:
                        found.append(f"{f.relative_to(self.root)}:{n}")
        self.assertEqual(found, [])  # the CHANGELOG may still tell the history

    def test_skills_name_where_and_with(self):
        for rel in ("skills/setup/SKILL.md", "skills/configure/SKILL.md", "skills/using-zouj-ai-sdlc/SKILL.md"):
            self.assertIn("sdlc where", self.text(rel), rel)
        for rel in ("skills/setup/SKILL.md", "skills/init/SKILL.md"):
            self.assertIn("--with", self.text(rel), rel)
        setup = self.text("skills/setup/SKILL.md")
        for part in ("review", "maintain", "deploy", "governance", "issues"):
            self.assertIn(part, setup, part)
        self.assertIn("/zouj-ai-sdlc:setup <profile>", self.text("skills/configure/SKILL.md"))  # the first profile
        self.assertIn("/zouj-ai-sdlc:setup solo|team|strict", self.text("skills/onboard/SKILL.md"))

    def test_docs_document_where_and_with(self):
        """0007 AC-18, spec R-22: the user docs name `sdlc where`, `--with` and the typed setup command; the ADR and
        the threat model record the decision and its gap."""
        for rel in ("README.md", "COMMANDS-QUICK-REF.md", "TROUBLESHOOTING.md"):
            text = self.text(rel)
            self.assertIn("sdlc where", text, rel)
            self.assertIn("--with", text, rel)
            self.assertIn("/zouj-ai-sdlc:setup solo", text, rel)
        self.assertTrue((self.root / "docs" / "adr" / "0003-first-profile-by-typed-setup-command.md").is_file())
        self.assertFalse((self.root / "docs" / "adr" / "0003-first-profile-by-typed-phrase.md").exists())
        arch = self.text("docs/architecture.md")
        self.assertIn('claude -p "/zouj-ai-sdlc:setup solo"', arch)  # the accepted gap, under its new name
        self.assertIn("dormant", arch)
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
        adr = self.text("docs/adr/0003-first-profile-by-typed-setup-command.md")
        for piece in (
            "Status: Accepted",
            "/zouj-ai-sdlc:setup <name>",
            "chore(aiops): Setup Profile",
            "AIOps-Profile:",
            "unsigned",
            "only missing files",
            "dormant",
        ):
            self.assertIn(piece, adr, piece)
        arch = self.text("docs/architecture.md")
        model = arch.split("\n## Threat model", 1)[1].split("\n## ", 1)[0]
        rows = [line for line in model.splitlines() if "/zouj-ai-sdlc:setup" in line]
        self.assertTrue(any(line.startswith("| The first profile") for line in rows), rows)  # the command's own row
        self.assertTrue(any(line.startswith("| The typed setup command writes") for line in rows), rows)  # R-2a
        self.assertTrue(any("`sdlc setup`" in line.split("|")[1] for line in rows), rows)  # the setup row names it
        gaps = arch.split("\n## Known gaps", 1)[1].split("\n## ", 1)[0]
        self.assertIn('claude -p "/zouj-ai-sdlc:setup solo"', gaps)  # a command typed into a session the agent starts
        self.assertIn("sdlc hook prompt", gaps)  # 0007 r5: a crafted payload in a repo without .aiops/
        self.assertIn("0003-first-profile-by-typed-setup-command", arch)
        for rel in ("docs/adoption.md", "docs/roadmap.md"):  # on main since PR #17
            self.assertIn("/zouj-ai-sdlc:setup", self.text(rel), rel)
        self.assertNotIn("<plugin>/bin/sdlc setup --profile solo", self.text("docs/adoption.md"))

    def test_docs_name_stack_detection(self):
        """0009 S9 (AC-23): the docs and skills describe stack detection and every --stack choice."""
        choices = "auto|none|python|node|go|java|react|angular"
        for rel in (
            "README.md",
            "COMMANDS-QUICK-REF.md",
            "TROUBLESHOOTING.md",
            "docs/install.md",
            "skills/setup/SKILL.md",
            "skills/init/SKILL.md",
            "skills/onboard/SKILL.md",
            "templates/scaffold/Makefile",
        ):
            self.assertIn("--stack", self.text(rel), rel)
            self.assertNotIn("--stack python|node|go", self.text(rel).replace("\\|", "|"), rel)  # the old choices
        self.assertIn(f'argument-hint: "[--stack {choices}]', self.text("skills/init/SKILL.md"))
        self.assertIn(choices, self.text("COMMANDS-QUICK-REF.md").replace("\\|", "|"))
        trouble = self.text("TROUBLESHOOTING.md")
        self.assertIn("## The wrong stack was detected, or `make check` hangs", trouble)
        self.assertIn("--stack none", trouble)
        self.assertIn("stacks.py", self.text("docs/architecture.md"))
        newer = self.text("CHANGELOG.md").split("\n## [0.2.0-beta.1]", 1)[0]  # unreleased or shipped since beta.1 (0010)
        for piece in (".aiops/0009-stack-detection/", "--stack auto", "src/test/"):
            self.assertIn(piece, newer, piece)
        roadmap = self.text("docs/roadmap.md")
        self.assertNotIn("**0009, one-pass", roadmap)
        self.assertNotIn("**0010, evals", roadmap)

    def test_release_banner_is_beta(self):
        """0008 AC-4: neither the README's status line nor the newest CHANGELOG section's banner says alpha."""
        log = self.text("CHANGELOG.md")
        section = log.split("\n## [", 2)[2].split("\n## [", 1)[0]  # the newest release, after [Unreleased]
        banner = next(ln for ln in section.splitlines() if ln.startswith(">"))
        self.assertNotIn("alpha", banner.lower())
        status = next(ln for ln in self.text("README.md").splitlines() if ln.startswith("> **Status"))
        self.assertNotIn("alpha", status.lower())

    def test_no_shipped_file_names_alpha_4(self):
        """0008 AC-2: the unreleased alpha (built before beta.1) is named by no tracked file outside .aiops/ and
        evals/results/. The needle is built from parts so this test doesn't name it either."""
        needle = "alpha" + ".4"
        files = subprocess.run(["git", "ls-files"], cwd=self.root, capture_output=True, text=True).stdout.split()
        found = [
            rel
            for rel in files
            if not rel.startswith((".aiops/", "evals/results/"))
            and (self.root / rel).is_file()
            and needle in (self.root / rel).read_text(errors="replace")
        ]
        self.assertEqual(found, [], found)

    def test_changelog_has_the_release(self):
        """0007 AC-19: the release section names both intents, and every pin in the shipped docs matches plugin.json."""
        import re

        version = json.loads(self.text(".claude-plugin/plugin.json"))["version"]
        self.assertEqual(version, "0.2.0-beta.2")  # 0010: 0009 stack detection + the README funnel
        log = self.text("CHANGELOG.md")
        section = log.split(f"## [{version}]", 1)[1].split("\n## [", 1)[0]
        for piece in (".aiops/0009-stack-detection/", "--stack auto", "README"):
            self.assertIn(piece, section, piece)
        beta1 = log.split("## [0.2.0-beta.1]", 1)[1].split("\n## [", 1)[0]  # 0008's release keeps its checks
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
            self.assertIn(piece, beta1, piece)
        unreleased = log.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
        self.assertNotIn("Planned as", unreleased)  # nothing is left waiting there
        # 0010 also asserted no `### ` here, which held only at its release commit: between releases `[Unreleased]`
        # collects the next entries (0011), and the section checks above prove what moved into the release.
        self.assertIn(f"[Unreleased]: https://github.com/zoujagger/zouj-ai-sdlc/compare/v{version}...HEAD", log)
        readme = self.text("README.md")
        self.assertEqual(set(re.findall(r"0\.2\.0-(?:alpha|beta|rc)\.\d+", readme.split("\n## Lifecycle", 1)[0])), {version})
        self.assertEqual(readme.count(f"@v{version}"), 2)  # both marketplace commands
        self.assertIn(f'"ref": "v{version}"', readme)
        history = json.loads(self.text("defaults/scaffold-history.json"))
        self.assertIn(version, history)
        # a release's tree is that release (0008); between releases a changed template is `unreleased` (0009), and
        # `scripts/scaffold-history.py --check` keeps the file in step with the tree either way
        if "## [Unreleased]\n\n### " not in log:
            self.assertNotIn("unreleased", history)

    def test_profile_eval_case_is_complete(self):
        """0007 AC-21: the behavioural case exists, is listed, and its fixture is a scaffolded repo with no profile."""
        import os
        import subprocess
        import tempfile

        import re

        case = self.root / "evals" / "profile-by-setup-command"
        self.assertFalse((self.root / "evals" / "profile-by-phrase").exists())  # renamed (0007 S19)
        for rel in (
            "case.yaml",
            "fixture.sh",
            "prompt.md",
            "graders/asks-for-setup-command.md",
            "graders/config-unchanged.md",
        ):
            self.assertTrue((case / rel).is_file(), rel)
        self.assertIn("name: profile-by-setup-command", (case / "case.yaml").read_text())
        self.assertIn("scaffold_script: fixture.sh", (case / "case.yaml").read_text())
        self.assertIn("solo", (case / "prompt.md").read_text())
        asks = (case / "graders" / "asks-for-setup-command.md").read_text()
        self.assertIn("`/zouj-ai-sdlc:setup solo`", asks)
        self.assertNotIn("Setup Profile", asks + (case / "case.yaml").read_text())
        unchanged = (case / "graders" / "config-unchanged.md").read_text()
        self.assertIn(".aiops/config.json", unchanged)
        # the whole template, not one key (round 1 L3): an added profile or key policy fails the grader
        pattern = json.loads(re.search(r"^pattern: (.*)$", unchanged, re.M).group(1))
        template = json.loads(self.text("templates/scaffold/.aiops/config.json"))
        self.assertTrue(re.search(pattern, self.text("templates/scaffold/.aiops/config.json")))
        for extra in ({"profile": "solo"}, {"approval_key_policy": "any"}, {"require_signed_approvals": False}):
            self.assertFalse(re.search(pattern, json.dumps({**template, **extra}, indent=2)), extra)
        self.assertIn("| profile-by-setup-command |", self.text("evals/README.md"))
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
