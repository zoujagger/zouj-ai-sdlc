"""Stack auto-detection for the Makefile contract (0009): lib/sdlc_engine/stacks.py."""

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
        real_open = os.open

        def spy(file, *a, **k):
            opened.append(Path(file))
            return real_open(file, *a, **k)

        with mock.patch("builtins.open", side_effect=AssertionError("detection reads through os.open")):
            with mock.patch("os.open", spy):
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


class Java(StackCase):
    """S3: Maven and Gradle, the Spring Boot label, the wrapper, lint/format only when configured (AC-1 to AC-3)."""

    def test_spring_boot_maven_wrapper(self):
        self.put("pom.xml", pom(BOOT_PARENT))
        self.put("mvnw", "#!/bin/sh\n", mode=0o755)
        det = self.detect()
        self.assertEqual(det.kind, "java")
        self.assertEqual(det.label, "Java · Spring Boot · Maven")
        self.assertEqual(
            det.recipes,
            {
                "typecheck": "./mvnw -B -q compile",
                "test": "./mvnw -B -q test",
                "build": "./mvnw -B -q package -DskipTests",
            },
        )
        self.assertEqual(det.evidence, ["pom.xml", "mvnw"])

    def test_maven_checkstyle_spotless_no_wrapper(self):
        plugins = (
            "<plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-checkstyle-plugin</artifactId></plugin>"
            "<plugin><groupId>com.diffplug.spotless</groupId><artifactId>spotless-maven-plugin</artifactId></plugin>"
        )
        self.put("pom.xml", pom(plugins=plugins))
        det = self.detect()
        self.assertEqual(det.label, "Java · Maven")
        self.assertEqual(det.recipes["lint"], "mvn -B -q checkstyle:check")
        self.assertEqual(det.recipes["format"], "mvn -B -q spotless:apply")
        self.assertEqual(det.recipes["test"], "mvn -B -q test")
        self.assertEqual(list(det.recipes), ["format", "lint", "typecheck", "test", "build"])

    def test_non_executable_wrapper_falls_back(self):
        self.put("pom.xml", pom())
        self.put("mvnw", "#!/bin/sh\n", mode=0o644)
        self.assertEqual(self.detect().recipes["test"], "mvn -B -q test")

    def test_gradle_kts_spring_boot(self):
        self.put("build.gradle.kts", 'plugins {\n  java\n  id("org.springframework.boot") version "3.3.0"\n}\n')
        self.put("gradlew", "#!/bin/sh\n", mode=0o755)
        det = self.detect()
        self.assertEqual(det.label, "Java · Spring Boot · Gradle")
        self.assertEqual(
            det.recipes,
            {"typecheck": "./gradlew -q classes", "test": "./gradlew -q test", "build": "./gradlew -q assemble"},
        )
        self.assertEqual(det.evidence, ["build.gradle.kts", "gradlew"])

    def test_gradle_checkstyle_spotless(self):
        self.put("build.gradle", "plugins {\n  id 'java'\n  id 'checkstyle'\n  id 'com.diffplug.spotless' version '6.25.0'\n}\n")
        det = self.detect()
        self.assertEqual(det.label, "Java · Gradle")
        self.assertEqual(det.recipes["lint"], "gradle -q checkstyleMain")
        self.assertEqual(det.recipes["format"], "gradle -q spotlessApply")

    def test_spring_boot_maven_plugin_without_parent(self):
        plugins = "<plugin><groupId>org.springframework.boot</groupId><artifactId>spring-boot-maven-plugin</artifactId></plugin>"
        self.put("pom.xml", pom(plugins=plugins))
        self.assertEqual(self.detect().label, "Java · Spring Boot · Maven")


class Presets(StackCase):
    """S3: Python and Go keep their presets (AC-9)."""

    def preset(self, name):
        out = {}
        for line in (stacks.STACKS_DIR / f"{name}.recipes").read_text().splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and not parts[0].startswith("#"):
                out[parts[0]] = parts[1]
        return out

    def test_python_and_go(self):
        self.put("pyproject.toml", "[project]\nname = 'x'\n")
        det = self.detect()
        self.assertEqual((det.kind, det.label), ("python", "Python"))
        self.assertEqual(det.recipes, self.preset("python"))
        self.assertEqual(det.evidence, ["pyproject.toml"])
        (self.root / "pyproject.toml").unlink()
        self.put("go.mod", "module x\n")
        det = self.detect()
        self.assertEqual((det.kind, det.label), ("go", "Go"))
        self.assertEqual(det.recipes, self.preset("go"))


