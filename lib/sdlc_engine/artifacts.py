"""Parse and rewrite .aiops Markdown artifacts: flat `key: value` front matter + `## ` sections.

Stdlib only: hooks import this on every tool call, so it must load fast and never need pip.
"""
import hashlib
import re
from dataclasses import dataclass

FM_RE = re.compile(r"\A---\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
SECTION_RE = re.compile(r"^## +(.+?)\s*$", re.M)
CHECKBOX_RE = re.compile(r"^\s*- \[( |x|X|~)\] +(.*)$", re.M)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

# Fields only a human approval may write (UserPromptSubmit hook or `sdlc approve` in a terminal).
APPROVAL_FIELDS = ("approved-by", "approved-at", "approved-via", "approved-sha256")


@dataclass
class Artifact:
    front: dict
    body: str
    has_front: bool

    def get(self, key, default=""):
        return self.front.get(key, default)


def parse(text):
    m = FM_RE.match(text)
    if not m:
        return Artifact({}, text, False)
    front = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, val = line.partition(":")
        if not sep:
            continue
        val = re.sub(r"\s+#.*$", "", val.strip())  # trailing "# comment"; a leading "#12" is a value
        front[key.strip()] = val.strip().strip("\"'")
    return Artifact(front, text[m.end():], True)


def set_fields(text, updates):
    """Return text with front-matter keys replaced or appended (comments on replaced lines are dropped)."""
    m = FM_RE.match(text)
    if not m:
        head = "\n".join(f"{k}: {v}" for k, v in updates.items())
        return f"---\n{head}\n---\n{text}"
    lines = m.group(1).splitlines()
    todo = dict(updates)
    for i, line in enumerate(lines):
        key = line.partition(":")[0].strip()
        if key in todo and not line.lstrip().startswith("#"):
            lines[i] = f"{key}: {todo.pop(key)}"
    lines += [f"{k}: {v}" for k, v in todo.items()]
    return "---\n" + "\n".join(lines) + "\n---\n" + text[m.end():]


def sections(body):
    """{heading: content} for every `## heading`, HTML comments removed."""
    body = COMMENT_RE.sub("", body)
    out = {}
    parts = SECTION_RE.split(body)
    for i in range(1, len(parts) - 1, 2):
        out[parts[i].strip()] = parts[i + 1].strip()
    return out


def strip_section(body, heading):
    pat = re.compile(rf"^## +{re.escape(heading)}\s*$.*?(?=^## |\Z)", re.M | re.S)
    return pat.sub("", body)


def checkboxes(body):
    """[(state, text)] for `- [ ]`, `- [~]`, `- [x]` lines outside HTML comments."""
    return [(s.lower(), t.strip()) for s, t in CHECKBOX_RE.findall(COMMENT_RE.sub("", body))]


def approval_hash(kind, text):
    """Hash of what a human approved. Plan progress (ticked boxes, Deviation log) doesn't invalidate it."""
    body = parse(text).body
    if kind == "plan":
        body = re.sub(r"(?m)^(\s*- )\[[xX~]\]", r"\1[ ]", body)
        body = strip_section(body, "Deviation log")
    norm = "\n".join(line.rstrip() for line in body.strip().splitlines())
    return hashlib.sha256(norm.encode()).hexdigest()


def ac_ids(text):
    return sorted(set(re.findall(r"\bAC-\d+\b", COMMENT_RE.sub("", text))), key=lambda s: int(s[3:]))
