"""The rule registry (defaults/rules + defaults/rules.md), `sdlc why`, and its agreement with the guard sources."""
import re
import subprocess
import sys
import unittest

from helpers import ROOT, SDLC

from sdlc_engine import rules

ID_RE = re.compile(r"^G-[A-Z]+-\d\d$")
AREAS = {"BASH", "ENV", "SEC", "FILE", "TOOL", "GATE", "LOCK", "ART", "MERGE", "DEPLOY", "TEST", "STOP", "SCAF", "FAIL"}


def why(*args):
    return subprocess.run([sys.executable, SDLC, "why", *args], capture_output=True, text=True, cwd=ROOT)


class Registry(unittest.TestCase):
    def test_well_formed(self):
        lines = [ln for ln in (ROOT / "defaults" / "rules").read_text().splitlines()
                 if ln.strip() and not ln.startswith("#")]
        ids = []
        for ln in lines:
            parts = ln.split(None, 3)
            self.assertEqual(len(parts), 4, ln)
            rid, cls, stage, summary = parts
            self.assertRegex(rid, ID_RE)
            self.assertIn(rid.split("-")[1], AREAS, ln)
            self.assertIn(stage, rules.STAGES, ln)
            self.assertIn(cls, rules.CLASSES, ln)
            self.assertTrue(stage and summary.strip(), ln)
            ids.append(rid)
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids")
        docs = rules.load()
        for rid in ids:
            self.assertTrue(docs[rid].why and docs[rid].instead, f"{rid} has no rules.md section")

    def test_only_heuristics_are_allowable(self):
        self.assertEqual(rules.ALLOWABLE, {"heuristic"})
        heur = {r.id for r in rules.load().values() if r.cls == "heuristic"}
        # decided at PR 1 review (zoujagger, 2026-11-06): G-BASH-01/02/06 sit in front of every other check, so
        # lifting them would lift everything; only sudo-style commands and env/printenv stay allowable
        self.assertEqual(heur, {"G-BASH-07", "G-ENV-03"})
        reg = rules.load()
        for rid in ("G-BASH-01", "G-BASH-02", "G-BASH-06"):
            self.assertEqual(reg[rid].cls, "safety", rid)
        self.assertEqual(reg["G-ENV-04"].cls, "secret")

    def test_malformed_registry_is_refused(self):
        for bad in ("G-X-1 heuristic every-repo x", "G-ENV-03 nosuchclass every-repo x", "G-ENV-03 heuristic",
                    "G-ENV-03 heuristic every-repo a\nG-ENV-03 heuristic every-repo b"):
            with self.assertRaises(ValueError, msg=bad):
                rules.parse_registry(bad)


class Why(unittest.TestCase):
    def test_known_id(self):
        r = why("G-ENV-03")
        self.assertEqual(r.returncode, 0, r.stderr)
        for needle in ("G-ENV-03", "class: heuristic", "protects:", "why:", "instead:", "allowable class"):
            self.assertIn(needle, r.stdout)

    def test_gate_rule_says_no_allowance(self):
        r = why("G-MERGE-03")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("class: gate", r.stdout)
        self.assertIn("no allowance", r.stdout)

    def test_front_rules_say_no_allowance(self):
        for rid in ("G-BASH-01", "G-BASH-02", "G-BASH-06", "G-ENV-04"):
            r = why(rid)
            self.assertIn("no allowance", r.stdout, rid)

    def test_sudo_warns_about_root_owned_path(self):
        self.assertIn("root-owned", why("G-BASH-07").stdout)

    def test_stages_are_readable_and_accurate(self):
        for rid in rules.load():
            out = why(rid).stdout
            self.assertNotRegex(out, r"protects: [a-z]+(-[a-z]+)+\n", rid)   # no raw slug
        self.assertIn("initialized", why("G-SEC-02").stdout)               # check_bash runs only in .aiops repos
        self.assertIn("every repo", why("G-SEC-04").stdout)                # guard-files.sh is always on

    def test_lifecycle_commands_are_documented(self):
        self.assertIn("uninstall", why("G-GATE-07").stdout)
        for name in ("upgrade", "repair", "uninstall"):
            self.assertIn(name, why("G-SCAF-01").stdout)

    def test_allowable_rule_explains_the_allowance(self):
        out = why("G-ENV-03").stdout
        self.assertIn(".aiops/config/allowed-commands", out)
        self.assertIn("G-ENV-03 <the exact command>", out)
        self.assertIn("every other rule still applies", out)

    def test_unknown_id_near_matches(self):
        r = why("G-ENV-3")
        self.assertEqual(r.returncode, 1)
        self.assertIn("G-ENV-03", r.stderr)

    def test_lowercase_and_missing_arg(self):
        self.assertEqual(why("g-env-03").returncode, 0)
        self.assertEqual(why().returncode, 1)


