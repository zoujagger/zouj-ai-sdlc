"""The rule registry (defaults/rules + defaults/rules.md), `sdlc why`, and its agreement with the guard sources."""
import re
import subprocess
import sys
import unittest

from helpers import ROOT, SDLC

from sdlc_engine import rules

ID_RE = re.compile(r"^G-[A-Z]+-\d\d$")


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
        self.assertEqual(heur, {"G-BASH-01", "G-BASH-02", "G-BASH-06", "G-BASH-07", "G-ENV-03"})

    def test_malformed_registry_is_refused(self):
        for bad in ("G-X-1 heuristic every-repo x", "G-ENV-03 nosuchclass every-repo x", "G-ENV-03 heuristic",
                    "G-ENV-03 heuristic every-repo a\nG-ENV-03 heuristic every-repo b"):
            with self.assertRaises(ValueError, msg=bad):
                rules.parse_registry(bad)


class Why(unittest.TestCase):
    def test_known_id(self):
        r = why("G-ENV-03")
        self.assertEqual(r.returncode, 0, r.stderr)
        for needle in ("G-ENV-03", "class: heuristic", "protects:", "why:", "instead:", "allowed-commands"):
            self.assertIn(needle, r.stdout)

    def test_gate_rule_says_no_allowance(self):
        r = why("G-MERGE-03")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("class: gate", r.stdout)
        self.assertIn("no allowance", r.stdout)

    def test_unknown_id_near_matches(self):
        r = why("G-ENV-3")
        self.assertEqual(r.returncode, 1)
        self.assertIn("G-ENV-03", r.stderr)

    def test_lowercase_and_missing_arg(self):
        self.assertEqual(why("g-env-03").returncode, 0)
        self.assertEqual(why().returncode, 1)


if __name__ == "__main__":
    unittest.main()
