"""The dsl part's validator, scripts/validate-dsl.py (0012 S2, AC-2): domain-neutral JSON models, stdlib only."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

SCRIPT = ROOT / "templates" / "scaffold" / "scripts" / "validate-dsl.py"

MACHINE = {
    "dsl": 1,
    "kind": "state_machine",
    "name": "ticket",
    "states": ["open", "in_progress", "closed"],
    "initial": "open",
    "final": ["closed"],
    "transitions": [
        {"from": "open", "to": "in_progress", "event": "start"},
        {"from": "in_progress", "to": "closed", "event": "resolve", "guard": "all checks done"},
    ],
}
RULES = {
    "dsl": 1,
    "kind": "rules",
    "name": "limits",
    "rules": [{"id": "R1", "when": "a request exceeds the daily limit", "then": "the request is refused"}],
}
WORKFLOW = {
    "dsl": 1,
    "kind": "workflow",
    "name": "review",
    "start": "submit",
    "steps": [{"id": "submit", "next": ["check"]}, {"id": "check", "next": ["done"]}, {"id": "done"}],
}


class ValidateDsl(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / "domain").mkdir()

    def put(self, name, model):
        text = model if isinstance(model, str) else json.dumps(model, indent=2)
        (self.root / "domain" / name).write_text(text)

    def run_it(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], cwd=self.root, capture_output=True, text=True, timeout=30
        )

    def problems(self, model, name="m.dsl.json"):
        self.put(name, model)
        r = self.run_it()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        return r.stdout

    def changed(self, base, **changes):
        model = json.loads(json.dumps(base))
        for key, value in changes.items():
            if value is None:
                model.pop(key, None)
            else:
                model[key] = value
        return model

    def test_valid_models_of_every_kind(self):
        self.put("ticket.dsl.json", MACHINE)
        self.put("limits.dsl.json", RULES)
        self.put("review.dsl.json", WORKFLOW)
        self.put("README.md", "# not a model\n")  # other files are ignored
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("validate-dsl: 3 model(s) ok", r.stdout)

    def test_no_directory_is_skipped(self):
        (self.root / "domain").rmdir()
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("validate-dsl: no domain/ - skipped", r.stdout)

    def test_invalid_json(self):
        out = self.problems('{"dsl": 1,\n  "kind": }')
        self.assertRegex(out, r"domain/m\.dsl\.json:2:11: invalid JSON: ")

    def test_header_problems(self):
        self.assertIn("domain/m.dsl.json: $: expected an object", self.problems("[1, 2]"))
        self.assertIn("domain/m.dsl.json: $.dsl: expected 1", self.problems(self.changed(RULES, dsl=2)))
        self.assertIn(
            'domain/m.dsl.json: $.kind: unknown kind "entity" (state_machine, rules or workflow)',
            self.problems(self.changed(RULES, kind="entity")),
        )
        self.assertIn("domain/m.dsl.json: $.name: expected an identifier", self.problems(self.changed(RULES, name="1 x")))
        self.assertIn("domain/m.dsl.json: $.colour: unknown key", self.problems(self.changed(RULES, colour="red")))
        self.assertIn("domain/m.dsl.json: $.rules: missing", self.problems(self.changed(RULES, rules=None)))

    def test_duplicate_key_in_an_object(self):
        out = self.problems('{"dsl": 1, "kind": "rules", "name": "a", "name": "b", "rules": []}')
        self.assertIn('domain/m.dsl.json: $: duplicate key "name"', out)

    def test_state_machine_references(self):
        bad = self.changed(MACHINE)
        bad["transitions"].append({"from": "closed", "to": "Shipped", "event": "ship"})
        self.assertIn('domain/m.dsl.json: $.transitions[2].to: unknown state "Shipped"', self.problems(bad))
        dup = self.changed(MACHINE)
        dup["transitions"].append({"from": "open", "to": "closed", "event": "start"})
        self.assertIn(
            'domain/m.dsl.json: $.transitions[2]: duplicate transition from "open" on "start"', self.problems(dup)
        )
        self.assertIn("domain/m.dsl.json: $.initial: missing", self.problems(self.changed(MACHINE, initial=None)))
        self.assertIn(
            'domain/m.dsl.json: $.initial: unknown state "new"', self.problems(self.changed(MACHINE, initial="new"))
        )
        self.assertIn(
            'domain/m.dsl.json: $.final[0]: unknown state "gone"', self.problems(self.changed(MACHINE, final=["gone"]))
        )
        self.assertIn(
            'domain/m.dsl.json: $.states[2]: duplicate state "open"',
            self.problems(self.changed(MACHINE, states=["open", "closed", "open"])),
        )
        bad_key = self.changed(MACHINE)
        bad_key["transitions"][0]["on"] = "x"
        self.assertIn("domain/m.dsl.json: $.transitions[0].on: unknown key", self.problems(bad_key))

    def test_rules(self):
        dup = self.changed(RULES)
        dup["rules"].append({"id": "R1", "when": "x", "then": "y"})
        self.assertIn('domain/m.dsl.json: $.rules[1].id: duplicate id "R1"', self.problems(dup))
        empty = self.changed(RULES)
        empty["rules"][0]["when"] = " "
        self.assertIn("domain/m.dsl.json: $.rules[0].when: expected non-empty text", self.problems(empty))
        self.assertIn("domain/m.dsl.json: $.rules: expected a non-empty list", self.problems(self.changed(RULES, rules=[])))

    def test_workflow_references(self):
        bad = self.changed(WORKFLOW)
        bad["steps"][1]["next"] = ["nowhere"]
        self.assertIn('domain/m.dsl.json: $.steps[1].next[0]: unknown step "nowhere"', self.problems(bad))
        self.assertIn(
            'domain/m.dsl.json: $.start: unknown step "begin"', self.problems(self.changed(WORKFLOW, start="begin"))
        )

    def test_duplicate_name_across_files(self):
        self.put("a.dsl.json", RULES)
        out = self.problems(self.changed(MACHINE, name="limits"), name="b.dsl.json")
        self.assertIn('domain/b.dsl.json: $.name: "limits" is also the name in domain/a.dsl.json', out)

    def test_every_problem_is_reported(self):
        bad = self.changed(MACHINE, initial="new", colour="red")
        out = self.problems(bad)
        self.assertIn("$.initial", out)
        self.assertIn("$.colour", out)
        self.assertIn("validate-dsl: 2 problem(s)", out)

    def test_a_link_is_not_followed(self):
        target = self.root / "elsewhere.json"
        target.write_text(json.dumps(RULES))
        os.symlink(target, self.root / "domain" / "m.dsl.json")
        r = self.run_it()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("domain/m.dsl.json: not a regular file (links are not followed)", r.stdout)

    def test_a_large_file_is_refused(self):
        out = self.problems('{"pad": "' + "x" * (1024 * 1024) + '"}')
        self.assertIn("domain/m.dsl.json: larger than 1 MiB", out)

    def test_deep_nesting_is_a_problem_not_a_crash(self):
        for depth in (100, 100000):
            out = self.problems("[" * depth + "]" * depth)
            self.assertIn("domain/m.dsl.json: nested deeper than 64 levels", out, depth)

    def test_another_directory(self):
        (self.root / "model").mkdir()
        (self.root / "model" / "x.dsl.json").write_text(json.dumps(RULES))
        r = self.run_it("model")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("validate-dsl: 1 model(s) ok", r.stdout)


if __name__ == "__main__":
    unittest.main()