class Coverage(unittest.TestCase):
    """defaults/rules and the guard sources agree: every id a hook emits is registered, and every live id is emitted."""
    SOURCES = sorted((ROOT / "hooks").glob("*.sh")) + sorted((ROOT / "lib" / "sdlc_engine").glob("*.py"))

    def emitted(self):
        found = {}
        for f in self.SOURCES:
            for rid in re.findall(r"\bG-[A-Z]+-\d\d\b", f.read_text()):
                found.setdefault(rid, f.name)
        return found

    def test_sources_and_registry_agree(self):
        reg = rules.load()
        emitted = self.emitted()
        unregistered = sorted(f"{rid} ({where})" for rid, where in emitted.items() if rid not in reg)
        self.assertEqual(unregistered, [], "ids used in hooks/lib but missing from defaults/rules")
        live = {rid for rid, r in reg.items() if r.cls != "retired"}
        self.assertEqual(sorted(live - set(emitted)), [], "registered ids that no hook emits")

    def test_only_heuristic_rules_consult_allowances(self):
        # guard-bash: `heuristic <id>` (which consults allowed-commands) is used exactly for the heuristic class
        src = (ROOT / "hooks" / "guard-bash.sh").read_text()
        via_helper = set(re.findall(r"&& heuristic (G-[A-Z]+-\d\d)", src))
        heur = {rid for rid, r in rules.load().items() if r.cls == "heuristic"}
        self.assertEqual(via_helper, heur)
        for rid in heur:
            self.assertNotRegex(src, rf"block {rid}\b", rid)

    def test_every_block_call_names_an_id(self):
        for f in (ROOT / "hooks").glob("*.sh"):
            for n, line in enumerate(f.read_text().splitlines(), 1):
                code = line.split("#", 1)[0]
                if re.search(r"(^|[;&|]\s*|\s)block\s+\S", code) and "block()" not in code:
                    self.assertRegex(code, r"block\s+(G-[A-Z]+-\d\d|\"'\$v'|\"\$@\")", f"{f.name}:{n}: {line.strip()}")
        src = (ROOT / "lib" / "sdlc_engine" / "guards.py").read_text()
        for m in re.finditer(r"_block\((?!rule_id)([^,]+),", src):
            self.assertRegex(m.group(1), r'^"G-[A-Z]+-\d\d"', m.group(0))


