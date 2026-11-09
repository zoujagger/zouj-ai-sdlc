"""Secret reads, in every repo where the plugin is installed (hooks/guard-bash.sh and hooks/guard-read.sh call it).

Shell: every word of every simple command (substitutions included, heredoc bodies and commit/PR message values
excluded) is checked against `secret-paths` after `~`/`$HOME` and glob expansion, with `cd` tracked. Recursive
readers and Grep/Glob are refused on a directory that directly contains a secret directory (`~` holds `.ssh`).
Stdlib only, no engine state: one python start per call instead of a subshell per word.
"""
import glob
import json
import os
import re
import sys
from fnmatch import fnmatchcase
from pathlib import Path

from .shell import RESET, scoped_segments, tokenize

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
GLOB_CHARS = re.compile(r"[*?\[]")
SUBST_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
HOME_RE = re.compile(r"\$\{HOME\}|\$HOME\b")
HARMLESS = {"echo", "printf", "ls", "test", "[", "[[", "mkdir", "which", "type", "true", "false", ":"}
MESSAGE_OPTS = {"-m", "--message", "--body", "-b", "--title", "--notes", "--subject"}   # values are prose, not paths
MESSAGE_SUBS = {"git": {"commit", "tag", "notes", "merge"}, "gh": {"pr", "issue", "release"},   # …for these only
                "glab": {"mr", "issue", "release"}, "hg": {"commit"}, "svn": {"commit", "ci"}, "jj": {"describe", "new"}}
PATTERN_FIRST = {"grep", "egrep", "fgrep", "rg", "ag", "ack"}                             # first operand is a regex
RECURSIVE = {"rg", "ag", "ack", "tar", "zip", "rsync"}                                   # always read whole trees
RECURSIVE_FLAG = {"grep", "egrep", "fgrep", "cp", "scp", "chmod", "du"}                  # with -r/-R
TEMPLATES = (".env.example", ".env.sample", ".env.template")
FIND_READS = {"-exec", "-execdir", "-ok", "-okdir", "-print0", "-fprint", "-fprint0", "-fprintf", "-fls"}


