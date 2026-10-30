"""PreToolUse decisions. Each check returns None (allow) or a block message stating the reason and the procedure.

Rules (only in repos initialized with `.aiops/`):
  * Artifacts: agents create them as Draft, in order (spec needs an approved intent, plan an approved spec,
    review an approved plan), and never write a gate status or `approved-*` fields.
  * Read-only lock: in states 1-3 (and with no active intent) nothing outside `.aiops/` and the exempt globs
    may be written, by Edit/Write or by shell commands.
  * Always: no shell writes to artifacts or `.aiops/config|state`, no forged approvals, no merging into main.
"""
import re
import shlex
from pathlib import Path

from . import artifacts as A
from .machine import (SCHEMAS, active_dir, config, current_branch, evaluate, gate, git, glob_hit, globs,
                      initialized, lock, phrase, project_root)

ARTIFACT_RE = re.compile(r"^\.aiops/(\d{4}-[a-z0-9-]+)/(intent|spec|plan|review)\.md$")
GUARDED_RE = re.compile(r"^\.aiops/(config(/|\.json$)|state(/|$))")


def _block(rule, reason, procedure):
    return f"BLOCKED by zouj-ai-sdlc ({rule}): {reason}\nProcedure: {procedure}"


def lock_procedure(st):
    if st is None:
        return "start from an intent: run /zouj-ai-sdlc:intent (or `sdlc use NNNN` to resume one)."
    if st.state in (1, 2, 3):
        kind = ("intent", "spec", "plan")[st.state - 1]
        return (f"you are in a read-only state. Finish {kind}.md under {st.dir.name}/, then stop and ask the human "
                f"to type `{phrase(kind, st.id)}`. Code is unlocked only after `Plan Approved`.")
    return "this intent is finished. Start a new one with /zouj-ai-sdlc:intent."


def _rel(root, path, cwd):
    p = Path(path).expanduser()
    p = (Path(cwd) / p) if not p.is_absolute() else p
    try:
        return p.resolve().relative_to(root).as_posix()
    except ValueError:
        return None   # outside the project: not this repo's application code


# ---------------------------------------------------------------- Edit / Write / MultiEdit

def simulate(tool, ti, path):
    """The file content after the tool runs, or None if it can't be predicted (the tool will fail anyway)."""
    if tool == "Write":
        return ti.get("content", "")
    current = path.read_text() if path.is_file() else ""
    edits = ti.get("edits") if tool == "MultiEdit" else [ti]
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        if old not in current:
            return None
        current = current.replace(old, new) if e.get("replace_all") else current.replace(old, new, 1)
    return current


def check_edit(data):
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path")
    if not path:
        return None
    cwd = data.get("cwd") or "."
    root = project_root(cwd)
    if not initialized(root):
        return None
    rel = _rel(root, path, cwd)
    if rel is None:
        return None
    if GUARDED_RE.match(rel):
        return _block("guardrails", f"'{rel}' is engine state or human-owned configuration.",
                      "propose the change in chat; a human edits .aiops/config. State changes go through `sdlc`.")
    m = ARTIFACT_RE.match(rel)
    if m:
        new = simulate(data.get("tool_name", ""), ti, root / rel)
        return None if new is None else check_artifact(root / ".aiops" / m.group(1), m.group(2), new)
    if rel.startswith(".aiops/") or glob_hit(rel, globs(root, "readonly-exempt")):
        return None
    locked, reason, st = lock(root)
    if locked:
        return _block("read-only lock", f"cannot edit '{rel}': {reason}.", lock_procedure(st))
    return None


