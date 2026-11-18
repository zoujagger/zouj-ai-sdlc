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


class Node(StackCase):
    """S2: Node, React and Angular from the repo's own scripts (AC-4 to AC-8)."""

    def test_pnpm_scripts(self):
        self.package({"lint": "eslint .", "test": "vitest run", "build": "tsc -p .", "typecheck": "tsc --noEmit"})
        self.put("pnpm-lock.yaml")
        det = self.detect()
        self.assertEqual(det.kind, "node")
        self.assertEqual(
            det.recipes,
            {"lint": "pnpm run lint", "typecheck": "pnpm run typecheck", "test": "pnpm run test", "build": "pnpm run build"},
        )
        self.assertEqual(det.evidence, ["package.json", "pnpm-lock.yaml"])

    def test_package_manager_from_lockfile(self):
        self.package({"test": "jest"})
        self.assertEqual(self.detect().recipes["test"], "npm run test")
        self.put("bun.lockb")
        self.assertEqual(self.detect().recipes["test"], "bun run test")
        self.put("yarn.lock")
        self.assertEqual(self.detect().recipes["test"], "yarn run test")

    def test_react_cra_and_vite(self):
        self.package({"test": "react-scripts test", "build": "react-scripts build"}, deps={"react": "^18.3.1"})
        self.put("yarn.lock")
        det = self.detect()
        self.assertEqual(det.kind, "react")
        self.assertEqual(det.label, "React")
        self.assertEqual(det.recipes["test"], "CI=true yarn run test")
        (self.root / "yarn.lock").unlink()
        self.package({"test:ci": "vitest run", "test": "vitest"}, dev={"react": "^18.3.1"})
        det = self.detect()
        self.assertEqual(det.kind, "react")
        self.assertEqual(det.recipes["test"], "npm run test:ci")

    def test_angular_karma_and_not(self):
        self.package({"test": "ng test", "lint": "ng lint", "build": "ng build"}, deps={"@angular/core": "^18.0.0"})
        karma = {"projects": {"app": {"architect": {"test": {"builder": "@angular-devkit/build-angular:karma"}}}}}
        self.put("angular.json", json.dumps(karma))
        det = self.detect()
        self.assertEqual(det.kind, "angular")
        self.assertEqual(det.label, "Angular")
        self.assertEqual(det.recipes["test"], "npm run test -- --watch=false --browsers=ChromeHeadless")
        self.assertIn("angular.json", det.evidence)
        jest = {"projects": {"app": {"architect": {"test": {"builder": "@angular-builders/jest:run"}}}}}
        self.put("angular.json", json.dumps(jest))
        self.assertEqual(self.detect().recipes["test"], "npm run test -- --watch=false")

    def test_tsc_fallback_and_npm_placeholder(self):
        self.package({"test": 'echo "Error: no test specified" && exit 1'})
        det = self.detect()
        self.assertNotIn("test", det.recipes)
        self.assertNotIn("typecheck", det.recipes)
        self.put("tsconfig.json", "{}")
        det = self.detect()
        self.assertEqual(det.recipes["typecheck"], "npx tsc --noEmit")
        self.assertIn("tsconfig.json", det.evidence)

    def test_script_order(self):
        self.package({"prettier": "prettier -w .", "format": "biome format", "type-check": "tsc", "tsc": "tsc -b"})
        det = self.detect()
        self.assertEqual(det.recipes["format"], "npm run format")
        self.assertEqual(det.recipes["typecheck"], "npm run type-check")

    def test_unsafe_script_names(self):
        bodies = {
            "lint;rm -rf ~": "BODY-ONE",
            "$(x)": "BODY-TWO",
            "a\nb": "BODY-THREE",
            "-x": "BODY-FOUR",
            "test": "BODY-FIVE $(curl evil)",
        }
        self.package(bodies)
        det = self.detect()
        self.assertEqual(det.recipes, {"test": "npm run test"})  # only the safe name, never a body
        for cmd in det.recipes.values():
            for body in ("BODY", "curl", "rm -rf", "$("):
                self.assertNotIn(body, cmd)

    def test_forced_kind_reads_scripts(self):
        self.package({"test": "react-scripts test"})
        det = self.detect(force="react")
        self.assertEqual(det.kind, "react")
        self.assertEqual(det.recipes["test"], "CI=true npm run test")

    def test_scripts_not_an_object(self):
        self.put("package.json", json.dumps({"scripts": ["lint"]}))
        det = self.detect()
        self.assertEqual(det.kind, "node")
        self.assertEqual(det.recipes, {})


if __name__ == "__main__":
    unittest.main()
