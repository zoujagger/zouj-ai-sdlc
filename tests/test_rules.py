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

    def test_no_text_ahead_of_the_code(self):
        # PR 1 ships no allowance reader and no upgrade/repair/uninstall: nothing may promise them yet
        text = (ROOT / "defaults" / "rules.md").read_text() + why("G-ENV-03").stdout
        for future in ("uninstall", "upgrade", "repair", "allowed-commands"):
            self.assertNotIn(future, text, future)

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

    def test_every_block_call_names_an_id(self):
        for f in (ROOT / "hooks").glob("*.sh"):
            for n, line in enumerate(f.read_text().splitlines(), 1):
                code = line.split("#", 1)[0]
                if re.search(r"(^|[;&|]\s*|\s)block\s+\S", code) and "block()" not in code:
                    self.assertRegex(code, r"block\s+(G-[A-Z]+-\d\d|\"'\$v')", f"{f.name}:{n}: {line.strip()}")
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


if __name__ == "__main__":
    unittest.main()