def patterns(root):
    out = []
    for f in (PLUGIN_ROOT / "defaults" / "secret-paths", Path(root) / ".aiops" / "config" / "secret-paths"):
        if f.is_file():
            out += [ln.split()[0] for ln in f.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    return out


def _template(rel):
    name = rel.rsplit("/", 1)[-1]
    return name in TEMPLATES or name.endswith(".pub")


def _rel(path, root):
    """Path relative to the repo root (as the secret-paths globs expect), else absolute."""
    p = os.path.normpath(path)
    r = os.path.normpath(str(root))
    return os.path.relpath(p, r) if p == r or p.startswith(r + os.sep) else p


def secret_hit(path, root, pats):
    """The matching glob if `path` (or anything inside it, as a directory) is secret material, else None."""
    rel = _rel(path, root)
    if _template(rel):
        return None
    for probe in (rel, rel.rstrip("/") + "/x"):
        for g in pats:
            if fnmatchcase(probe, g):
                return g
    return None


def ancestor_hit(path, root, pats, files=False):
    """A secret directory (or, with files=True, a secret file) directly inside directory `path`."""
    try:
        entries = [e for e in os.scandir(path) if files or e.is_dir(follow_symlinks=False)]
    except OSError:
        return None
    for e in entries:
        hit = secret_hit(e.path, root, pats)
        if hit:
            return f"{e.name}/ ({hit})"
    return None


def _expand(word, cwd):
    """The paths a word names: `~`/`$HOME` expanded, globs matched against the tree. A glob that would match a
    literal `.env` counts even when no such file exists yet."""
    w = word[1:] if word[:1] in "<>" else word
    if w.startswith("--") and "=" in w:
        w = w.split("=", 1)[1]
    w = re.sub(r"^[\w.-]+=(?=[@<])", "", w)                 # curl -F file=@.env / f=<.env, gh api -F body=@.env
    w = w[1:] if w[:1] in "@<" else w                       # curl --data-binary @.env
    w = os.path.expanduser(HOME_RE.sub(os.path.expanduser("~"), w.rstrip(")")))
    if not w or "$" in w:
        return []
    full = w if os.path.isabs(w) else os.path.join(cwd, w)
    if not GLOB_CHARS.search(w):
        return [full]
    found = glob.glob(full)
    if fnmatchcase(".env", os.path.basename(w)):
        found.append(os.path.join(os.path.dirname(full), ".env"))
    return found


def _skip_indexes(name, args):
    """Argument positions that are prose or a search pattern, not paths."""
    skip, operands = set(), 0
    sub = next((a for a in args if not a.startswith("-")), "")
    for i, a in enumerate(args):
        if (sub in MESSAGE_SUBS.get(name, ()) and a in MESSAGE_OPTS) or (name in PATTERN_FIRST and a in ("-e", "--regexp")):
            skip.add(i + 1)
        elif name in PATTERN_FIRST and not a.startswith("-") and i not in skip:
            operands += 1
            if operands == 1 and not any(x in ("-e", "--regexp", "-f", "--file") for x in args):
                skip.add(i)
    return skip


def check_shell(cmd, cwd, root, pats=None, depth=0):
    """A block reason if the command reads secret material, else None. Inside `$(…)` the output feeds another
    command, so nothing counts as harmless and `find` is a recursive reader."""
    pats = patterns(root) if pats is None else pats
    for m in SUBST_RE.finditer(cmd):                       # $(…) and `…`, also inside quotes: commands of their own
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        if depth < 3 and (why := check_shell(inner, cwd, root, pats, depth + 1)):
            return why
    try:
        segs = scoped_segments(tokenize(cmd))
    except Exception:  # noqa: BLE001: unparsable input: fall back to whitespace words
        segs = [(cmd.split(), [])]
    start_cwd = cwd
    for words, _redirs in segs:
        if _redirs is None:                                # the second reading (comments kept) starts afresh
            cwd = start_cwd if words == RESET else cwd
            continue
        while words and re.match(r"^[A-Za-z_]\w*=", words[0]):
            words = words[1:]
        if not words:
            continue
        name, args = os.path.basename(words[0]), words[1:]
        if name == "cd":
            dest = next((a for a in args if not a.startswith("-")), "~")
            dest = os.path.expanduser(HOME_RE.sub(os.path.expanduser("~"), dest))
            cwd = dest if os.path.isabs(dest) else os.path.join(cwd, dest)
            continue
        if name in HARMLESS and not depth:
            continue
        skip = _skip_indexes(name, args)
        recursive = name in RECURSIVE or (name in RECURSIVE_FLAG and any(
            re.match(r"^-[a-zA-Z]*[rR]", a) or a == "--recursive" for a in args)) or (name == "find" and (
                depth or any(a in FIND_READS for a in args)))
        hidden = name in ("rg", "ag") and any(re.match(r"^(--hidden|--no-ignore\S*|-u+|-\w*u|-\.)$", a) for a in args)
        if hidden and not [a for j, a in enumerate(args) if not a.startswith("-") and j not in skip]:
            if (hit := ancestor_hit(cwd, root, pats, files=True)):   # no path operand: the cwd, hidden files included
                return f"`{name}` with hidden files searches '{cwd}', which holds secret material ({hit})"
        for i, word in enumerate(words):
            if i and (i - 1) in skip:
                continue
            for path in _expand(word, cwd):
                hit = secret_hit(path, root, pats)
                if hit:
                    return f"reading secret material ('{word}' matches {hit})"
                if recursive and i and os.path.isdir(path) and (hit := ancestor_hit(path, root, pats)):
                    return f"a recursive read of '{word}' reaches secret material ({hit})"
    return None


def check_search(ti, root, pats=None):
    """Grep/Glob: a `glob` that reaches secret material from `path`, or a `path` outside the repo that directly holds a
    secret directory (`~`). Inside the repo, Grep (ripgrep) honours .gitignore, and secret paths themselves are
    refused by guard-read.sh, so `path: "."` and no path behave the same."""
    pats = patterns(root) if pats is None else pats
    path = ti.get("path")
    if not path:
        return None
    base = os.path.expanduser(path)
    base = base if os.path.isabs(base) else os.path.join(root, base)
    g = ti.get("glob") or (ti.get("pattern") if ti.get("_tool") == "Glob" else None)
    if g:
        for probe in (os.path.join(base, g), os.path.join(base, g.split("**")[0].rstrip("/*") or ".", "x")):
            if secret_hit(probe, root, pats):
                return f"'{path}' with glob '{g}' reaches secret material"
    if os.path.isdir(base) and _rel(base, root).startswith("/") and (hit := ancestor_hit(base, root, pats)):
        return f"'{path}' contains secret material ({hit}); search a narrower path"
    return None


def main():
    data = json.loads(sys.stdin.read() or "{}")
    root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    ti = data.get("tool_input") or {}
    tool = data.get("tool_name") or "Bash"
    if tool == "Bash":
        why = check_shell(ti.get("command", ""), data.get("cwd") or root, root)
    else:
        why = check_search({**ti, "_tool": tool}, root)
    if why:
        print(f"BLOCKED [G-SEC-03] by guard-{'bash' if tool == 'Bash' else 'read'}: {why}\n"
              "Procedure: use .env.example / documentation for names; never read real secrets into the session. "
              "(details: `sdlc why G-SEC-03`)",
              file=sys.stderr)
        return 2
    return 0
