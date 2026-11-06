#!/usr/bin/env python3
"""Regenerate defaults/scaffold-history.json: the normalized sha256 of every scaffold file of every release.

For each `v*` tag, the scaffold (templates/scaffold/) and stack presets (templates/stacks/) are read from git at that
tag; the working tree is added under the plugin.json version, or under `unreleased` while that version is already
tagged. Each file is hashed after lifecycle.normalize() (the CI ref put back to its placeholder). The Makefile is
also hashed with each stack preset of the same release wired in (`Makefile+<stack>`). `sdlc upgrade`/`repair`
use the result to adopt repos initialized before install-state existed. Stdlib only. Run from the repo:

    python3 scripts/scaffold-history.py          # writes defaults/scaffold-history.json
    python3 scripts/scaffold-history.py --check  # exit 1 if the file is out of date
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from sdlc_engine import cli, lifecycle  # noqa: E402

SCAFFOLD, STACKS = "templates/scaffold", "templates/stacks"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def hashes(read, paths, recipes):
    out = {}
    for rel in paths:
        data = read(rel)
        out[rel] = lifecycle.sha256_bytes(lifecycle.normalize(data))
        if rel == "Makefile":
            for stack, text in recipes.items():
                wired = cli.wire(data.decode(), stack, text)[0].encode()
                out[f"Makefile+{stack}"] = lifecycle.sha256_bytes(lifecycle.normalize(wired))
    return out


def at_tag(tag):
    paths = [p.split(f"{SCAFFOLD}/", 1)[1] for p in git("ls-tree", "-r", "--name-only", tag, SCAFFOLD).decode().split()]
    recipes = {}
    for stack in cli.STACKS:
        try:
            recipes[stack] = git("show", f"{tag}:{STACKS}/{stack}.recipes").decode()
        except subprocess.CalledProcessError:
            pass
    return hashes(lambda rel: git("show", f"{tag}:{SCAFFOLD}/{rel}"), sorted(paths), recipes)


def build():
    tags = [t for t in git("tag", "-l", "v*").decode().split() if t[1:2].isdigit()]
    hist = {t[1:]: at_tag(t) for t in tags}
    version = cli.plugin_version()
    recipes = {s: (ROOT / STACKS / f"{s}.recipes").read_text() for s in cli.STACKS}
    current = hashes(lambda rel: (ROOT / SCAFFOLD / rel).read_bytes(), lifecycle.scaffold_paths(), recipes)
    if version not in hist:
        hist[version] = current
    elif hist[version] != current:
        hist["unreleased"] = current          # the tagged release keeps its own hashes
    return {v: dict(sorted(files.items())) for v, files in sorted(hist.items(), key=lambda kv: lifecycle.version_key(kv[0]))}


def main(argv):
    text = json.dumps(build(), indent=1) + "\n"
    target = ROOT / "defaults" / "scaffold-history.json"
    if "--check" in argv:
        ok = target.is_file() and target.read_text() == text
        print("scaffold-history.json is up to date" if ok else "scaffold-history.json is stale: run "
              "python3 scripts/scaffold-history.py", file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    target.write_text(text)
    print(f"wrote {target.relative_to(ROOT)}: {', '.join(json.loads(text))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