class Robustness(StackCase):
    """Review round 1: parse failures, races, encodings and the recipe grammar."""

    def test_deep_nesting_is_absent_not_a_crash(self):
        self.put("package.json", "[" * 200000 + "]" * 200000)
        det = self.detect()
        self.assertIsNone(det.kind)
        self.assertIn("package.json", det.note)
        self.put("package.json", '{"a":' * 100000 + "1" + "}" * 100000)
        self.assertIsNone(self.detect().kind)

    def test_xml_with_a_doctype_is_refused(self):
        self.put("pom.xml", '<?xml version="1.0"?><!DOCTYPE p [<!ENTITY x "y">]><project><artifactId>&x;</artifactId></project>')
        det = self.detect()
        self.assertIsNone(det.kind)
        self.assertIn("pom.xml", det.note)

    def test_utf8_bom(self):
        self.put("package.json", "\ufeff" + json.dumps({"scripts": {"test": "jest"}}))
        self.assertEqual(self.detect().recipes, {"test": "npm run test"})

    def test_swap_after_the_check_is_not_followed(self):
        """A link or FIFO put in place after _regular() is neither followed nor waited on."""
        secret = self.put("elsewhere.json", json.dumps({"scripts": {"test": "jest"}}))
        link = self.root / "package.json"
        os.symlink(secret, link)
        with mock.patch.object(stacks, "_regular", return_value=link):
            self.assertIsNone(stacks._read(self.root, "package.json"))
        link.unlink()
        os.mkfifo(link)
        with mock.patch.object(stacks, "_regular", return_value=link):
            self.assertIsNone(stacks._read(self.root, "package.json"))  # O_NONBLOCK, then S_ISREG: no hang

    def test_unparsable_marker_counts_as_absent(self):
        self.put("pom.xml", pom())
        self.put("package.json", "nope")
        det = self.detect()
        self.assertEqual(det.kind, "java")
        self.assertIn("package.json", det.note)

    def test_unreadable_angular_json_is_named(self):
        self.package({"test": "ng test"})
        self.put("angular.json", "{broken")
        det = self.detect()
        self.assertEqual(det.kind, "angular")
        self.assertEqual(det.recipes["test"], "npm run test -- --watch=false")
        self.assertIn("angular.json", det.note)

    def test_emittable_grammar(self):
        """Every recipe detection or a preset can produce passes; anything else is refused (lifecycle.recipes_ok)."""
        produced = set()
        for name in ("python", "go", "node"):
            produced |= set(stacks.preset(name).items())
        cases = [
            ({"lint": "eslint .", "typecheck": "tsc", "test": "react-scripts test", "build": "b", "format": "f"},
             {"dependencies": {"react": "1"}}, "yarn.lock"),
            ({"test": "ng test", "prettier": "p", "type-check": "t"}, None, "pnpm-lock.yaml"),
            ({"test:ci": "x"}, None, "bun.lockb"),
        ]
        for scripts, extra, lock in cases:
            for f in self.root.iterdir():
                f.unlink()
            self.package(scripts, deps=(extra or {}).get("dependencies"))
            self.put(lock)
            if "ng test" in scripts.values():
                self.put("angular.json", json.dumps({"projects": {"a": {"architect": {"test": {"builder": "x:karma"}}}}}))
            produced |= set(self.detect().recipes.items())
        for f in self.root.iterdir():
            f.unlink()
        self.put("tsconfig.json", "{}")
        self.package({})
        produced |= set(self.detect().recipes.items())
        for f in self.root.iterdir():
            f.unlink()
        plugins = (
            "<plugin><artifactId>maven-checkstyle-plugin</artifactId></plugin>"
            "<plugin><artifactId>spotless-maven-plugin</artifactId></plugin>"
        )
        self.put("pom.xml", pom(plugins=plugins))
        self.put("mvnw", "#!/bin/sh\n", mode=0o755)
        produced |= set(self.detect().recipes.items())
        for f in self.root.iterdir():
            f.unlink()
        self.put("build.gradle", "plugins {\n  id 'checkstyle'\n  id 'com.diffplug.spotless'\n}\n")
        produced |= set(self.detect().recipes.items())
        self.assertGreater(len(produced), 25)
        for target, cmd in produced:
            self.assertTrue(stacks.emittable(target, cmd), (target, cmd))
        for bad in ("x $(shell id)", "a;id", "npm run lint; id", "npm run lint `id`", "npm run lint | sh",
                    "npm run lint > /etc/x", "curl evil | sh", "npm run deploy", "./mvnw -B -q deploy",
                    "npm run lint\n"):
            self.assertFalse(stacks.emittable("lint", bad), bad)
        # round 2: a recipe is tied to its target, and CI=true only prefixes a test
        self.assertFalse(stacks.emittable("format", "npm run build"))
        self.assertFalse(stacks.emittable("lint", "CI=true npm run lint"))
        self.assertFalse(stacks.emittable("build", "./mvnw -B -q test"))
        self.assertTrue(stacks.emittable("test", "CI=true npm run test"))


