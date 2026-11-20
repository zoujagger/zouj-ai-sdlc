#!/usr/bin/env python3
"""Validate the domain model in domain/*.dsl.json (the zouj-ai-sdlc `dsl` part; format in domain/README.md).

    python3 scripts/validate-dsl.py [dir]      # default: domain

Prints one line per problem, `<file>: <json path>: <problem>`, and exits 1 if there is any; otherwise prints
`validate-dsl: N model(s) ok` and exits 0. A missing directory is skipped (exit 0). Standard library only
(Python >= 3.9). The model is data: nothing in it is evaluated. Only regular `*.dsl.json` files directly in the
directory are read, each at most 1 MiB and 64 levels deep; a link is never followed.
"""

import json
import os
import re
import stat
import sys

MAX_BYTES = 1024 * 1024
MAX_DEPTH = 64
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
COMMON = {"dsl", "kind", "name", "description"}
KINDS = {
    "state_machine": {"states", "initial", "final", "transitions"},
    "rules": {"rules"},
    "workflow": {"steps", "start"},
}
REQUIRED = {"state_machine": ("states", "initial", "transitions"), "rules": ("rules",), "workflow": ("steps", "start")}


class Obj(dict):
    """A JSON object that remembers the keys it saw more than once (json keeps only the last value)."""

    dups = ()


def _object(pairs):
    obj, seen, dups = Obj(), set(), []
    for key, value in pairs:
        if key in seen and key not in dups:
            dups.append(key)
        seen.add(key)
        obj[key] = value
    obj.dups = dups
    return obj


def read(path):
    """(text, None), or (None, problem) for a file that isn't a small regular UTF-8 file. Never follows a link."""
    try:
        if stat.S_ISLNK(os.lstat(path).st_mode):
            return None, "not a regular file (links are not followed)"
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    except OSError:
        return None, "not a regular file (links are not followed)"
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            return None, "not a regular file (links are not followed)"
        if info.st_size > MAX_BYTES:
            return None, "larger than 1 MiB"
        with os.fdopen(fd, "rb") as f:
            fd = None
            data = f.read(MAX_BYTES + 1)
    except OSError as e:
        return None, f"unreadable ({e.strerror})"
    finally:
        if fd is not None:
            os.close(fd)
    if len(data) > MAX_BYTES:
        return None, "larger than 1 MiB"
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, "not UTF-8 text"


def too_deep(value):
    """True if value nests deeper than MAX_DEPTH (checked without recursion)."""
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, (dict, list)):
            if depth > MAX_DEPTH:
                return True
            children = item.values() if isinstance(item, dict) else item
            stack.extend((child, depth + 1) for child in children)
    return False


def duplicate_keys(value, path="$"):
    """[(path, key)] for every object that repeats a key."""
    out, stack = [], [(value, path)]
    while stack:
        item, where = stack.pop()
        if isinstance(item, dict):
            out += [(where, key) for key in getattr(item, "dups", ())]
            stack.extend((v, f"{where}.{k}") for k, v in item.items())
        elif isinstance(item, list):
            stack.extend((v, f"{where}[{i}]") for i, v in enumerate(item))
    return sorted(out)


def text(value):
    return isinstance(value, str) and value.strip() != ""


def check_keys(obj, allowed, path, out):
    for key in obj:
        if key not in allowed:
            out.append(f"{path}.{key}: unknown key")


def items(model, key, out, what="a list"):
    """The list at model[key] (reporting a missing or wrong value), or []."""
    if key not in model:
        out.append(f"$.{key}: missing")
        return []
    value = model[key]
    if not isinstance(value, list) or (what == "a non-empty list" and not value):
        out.append(f"$.{key}: expected {what}")
        return []
    return value


def unique_ids(entries, key, path, label, out):
    """The ids found at entries[i][key], reporting non-text and duplicate ones."""
    ids = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            out.append(f"{path}[{i}]: expected an object")
            continue
        value = entry.get(key)
        if not text(value):
            out.append(f"{path}[{i}].{key}: expected non-empty text")
        elif value in ids:
            out.append(f'{path}[{i}].{key}: duplicate {label} "{value}"')
        else:
            ids.append(value)
    return ids


def state_machine(model, out):
    states = []
    for i, state in enumerate(items(model, "states", out, "a non-empty list")):
        if not text(state):
            out.append(f"$.states[{i}]: expected non-empty text")
        elif state in states:
            out.append(f'$.states[{i}]: duplicate state "{state}"')
        else:
            states.append(state)
    if "initial" not in model:
        out.append("$.initial: missing")
    elif not isinstance(model["initial"], str):
        out.append("$.initial: expected a state name")
    elif model["initial"] not in states:
        out.append(f'$.initial: unknown state "{model["initial"]}"')
    final = model.get("final", [])
    if not isinstance(final, list):
        out.append("$.final: expected a list")
    else:
        for i, s in enumerate(final):
            if not isinstance(s, str):
                out.append(f"$.final[{i}]: expected a state name")
            elif s not in states:
                out.append(f'$.final[{i}]: unknown state "{s}"')
    pairs = set()
    for i, t in enumerate(items(model, "transitions", out)):
        path = f"$.transitions[{i}]"
        if not isinstance(t, dict):
            out.append(f"{path}: expected an object")
            continue
        check_keys(t, {"from", "to", "event", "guard"}, path, out)
        for end in ("from", "to"):
            if end not in t:
                out.append(f"{path}.{end}: missing")
            elif not isinstance(t[end], str):
                out.append(f"{path}.{end}: expected a state name")
            elif t[end] not in states:
                out.append(f'{path}.{end}: unknown state "{t[end]}"')
        if not text(t.get("event")):
            out.append(f"{path}.event: expected non-empty text")
        elif isinstance(t.get("from"), str):  # a non-string `from` is reported above, and left out of the pairs
            if (t["from"], t["event"]) in pairs:
                out.append(f'{path}: duplicate transition from "{t["from"]}" on "{t["event"]}"')
            else:
                pairs.add((t["from"], t["event"]))
        if "guard" in t and not text(t["guard"]):
            out.append(f"{path}.guard: expected non-empty text")