class Allowance(unittest.TestCase):
    """rules.allowed / allowance_problems: an exact single-line command, one heuristic rule per entry (0004 S5)."""
    def setUp(self):
        import tempfile
        from pathlib import Path
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".aiops" / "config").mkdir(parents=True)
        self.f = self.root / ".aiops" / "config" / "allowed-commands"

    def tearDown(self):
        self._tmp.cleanup()

    def entries(self, text):
        self.f.write_text(text)

    def test_exact_match_only(self):
        self.entries("# human-owned\nG-ENV-03 ls env\nG-BASH-07 sudo systemctl status docker   \n")
        self.assertTrue(rules.allowed(self.root, "G-ENV-03", "ls env"))
        self.assertTrue(rules.allowed(self.root, "G-ENV-03", "  ls env\n"))        # surrounding whitespace trimmed
        self.assertTrue(rules.allowed(self.root, "G-BASH-07", "sudo systemctl status docker"))
        for cmd in ("ls  env", "ls env; git push --force", "ls env x", "LS ENV", "ls env && true", "ls"):
            self.assertFalse(rules.allowed(self.root, "G-ENV-03", cmd), cmd)
        self.assertFalse(rules.allowed(self.root, "G-BASH-07", "ls env"))          # the entry names one rule
        self.assertFalse(rules.allowed(self.root, "g-env-03", "ls env"))           # ids are exact too

    def test_full_environment_dump_never_allowed(self):
        self.entries("G-ENV-03 printenv\nG-ENV-03 env\nG-ENV-03 env -0\nG-ENV-03 FOO=1 env\nG-ENV-03 printenv PATH\n"
                     "G-ENV-03 ls env\n")
        for cmd in ("printenv", "env", "env -0", "FOO=1 env"):
            self.assertFalse(rules.allowed(self.root, "G-ENV-03", cmd), cmd)
        # review round 2: options with arguments, wrappers, grouping, redirection and substitution are dumps too
        for cmd in ("env -u HOME", "env -C /tmp", "env --chdir /tmp", "command env", "nice env", "exec env",
                    "time printenv", "nohup env", "timeout 5 env", "(env)", "{ env; }", "env > /tmp/x",
                    "echo $(env)", "cat <(env)", "echo `printenv`", "printenv -0", "/usr/bin/env", "printenv | cat"):
            self.assertTrue(rules.dumps_environment(cmd), cmd)
        for cmd in ("printenv PATH", "printenv HOME USER", "ls env", "python -m venv env"):
            self.assertFalse(rules.dumps_environment(cmd), cmd)
        for cmd in ("printenv PATH", "ls env"):
            self.assertTrue(rules.allowed(self.root, "G-ENV-03", cmd), cmd)
        probs = "\n".join(rules.allowance_problems(self.f.read_text()))
        self.assertIn("line 1", probs)
        self.assertIn("whole environment", probs)
        self.assertNotIn("line 5", probs)

    def test_only_safe_env_forms(self):
        """0005 S2 (gap 6): only `printenv NAME…` or commands that never run env/printenv are allowable."""
        for cmd in ("printenv PATH", "printenv HOME USER", "ls env", "cd env", "python -m venv env",
                    "python3 -m venv env", "virtualenv env", "cat env/pyvenv.cfg", "ls env && cd env"):
            self.assertTrue(rules.safe_env_command(cmd), cmd)
        # review round 1: source runs its argument; every simple command must be safe; no secret-named printenv
        for cmd in ("source env/bin/activate", ". env/bin/activate", "source env", "cat env | sh",
                    "ls env && export -p", "ls env; set", "printenv GITHUB_TOKEN", "printenv AWS_SECRET_ACCESS_KEY",
                    "ls env && make"):
            self.assertFalse(rules.safe_env_command(cmd), cmd)
        for cmd in ("env", "printenv", "env FOO=1 make", "bash -c env", "env env", "xargs env",
                    "if true; then env; fi", "env>/tmp/x", "echo $(printenv)", "nice env", "printenv -0",
                    "cat <(env)", "watch env", "sh -c printenv", "eval env", "ls env; env", "find . -exec env \\;",
                    "ls env > /tmp/x", "python -c 'import os; print(os.environ)' env"):
            self.assertFalse(rules.safe_env_command(cmd), cmd)
        self.entries("G-ENV-03 ls env\nG-ENV-03 bash -c env\nG-ENV-03 env FOO=1 make\n")
        self.assertTrue(rules.allowed(self.root, "G-ENV-03", "ls env"))
        self.assertFalse(rules.allowed(self.root, "G-ENV-03", "bash -c env"))
        probs = "\n".join(rules.allowance_problems(self.f.read_text()))
        self.assertIn("line 2", probs)
        self.assertIn("line 3", probs)
        self.assertNotIn("line 1", probs)

    def test_problems_never_echo_unrecognised_text(self):
        probs = "\n".join(rules.allowance_problems("-----BEGIN OPENSSH PRIVATE KEY-----\n  ssh-ed25519 AAAAsecret x\n"))
        self.assertNotIn("OPENSSH", probs)
        self.assertNotIn("AAAAsecret", probs)
        self.assertIn("line 1", probs)

    def test_multiline_command_never_allowed(self):
        self.entries("G-ENV-03 ls env\n")
        self.assertFalse(rules.allowed(self.root, "G-ENV-03", "ls env\nrm -rf .aiops"))
        self.assertFalse(rules.allowed(self.root, "G-ENV-03", "ls env\r"))

    def test_non_heuristic_ids_never_allowed(self):
        reg = rules.load()
        lines = "".join(f"{rid} git push origin main\n" for rid in reg)
        self.entries(lines)
        for rid, r in reg.items():
            if r.cls != "heuristic":
                self.assertFalse(rules.allowed(self.root, rid, "git push origin main"), rid)

    def test_no_file_or_unknown_id(self):
        self.assertFalse(rules.allowed(self.root, "G-ENV-03", "ls env"))
        self.entries("G-ENV-03 ls env\n")
        self.assertFalse(rules.allowed(self.root, "G-NOPE-01", "ls env"))

    def test_problems_name_line_and_class(self):
        probs = rules.allowance_problems(
            "# comment\n\nG-ENV-03 ls env\nG-MERGE-03 git push origin main\nG-SEC-06 cat .env\nG-NOPE-01 x\n"
            "G-ENV-03\nnot-an-id ls\nG-BASH-01 eval eval eval eval true\n")
        text = "\n".join(probs)
        self.assertEqual(len(probs), 6, text)
        self.assertIn("line 4", text)
        self.assertIn("G-MERGE-03 is a gate rule", text)
        self.assertIn("G-SEC-06 is a secret rule", text)
        self.assertIn("G-BASH-01 is a safety rule", text)
        self.assertIn("unknown rule id G-NOPE-01", text)
        self.assertIn("line 7", text)                                               # an id with no command
        self.assertNotIn("line 3", text)                                            # the valid entry
        self.assertEqual(rules.allowance_problems("G-ENV-03 ls env\n"), [])