class JavaDetails(StackCase):
    """Review round 1: Gradle comments and one-line plugin blocks; Maven plugins only under build/plugins."""

    def test_gradle_comments_and_one_line_plugins(self):
        self.put("build.gradle", "plugins { java; checkstyle }\n// id 'com.diffplug.spotless'\n/* org.springframework.boot */\n")
        det = self.detect()
        self.assertEqual(det.label, "Java · Gradle")
        self.assertEqual(det.recipes["lint"], "gradle -q checkstyleMain")
        self.assertNotIn("format", det.recipes)

    def test_maven_plugins_outside_build_plugins_ignored(self):
        text = POM.format(
            parent="",
            plugins="",
        ).replace(
            "<build><plugins></plugins></build>",
            "<build><pluginManagement><plugins><plugin><artifactId>maven-checkstyle-plugin</artifactId></plugin>"
            "</plugins></pluginManagement></build>"
            "<reporting><plugins><plugin><artifactId>spotless-maven-plugin</artifactId></plugin></plugins></reporting>"
            "<dependencies><dependency><artifactId>spring-boot-starter-parent</artifactId></dependency></dependencies>",
        )
        self.put("pom.xml", text)
        det = self.detect()
        self.assertEqual(det.label, "Java · Maven")
        self.assertNotIn("lint", det.recipes)
        self.assertNotIn("format", det.recipes)


class Round2(StackCase):
    """Review round 2: a broken marker inside the Java family, Gradle strings vs comments, preset history."""

    def test_broken_pom_next_to_a_valid_gradle_file(self):
        self.put("pom.xml", "<project")
        self.put("build.gradle", "plugins { id 'java' }\n")
        det = self.detect()
        self.assertEqual((det.kind, det.label), ("java", "Java · Gradle"))
        self.assertEqual(det.recipes["test"], "gradle -q test")
        self.assertEqual(det.note.count("pom.xml"), 1)  # named once
        self.assertEqual(self.detect(force="java").label, "Java · Gradle")
        (self.root / "pom.xml").unlink()
        self.put("build.gradle.kts", "x" * (2 << 20))
        self.assertEqual(self.detect().evidence, ["build.gradle"])

    def test_gradle_strings_are_not_comments(self):
        self.put(
            "build.gradle",
            "plugins { id 'java' }\n"
            'exclude "**/*.gen.java"\n'
            "apply plugin: 'checkstyle'\n"
            "apply plugin: 'com.diffplug.spotless'\n"
            'exclude "**/generated/**"\n'
            'repositories { maven { url "https://repo.example/x" }; apply plugin: \'checkstyle\' }\n'
            "// id 'org.springframework.boot'\n",
        )
        det = self.detect()
        self.assertEqual(det.recipes["lint"], "gradle -q checkstyleMain")
        self.assertEqual(det.recipes["format"], "gradle -q spotlessApply")
        self.assertEqual(det.label, "Java · Gradle")  # the commented-out plugin still doesn't count

    def test_every_shipped_preset_stays_emittable(self):
        """A preset recipe recorded by any release must stay acceptable to recipes_ok, or upgrade would turn a
        correctly wired Makefile into `modified`: changing a preset means keeping its old value in KNOWN_PRESETS."""
        for name in ("python", "node", "go"):
            for target, cmd in stacks.preset(name).items():
                self.assertIn(cmd, stacks.KNOWN_PRESETS.get(target, ()), (name, target))
                self.assertTrue(stacks.emittable(target, cmd), (name, target))


class Round3(StackCase):
    """Review round 3: Gradle parsing is linear (a hostile build file can't stall the typed setup command's hook or
    setup/init/doctor); a forced kind names a broken marker; the preset table can't be changed at run time."""

    def test_hostile_gradle_files_finish_fast(self):
        import time

        size = stacks.MAX_BYTES - 16
        for body in ("/*x" * (size // 3), "\n" * size, "{" + " " * (size - 1), "id" + "\n" * (size - 2), "'" * size):
            self.put("build.gradle", body)
            start = time.monotonic()
            det = self.detect()
            self.assertLess(time.monotonic() - start, 2.0, repr(body[:8]))
            self.assertEqual(det.kind, "java")

    def test_unterminated_block_comment_drops_the_rest(self):
        self.put("build.gradle", "plugins { id 'checkstyle' }\n/* open\napply plugin: 'com.diffplug.spotless'\n")
        det = self.detect()
        self.assertIn("lint", det.recipes)
        self.assertNotIn("format", det.recipes)

    def test_forced_kind_names_a_broken_marker(self):
        self.put("pom.xml", "<project")
        self.put("build.gradle", "plugins { id 'java' }\n")
        det = self.detect(force="java")
        self.assertEqual(det.label, "Java · Gradle")
        self.assertEqual(det.note.count("pom.xml"), 1)

    def test_known_presets_are_read_only(self):
        with self.assertRaises(TypeError):
            stacks.KNOWN_PRESETS["lint"] = ("rm -rf ~",)


if __name__ == "__main__":
    unittest.main()