def check_artifact(d, kind, new_text):
    schema = SCHEMAS[kind]
    ident = d.name[:4]
    path = d / f"{kind}.md"
    new = A.parse(new_text)
    gate_value = schema["gate"]
    if not path.is_file():
        if schema["requires"]:
            ok, why = gate(d, schema["requires"])
            if not ok:
                req = schema["requires"]
                return _block("state order", f"{kind}.md needs an approved {req}.md first ({req}.md: {why}).",
                              f"finish {req}.md and ask the human to type `{phrase(req, ident)}`.")
        if gate_value and new.get("status") not in ("", "Draft"):
            return _block("human gate", f"a new {kind}.md must start as `status: Draft`.",
                          "write it as Draft; the human approves it by typing the approval phrase.")
        if any(new.get(f) for f in A.APPROVAL_FIELDS):
            return _block("human gate", "approved-* fields are written only by a human approval.",
                          "leave them out; they are stamped when the human approves.")
        return None
    old = A.parse(path.read_text())
    for f in A.APPROVAL_FIELDS:
        if old.get(f) != new.get(f):
            return _block("human gate", f"`{f}` in {kind}.md can only be written by a human approval.",
                          f"leave approval fields untouched. The human types `{phrase(kind, ident)}`."
                          if gate_value else "leave approval fields untouched.")
    if gate_value and new.get("status") != old.get("status") and new.get("status") != "Draft":
        return _block("human gate", f"setting {kind}.md to `status: {new.get('status')}` is a human decision.",
                      f"stop and ask the human to type `{phrase(kind, ident)}` in the prompt."
                      if new.get("status") == gate_value else "only `Draft` may be set by the agent.")
    return None


# ---------------------------------------------------------------- Bash

HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?^\s*\2\s*$", re.M | re.S)
SEPARATORS = {";", "&&", "||", "|", "&", "|&", "(", ")", ";;", "{", "}", "!", "\n"}
PREFIXES = {"sudo", "command", "env", "nohup", "time", "exec", "builtin", "xargs", "then", "do", "else", "if",
            "while", "until"}
ALL_TARGETS = {"rm", "rmdir", "touch", "mkdir", "truncate", "tee", "shred", "unlink"}
DEST_TARGET = {"cp", "ln", "install", "rsync", "scp"}
INPLACE = {"sed", "perl", "ruby", "gsed"}
PKG = {
    "npm": {"install", "i", "add", "ci", "uninstall", "remove", "rm", "update", "up", "upgrade", "link"},
    "pnpm": {"install", "i", "add", "remove", "rm", "update", "up", "upgrade", "link"},
    "yarn": {"", "install", "add", "remove", "upgrade", "up"},
    "bun": {"install", "i", "add", "remove", "update"},
    "pip": {"install", "uninstall"}, "pip3": {"install", "uninstall"},
    "uv": {"add", "remove", "sync", "pip", "lock"}, "poetry": {"add", "remove", "install", "update", "lock"},
    "go": {"get"}, "cargo": {"add", "remove", "install", "update"}, "gem": {"install", "uninstall"},
    "bundle": {"install", "add", "update"}, "composer": {"require", "install", "update", "remove"},
}
GIT_LOCKED = {"apply", "am", "cherry-pick", "merge", "rebase", "revert", "pull", "restore", "rm", "mv", "clean",
              "reset", "stash"}
GIT_MAIN_FORBIDDEN = {"merge", "rebase", "cherry-pick", "am"}
GIT_TREE_WRITERS = {"rm", "mv", "checkout", "restore", "reset", "clean", "stash"}
MAKE_WRITERS = {"format", "fmt", "fix", "generate", "gen", "migrate", "codegen"}
ENGINE_RE = re.compile(r"(^|[\s;&|(/])(sdlc\s+(approve|close|unlock|hook)\b|-m\s+sdlc_engine|sdlc_engine\.)")


def tokenize(cmd):
    cmd = HEREDOC_RE.sub("", cmd)
    lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:   # unbalanced quotes: fall back to whitespace split
        return cmd.split()


def segments(tokens):
    """Split tokens into simple commands; return [(words, redirect_targets)]."""
    out, words, redirs, i = [], [], [], 0
    while i < len(tokens):
        t = tokens[i]
        if t in SEPARATORS:
            out.append((words, redirs))
            words, redirs = [], []
        elif set(t) <= set("<>&|") and ">" in t:
            if words and words[-1].isdigit():
                words.pop()            # the "2" in 2>file
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            i += 1
            if not (t.endswith("&") and target.lstrip("-").isdigit()) and target not in SEPARATORS:
                redirs.append(target)
        elif not (set(t) <= set("<")):
            words.append(t)
        i += 1
    out.append((words, redirs))
    return [(w, r) for w, r in out if w or r]


SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}


def _nested_command(words):
    """The command string run by `bash -c '...'` or `eval ...`, else None."""
    if not words:
        return None
    name = Path(words[0]).name
    if name == "eval":
        return " ".join(words[1:])
    if name in SHELLS:
        for i, a in enumerate(words[1:], 1):
            if re.match(r"^-[a-zA-Z]*c[a-zA-Z]*$", a) and i + 1 < len(words):
                return words[i + 1]
    return None


def _strip_prefix(words):
    i = 0
    while i < len(words) and (words[i] in PREFIXES or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[i])
                              or (i and words[i - 1] == "env" and words[i].startswith("-"))):
        i += 1
    return words[i:]


def write_targets(words, cwd):
    """Paths a simple command writes to, as far as a static read can tell."""
    if not words:
        return []
    name, args = Path(words[0]).name, words[1:]
    nonopt = [a for a in args if not a.startswith("-")]
    if name in ALL_TARGETS:
        return nonopt
    if name in ("chmod", "chown", "chgrp"):
        return nonopt[1:]
    if name == "mv":
        return nonopt
    if name in DEST_TARGET:
        return nonopt[-1:]
    if name == "dd":
        return [a[3:] for a in args if a.startswith("of=")]
    if name in INPLACE and any(re.match(r"^-[a-zA-Z]*i", a) or a.startswith("--in-place") for a in args):
        return [a for a in nonopt if (Path(cwd) / a).is_file()]
    return []


def _git_sub(args):
    i = 0
    while i < len(args):
        if args[i] in ("-C", "-c", "--git-dir", "--work-tree"):
            i += 2
        elif args[i].startswith("-"):
            i += 1
        else:
            return args[i], args[i + 1:]
    return "", []


def _code_paths(root, rels):
    exempt = globs(root, "readonly-exempt")
    return [r for r in rels if r and not r.startswith(".aiops/") and not glob_hit(r, exempt)]


def _git_changed(root, staged_only):
    out = git(root, "diff", "--cached", "--name-only") if staged_only else git(root, "status", "--porcelain")
    if not out:
        return []
    return [ln if staged_only else ln[3:].split(" -> ")[-1] for ln in out.splitlines()]


def check_bash(data):
    cmd = (data.get("tool_input") or {}).get("command", "")
    cwd = data.get("cwd") or "."
    root = project_root(cwd)
    if not initialized(root) or not cmd.strip():
        return None
    if "AIOps-Approval" in cmd:
        return _block("human gate", "approval commits are created only by a human approval.",
                      "ask the human to type the approval phrase (e.g. `Plan Approved 0001`).")
    if ENGINE_RE.search(cmd):
        return _block("human gate", "`sdlc approve|close|unlock|hook` are human-only (or hook-only) commands.",
                      "stop and ask the human: they type `Intent|Spec|Plan Approved NNNN` in the prompt, "
                      "or run the command in their own terminal.")
    locked, reason, st = lock(root)
    on_main = current_branch(root) == config(root)["main_branch"]
    return _check_command(cmd, Path(cwd), root, locked, reason, st, on_main, depth=0)


