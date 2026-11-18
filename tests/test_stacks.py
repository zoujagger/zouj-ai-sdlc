"""Stack auto-detection for the Makefile contract (0009): lib/sdlc_engine/stacks.py."""

import builtins
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (puts lib/ on sys.path)
from sdlc_engine import stacks


class StackCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def put(self, rel, text="", mode=None):
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
        if mode is not None:
            f.chmod(mode)
        return f

    def package(self, scripts=None, deps=None, dev=None):
        data = {"name": "app", "scripts": scripts or {}}
        if deps:
            data["dependencies"] = deps
        if dev:
            data["devDependencies"] = dev
        self.put("package.json", json.dumps(data))

    def detect(self, force=None):
        return stacks.detect(self.root, force)


POM = """<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  {parent}
  <artifactId>demo</artifactId>
  <build><plugins>{plugins}</plugins></build>
</project>
"""
BOOT_PARENT = (
    "<parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId>"
    "<version>3.3.0</version></parent>"
)


def pom(parent="", plugins=""):
    return POM.format(parent=parent, plugins=plugins)


class Family(StackCase):
    """S1: the result type, the family choice and the reading rules (AC-10, AC-11)."""

    def test_nothing_to_detect(self):
        det = self.detect()
        self.assertIsNone(det.kind)
        self.assertEqual(det.recipes, {})
        self.assertIn("no stack", det.note)

    def test_ambiguous_root(self):
        self.put("pom.xml", pom())
        self.put("go.mod", "module x\n")
        det = self.detect()
        self.assertIsNone(det.kind)
        self.assertEqual(det.recipes, {})
        for piece in ("java", "go", "--stack"):
            self.assertIn(piece, det.note)

    def test_unreadable_and_linked_files(self):
        outside = Path(tempfile.mkdtemp())
        try:
            (outside / "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}))
            os.symlink(outside / "package.json", self.root / "package.json")
            det = self.detect()
            self.assertIsNone(det.kind)  # a link is never followed
            (self.root / "package.json").unlink()
            self.put("package.json", json.dumps({"scripts": {"test": "x" * (2 << 20)}}))  # over 1 MiB
            self.assertIsNone(self.detect().kind)
            self.put("package.json", "{not json")
            det = self.detect()
            self.assertIsNone(det.kind)
            self.assertIn("package.json", det.note)
            (self.root / "package.json").unlink()
            self.put("pom.xml", "<project><unclosed>")
            det = self.detect()
            self.assertIsNone(det.kind)
            self.assertIn("pom.xml", det.note)
        finally:
            for f in outside.iterdir():
                f.unlink()
            outside.rmdir()

    def test_marker_in_a_subdirectory_is_ignored(self):
        self.put("frontend/package.json", json.dumps({"scripts": {"test": "jest"}}))
        self.assertIsNone(self.detect().kind)

    def test_reads_only_markers(self):
        for rel, text in (
            ("package.json", json.dumps({"scripts": {"lint": "eslint ."}})),
            ("tsconfig.json", "{}"),
            ("pnpm-lock.yaml", ""),
            (".npmrc", "//registry/:_authToken=secret"),
            (".env", "TOKEN=secret"),
            ("settings.xml", "<settings/>"),
        ):
            self.put(rel, text)
        opened = []
        real_open = builtins.open

        def spy(file, *a, **k):
            opened.append(Path(file))
            return real_open(file, *a, **k)

        with mock.patch("builtins.open", spy):
            self.detect()
        self.assertTrue(opened)
        for path in opened:
            self.assertEqual(path.parent, self.root, path)
            self.assertIn(path.name, stacks.MARKERS, path)
        for secret in (".npmrc", ".env", "settings.xml"):
            self.assertNotIn(secret, stacks.MARKERS)

    def test_kinds_and_choices(self):
        self.assertEqual(stacks.KINDS, ("python", "node", "go", "java", "react", "angular"))
        self.assertEqual(stacks.CHOICES, ("auto", "none") + stacks.KINDS)


if __name__ == "__main__":
    unittest.main()