class History(unittest.TestCase):
    """defaults/scaffold-history.json holds every release's scaffold, and the current one (0004 S10)."""
    def test_current_scaffold_in_history(self):
        import json
        from sdlc_engine import lifecycle
        hist = json.loads((ROOT / "defaults" / "scaffold-history.json").read_text())
        for v in ("0.1.0", "0.2.0-alpha.1", "0.2.0-alpha.2"):
            self.assertIn(v, hist)
        key = lifecycle.history_key()
        self.assertIn(key, hist, "regenerate: python3 scripts/scaffold-history.py")
        current = {rel: lifecycle.sha256_bytes(lifecycle.normalize((ROOT / "templates" / "scaffold" / rel).read_bytes()))
                   for rel in lifecycle.scaffold_paths()}
        recorded = {rel: h for rel, h in hist[key].items() if "+" not in rel}
        self.assertEqual(recorded, current, "regenerate: python3 scripts/scaffold-history.py")

    def test_normalize_undoes_the_ref_pin(self):
        from sdlc_engine import lifecycle
        for pinned in (b"      ZOUJ_SDLC_REF: v0.1.0        # pin", b"      ZOUJ_SDLC_REF: " + b"a" * 40 + b"   # x",
                       b'        "ref": "v0.2.0-alpha.2"'):
            self.assertIn(b"__ZOUJ_SDLC_REF__", lifecycle.normalize(pinned), pinned)


class Skills(unittest.TestCase):
    """/zouj-ai-sdlc:configure is a thin, read-only wrapper over setup (0004 S17)."""
    def test_configure_is_read_only(self):
        f = ROOT / "skills" / "configure" / "SKILL.md"
        self.assertTrue(f.is_file())
        text = f.read_text()
        self.assertRegex(text, r"(?m)^name: configure$")
        self.assertRegex(text, r"(?m)^description: .+")
        ran = set(re.findall(r"Run `(sdlc [a-z-]+[^`]*)`", text))
        self.assertTrue(ran)
        for cmd in ran:
            self.assertRegex(cmd, r"^sdlc (list-installed|doctor|setup --profile <\w+> --dry-run)$", cmd)
        self.assertIn("-I <plugin>/bin/sdlc setup --profile", text)     # the human's terminal command, at the end
        self.assertLess(text.index("--dry-run"), text.index("-I <plugin>/bin/sdlc setup --profile"))
        for word in ("--yes", "uninstall", "approve"):
            self.assertNotIn(f"Run `sdlc {word}", text)

    def test_skills_mention_the_lifecycle(self):
        setup = (ROOT / "skills" / "setup" / "SKILL.md").read_text()
        status = (ROOT / "skills" / "status" / "SKILL.md").read_text()
        for cmd in ("sdlc list-installed", "sdlc upgrade"):
            self.assertIn(cmd, setup, cmd)
        self.assertIn("sdlc why", status)


class Stages0005(unittest.TestCase):
    def test_safety_rules_every_repo(self):
        for rid in ("G-SEC-01", "G-TOOL-02", "G-TOOL-04", "G-TOOL-05", "G-BASH-01", "G-ENV-05"):
            self.assertIn("in every repo", why(rid).stdout, rid)
        self.assertIn("class: secret", why("G-ENV-05").stdout)


if __name__ == "__main__":
    unittest.main()