def _check_command(cmd, cwd, root, locked, reason, st, on_main, depth):
    for words, redirs in segments(tokenize(cmd)):
        words = _strip_prefix(words)
        if words and words[0] == "cd":
            dest = next((a for a in words[1:] if not a.startswith("-")), "~")
            cwd = Path(dest).expanduser() if Path(dest).expanduser().is_absolute() else cwd / dest
            continue
        inner = _nested_command(words)
        if inner is not None:
            if depth >= 3:
                return _block("bash", "nested shells are too deep to inspect.", "run the command directly.")
            msg = _check_command(inner, cwd, root, locked, reason, st, on_main, depth + 1)
            if msg:
                return msg
            continue
        targets = redirs + write_targets(words, cwd)
        for t in targets:
            if t.startswith("/dev/"):
                continue
            rel = _rel(root, t, cwd)
            if rel is None:
                continue
            if ARTIFACT_RE.match(rel) or GUARDED_RE.match(rel):
                return _block("artifacts", f"shell writes to '{rel}' bypass the gate guard.",
                              "edit artifacts with the Edit/Write tools; engine state changes go through `sdlc`.")
            if locked and _code_paths(root, [rel]):
                return _block("read-only lock", f"`{' '.join(words)[:80]}` writes '{rel}': {reason}.",
                              lock_procedure(st))
        if not words:
            continue
        name, args = Path(words[0]).name, words[1:]
        if name == "gh" and args[:1] == ["api"] and any(re.search(r"/pulls/\d+/merge\b|/merges\b", a) for a in args):
            return _block("final gate", "merging through the GitHub API is the human's decision.",
                          "leave the PR for a CODEOWNER to review and merge.")
        if name == "git":
            sub, rest = _git_sub(args)
            if sub in GIT_TREE_WRITERS:
                hit = next((r for r in (_rel(root, a, cwd) for a in rest if not a.startswith("-"))
                            if r and (ARTIFACT_RE.match(r) or GUARDED_RE.match(r))), None)
                if hit:
                    return _block("artifacts", f"`git {sub}` on '{hit}' would delete or rewrite an artifact outside the "
                                  "gate guard.", "edit artifacts with the Edit/Write tools; ask the human to remove one.")
            if on_main and sub in GIT_MAIN_FORBIDDEN:
                return _block("final gate", f"`git {sub}` on {config(root)['main_branch']}: merging is the human's decision.",
                              "leave the branch for the human to review and merge (/zouj-ai-sdlc:pr).")
            if sub == "commit":
                for i, a in enumerate(rest):
                    f = rest[i + 1] if a in ("-F", "--file") and i + 1 < len(rest) else \
                        a.split("=", 1)[1] if a.startswith("--file=") else None
                    path = (cwd / f) if f and f != "-" else None
                    if path and path.is_file() and "AIOps-Approval" in path.read_text(errors="replace"):
                        return _block("human gate", "approval commits are created only by a human approval.",
                                      "ask the human to type the approval phrase (e.g. `Plan Approved 0001`).")
            if not locked:
                continue
            checkout_paths = sub == "checkout" and _code_paths(root, [
                r for r in (_rel(root, a, cwd) for a in rest if not a.startswith("-") and (cwd / a).is_file()) if r])
            if sub in GIT_LOCKED or (sub == "checkout" and "--" in rest) or checkout_paths:
                return _block("read-only lock", f"`git {sub}` changes the working tree: {reason}.", lock_procedure(st))
            if sub == "add":
                paths = [a for a in rest if not a.startswith("-")]
                if not paths or any(a in ("-A", "--all", "-u", "--update") for a in rest) or "." in paths:
                    rels = _git_changed(root, staged_only=False)
                else:
                    rels = [_rel(root, p, cwd) for p in paths]
                if bad := _code_paths(root, rels):
                    return _block("read-only lock", f"`git add` would stage code ({', '.join(bad[:3])}): {reason}.",
                                  lock_procedure(st))
            if sub == "commit":
                all_flag = any(re.match(r"^-[a-zA-Z]*a", a) or a == "--all" for a in rest)
                rels = _git_changed(root, staged_only=not all_flag)
                if bad := _code_paths(root, rels):
                    return _block("read-only lock", f"`git commit` would commit code ({', '.join(bad[:3])}): {reason}.",
                                  lock_procedure(st))
            continue
        if not locked:
            continue
        sub = next((a for a in args if not a.startswith("-")), "")
        if name.startswith("python") and args[:2] == ["-m", "pip"]:
            name, sub = "pip", (args[2] if len(args) > 2 else "")
        if name in PKG and sub in PKG[name]:
            return _block("read-only lock", f"`{name} {sub}` changes dependencies: {reason}.", lock_procedure(st))
        if name == "make" and any(a in MAKE_WRITERS for a in args):
            return _block("read-only lock", f"`make {' '.join(args)}` rewrites code: {reason}.", lock_procedure(st))
        if name in ("patch", "unzip") or (name == "tar" and args and "x" in args[0]):
            return _block("read-only lock", f"`{name}` writes files: {reason}.", lock_procedure(st))
    return None


__all__ = ["check_edit", "check_bash", "check_artifact", "lock_procedure", "active_dir", "evaluate"]