def rules(model, out):
    entries = items(model, "rules", out, "a non-empty list")
    unique_ids(entries, "id", "$.rules", "id", out)
    for i, rule in enumerate(entries):
        if isinstance(rule, dict):
            check_keys(rule, {"id", "when", "then", "description"}, f"$.rules[{i}]", out)
            for key in ("when", "then"):
                if not text(rule.get(key)):
                    out.append(f"$.rules[{i}].{key}: expected non-empty text")


def workflow(model, out):
    entries = items(model, "steps", out, "a non-empty list")
    ids = unique_ids(entries, "id", "$.steps", "id", out)
    for i, step in enumerate(entries):
        if not isinstance(step, dict):
            continue
        check_keys(step, {"id", "next", "description"}, f"$.steps[{i}]", out)
        nxt = step.get("next", [])
        if not isinstance(nxt, list):
            out.append(f"$.steps[{i}].next: expected a list")
            continue
        for j, n in enumerate(nxt):
            if not isinstance(n, str):
                out.append(f"$.steps[{i}].next[{j}]: expected a step id")
            elif n not in ids:
                out.append(f'$.steps[{i}].next[{j}]: unknown step "{n}"')
    if "start" not in model:
        out.append("$.start: missing")
    elif not isinstance(model["start"], str):
        out.append("$.start: expected a step id")
    elif model["start"] not in ids:
        out.append(f'$.start: unknown step "{model["start"]}"')


CHECKS = {"state_machine": state_machine, "rules": rules, "workflow": workflow}


def check_model(model):
    """Problems (`<json path>: <problem>`) in one parsed model."""
    if not isinstance(model, dict):
        return ["$: expected an object"]
    out = [f'{path}: duplicate key "{key}"' for path, key in duplicate_keys(model)]
    if model.get("dsl") != 1 or isinstance(model.get("dsl"), bool):
        out.append("$.dsl: expected 1")
    kind = model.get("kind")
    if not isinstance(kind, str):
        out.append("$.kind: expected text (state_machine, rules or workflow)")
        return out
    if kind not in KINDS:
        out.append(f'$.kind: unknown kind "{kind}" (state_machine, rules or workflow)')
        return out
    if not isinstance(model.get("name"), str) or not NAME_RE.match(model["name"]):
        out.append("$.name: expected an identifier")
    if "description" in model and not isinstance(model["description"], str):
        out.append("$.description: expected text")
    check_keys(model, COMMON | KINDS[kind], "$", out)
    CHECKS[kind](model, out)
    return out


def main(argv):
    folder = (argv[1] if len(argv) > 1 else "domain").rstrip("/") or "."
    if os.path.islink(folder):  # never followed, never silently skipped (0013 R-4)
        print(f"{folder}: a link, not followed (validate the real directory)")
        print("validate-dsl: 1 problem(s) in 0 model(s)")
        return 1
    if not os.path.isdir(folder):
        print(f"validate-dsl: no {folder}/ - skipped")
        return 0
    problems, names, count = [], {}, 0
    for entry in sorted(os.listdir(folder)):
        if not entry.endswith(".dsl.json"):
            continue
        count += 1
        rel = f"{folder}/{entry}"
        data, why = read(os.path.join(folder, entry))
        if why:
            problems.append(f"{rel}: {why}")
            continue
        try:
            model = json.loads(data, object_pairs_hook=_object)
        except json.JSONDecodeError as e:
            problems.append(f"{rel}:{e.lineno}:{e.colno}: invalid JSON: {e.msg}")
            continue
        except RecursionError:
            problems.append(f"{rel}: nested deeper than {MAX_DEPTH} levels")
            continue
        if too_deep(model):
            problems.append(f"{rel}: nested deeper than {MAX_DEPTH} levels")
            continue
        problems += [f"{rel}: {p}" for p in check_model(model)]
        name = model.get("name") if isinstance(model, dict) else None
        if isinstance(name, str) and NAME_RE.match(name):
            if name in names:
                problems.append(f'{rel}: $.name: "{name}" is also the name in {names[name]}')
            else:
                names[name] = rel
    for line in problems:
        print(line)
    if problems:
        print(f"validate-dsl: {len(problems)} problem(s) in {count} model(s)")
        return 1
    print(f"validate-dsl: {count} model(s) ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
