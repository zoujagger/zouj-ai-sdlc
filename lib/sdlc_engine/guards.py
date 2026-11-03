"""PreToolUse decisions. Each check returns None (allow) or a block message stating the reason and the procedure.

Rules (only in repos initialized with `.aiops/`):
  * Artifacts: agents create them as Draft, in order (spec needs an approved intent, plan an approved spec,
    review an approved plan), and never write a gate status or `approved-*` fields.
  * Read-only lock: in states 1-3 (and with no active intent) nothing outside `.aiops/` and the exempt globs
    may be written, by Edit/Write or by shell commands.
  * Always: no shell writes to artifacts or `.aiops/config|state`, no forged approvals, no merging into main.
"""
import glob
import re
import shlex
from fnmatch import fnmatchcase
from pathlib import Path

from . import artifacts as A
from .shell import SEPARATORS, segments, tokenize
from .machine import (PLUGIN_ROOT, SCHEMAS, active_dir, config, current_branch, evaluate, gate, git, glob_hit, globs,
                      initialized, lock, phrase, project_root)

ARTIFACT_RE = re.compile(r"^\.aiops/(\d{4}-[a-z0-9-]+)/(intent|spec|plan|review)\.md$")
GUARDED_RE = re.compile(r"^\.aiops/(config(/|\.json$)|state(/|$))")
INTENT_TREE_RE = re.compile(r"^\.aiops(/\d{4}-[a-z0-9-]+(/.*)?)?$")


def _aiops_protected(rel):
    """`.aiops` itself, an intent folder or anything in it, or engine state/config: never a shell target."""
    return bool(INTENT_TREE_RE.match(rel) or GUARDED_RE.match(rel))


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
    if _in_plugin(path, cwd, root):
        return _block("toolchain", f"'{path}' is inside the installed plugin, which the human runs to approve.",
                      "change the plugin through its own repo.")
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
    if new.get("id") and new.get("id") != ident:
        return _block("artifacts", f"`id: {new.get('id')}` in {kind}.md must match its folder ({ident}).",
                      "keep `id` equal to the folder number; artifacts can't be moved between intents.")
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
    if old.get("id") != new.get("id"):
        return _block("artifacts", f"`id` in {kind}.md can't be changed.", "keep `id` equal to the folder number.")
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
HUMAN_SUBS = r"(approve|close|unlock|hook|legacy-approvals)"
# Commands that run their arguments as a command; any literal words (options, durations) may follow them. Shells
# count only with -c (`sh script.sh $x hook` runs a script, not $x).
WRAPPER_WORDS = {"sudo", "doas", "command", "exec", "env", "nohup", "time", "builtin", "xargs", "eval", "nice",
                 "timeout", "stdbuf", "setsid", "ionice", "chrt", "taskset", "unbuffer", "watch", "flock", "trap",
                 "coproc", "strace", "ltrace", "parallel", "busybox", "then", "do", "else", "while", "until", "if",
                 "elif", "!", "{"}
WRAPPERS = r"(sudo|doas|command|exec|env|nohup|time|builtin|xargs|eval|nice|timeout|stdbuf|setsid|ionice|chrt|" \
           r"taskset|unbuffer|watch|flock|trap|coproc|strace|ltrace|parallel|python[\d.]*)"
SHELL_C = r"((busybox|su)\s+)?(\S*/)?(ba|z|da|k|fi)?sh\s+(-\S+\s+)*?-\w*c|script\s+(-\S+\s+)*?-\w*c|su\s+(-\S+\s+)*?-c"
CMD_POS = (rf"(^|[;&|()`\n{{!]|\b(then|do|else|while|until|if|elif|coproc)\s)\s*"
           rf"(((\S*/)?{WRAPPERS}|{SHELL_C})(\s+[^\s$`;&|]+)*?\s+|\w+=\S*\s+)*")
SHELL_FED_RE = re.compile(r"\|\s*(\S*/)?((busybox|su)\s+)?(ba|z|da|k|fi)?sh\b|\b(source|\.)\s+(<\(|/dev/stdin|/dev/fd|/proc/)")
HUMAN_WORD_RE = re.compile(rf"(^|[\s=;&|(]){HUMAN_SUBS}(\s|$|[;&|)])")
ENGINE_RES = (   # matched against the command with quotes and backslashes removed, so `"sdl\c"` reads `sdlc`
    re.compile(rf"(^|[\s;&|(/])sdlc\s+(-\S+\s+)*{HUMAN_SUBS}\b"),
    re.compile(rf"{CMD_POS}[^\s;&|]*[$`][^\s;&|]*\s+{HUMAN_SUBS}\b"),     # dynamic command word: $s, ${s}lc, $(…)
    re.compile(rf"{CMD_POS}(\$\([^)]*\)|`[^`]*`)\S*\s+{HUMAN_SUBS}\b"),  # $(which sdlc) hook, `which sdlc` close
    re.compile(r"(^|[\s;&|(/])sdlc\s+(-\S+\s+)*\S*[$`]"),              # dynamic subcommand: sdlc $x, sdlc $(…)
    re.compile(r"(\bfunction\s+\w+|\b\w+\s*\(\s*\))\s*\{[^}]*\bsdlc\b"),   # a function wrapping sdlc
    re.compile(r"\balias\s+\w+=\S*\bsdlc\b"),
    re.compile(r"\bxargs\b[^;&|\n]*\bsdlc\b"),
    re.compile(r"\b(cp|install|rsync|ln|mv|scp)\b[^;&|\n]*(\bbin/sdlc\b|\bsdlc_engine\b)"),   # copying the engine
    re.compile(r"\b(cat|tee)\b[^;&|\n]*(\bbin/sdlc\b|\bsdlc_engine\b)[^;&|\n]*>"),
    re.compile(r"-m\s+sdlc_engine\b|\bsdlc_engine\.|\b(import|from)\s+sdlc_engine\b"),
)
TRAILER_RE = re.compile(r"AIOps-Approval\s*:")
FORMAT_TRAILER_RE = re.compile(r"AIOps-\S*[%$]\S*:|\w+=\S*AIOps-")      # printf 'AIOps-%s:', AIOps-$x:, m=AIOps-…
MARKERS = r"(CLAUDECODE|CLAUDE_CODE_CHILD_SESSION)"
ENV_RES = (
    re.compile(rf"(?<![\w$]){MARKERS}="),                                # an assignment, not `[ $CLAUDECODE = 1 ]`
    re.compile(rf"\bunset\b[^;&|\n]*\b{MARKERS}\b"),
    re.compile(rf"(\s-u\s*|--unset[=\s]+){MARKERS}\b"),
    re.compile(r"\benv\s+(-\S+\s+)*(-i|--ignore-environment|-)(\s|$)"),
    re.compile(rf"\b(export|declare|typeset|readonly|local)\b[^;&|\n]*\b{MARKERS}\b"),   # export -n, declare +x, …
    # computed marker names: `unset ${a}CODE`, `unset CLAUDE{CODE,}`, `unset CLAUDE*`, printf-built `CLAUDE%s`
    re.compile(r"\bunset\b[^;&|\n]*\s(\$|[^\s$\[]*[{*?%])"),
    re.compile(r"\benv\b[^;&|\n]*\s(-u\s*|--unset[=\s]+)(\$|[^\s$]*[{*?%])"),
    re.compile(r"\b(export|declare|typeset)\b[^;&|\n]*\s(-n|\+x)\b[^;&|\n]*\s(\$|[^\s$]*[{*?%])"),
    re.compile(r"\bexec\s+-\w*c"),                                    # bash's own empty-environment exec
)


SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}


def _dynamic_engine_call(cmd, plain):
    """A human-only subcommand word anywhere, with a command word the parser can't read: `$s`, `${s}lc`, `$(…)`, or a
    glob/brace (`bin/sdl?`, `sdl{c,}`) after any wrappers and assignments; or text piped or sourced into a shell."""
    if not HUMAN_WORD_RE.search(plain):
        return False
    if SHELL_FED_RE.search(plain) and re.search(rf"([$`?*\[{{]\S*|sdl\S*)\s+{HUMAN_SUBS}\b", plain):
        return True
    for words, _ in segments(tokenize(cmd)):
        i = 0
        while i < len(words) and (words[i] in WRAPPER_WORDS or re.match(r"^[A-Za-z_]\w*=", words[i])
                                  or re.match(r"^python[\d.]*$", Path(words[i]).name)
                                  or (i and words[i - 1] in WRAPPER_WORDS and words[i].startswith("-"))):
            i += 1
        if i < len(words) and re.search(r"[$`?*\[{]", words[i].split()[0] if words[i].split() else ""):
            return True
    return False


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
    target_dir = _target_directory(args)
    if name in ALL_TARGETS:
        return nonopt
    if name in ("chmod", "chown", "chgrp"):
        return nonopt[1:]
    if name == "mv":
        return nonopt + target_dir
    if name in DEST_TARGET:
        return target_dir or nonopt[-1:]
    if name == "dd":
        return [a[3:] for a in args if a.startswith("of=")]
    if name in ("curl", "wget"):
        return [t for t in _download_targets(name, args) if t != "-"]
    if name == "find" and any(a in FIND_ACTIONS for a in args):
        return args[:next((i for i, a in enumerate(args) if a.startswith("-") or a in ("(", "!")), len(args))]
    inplace = (name in INPLACE and any(re.match(r"^-[a-zA-Z]*i", a) or a.startswith("--in-place") for a in args)) \
        or (name in ("awk", "gawk") and _awk_inplace(args))
    if inplace:
        return [a for a in nonopt if (Path(cwd) / a).is_file()]
    return []


def _download_targets(name, args):
    """Files curl (-o/--output) or wget (-O/--output-document) would write."""
    short, long = ("o", "--output") if name == "curl" else ("O", "--output-document")
    out = []
    for i, a in enumerate(args):
        if a.startswith(long + "="):
            out.append(a.split("=", 1)[1])
        elif a == long and i + 1 < len(args):
            out.append(args[i + 1])
        elif re.match(r"^-[a-zA-Z]+$", a) and short in a[1:]:
            rest = a[a.index(short, 1) + 1:]
            if rest:
                out.append(rest)          # -oFILE / -sSLoFILE
            elif i + 1 < len(args):
                out.append(args[i + 1])   # -o FILE / -sSLo FILE
    return out


FIND_ACTIONS = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}


def _target_directory(args):
    """The DIR of `-t DIR`, `-tDIR`, `--target-directory DIR` or `--target-directory=DIR`."""
    for i, a in enumerate(args):
        if a in ("-t", "--target-directory") and i + 1 < len(args):
            return [args[i + 1]]
        if a.startswith("--target-directory="):
            return [a.split("=", 1)[1]]
        if re.match(r"^-t.+", a):
            return [a[2:]]
    return []


def _awk_inplace(args):
    return any((a == "-i" and i + 1 < len(args) and args[i + 1] == "inplace") or a in ("-iinplace", "--include=inplace")
               for i, a in enumerate(args))


GIT_COMMIT_VALUE_OPTS = {"-m", "--message", "-F", "--file", "-C", "--reuse-message", "-c", "--reedit-message",
                         "--author", "--date", "--fixup", "--squash", "-t", "--template", "--trailer", "--cleanup"}


def _git_commit_pathspecs(rest):
    """Paths named on a `git commit` command line (they get committed even if not staged)."""
    paths, i = [], 0
    while i < len(rest):
        a = rest[i]
        if a == "--":
            return paths + rest[i + 1:]
        if a in GIT_COMMIT_VALUE_OPTS or (re.match(r"^-[a-zA-Z]+$", a) and a[-1] in "mFCct"):
            i += 2
            continue
        if not a.startswith("-"):
            paths.append(a)
        i += 1
    return paths


def _git_sub(args, cwd):
    """(subcommand, its args, the directory git runs in after any `-C DIR`)."""
    i = 0
    while i < len(args):
        if args[i] in ("-C", "--work-tree") and i + 1 < len(args) or args[i].startswith("--work-tree="):
            value = args[i].split("=", 1)[1] if "=" in args[i] else args[i + 1]
            d = Path(value).expanduser()
            cwd = d if d.is_absolute() else cwd / d
            i += 1 if "=" in args[i] else 2
        elif args[i] in ("-c", "--git-dir"):
            i += 2
        elif args[i].startswith("-"):
            i += 1
        else:
            return args[i], args[i + 1:], cwd
    return "", [], cwd


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
    plain = re.sub(r"[\\'\"]", "", cmd)
    if TRAILER_RE.search(plain) or (FORMAT_TRAILER_RE.search(plain) and "Approval" in plain
                                    and re.search(r"\bgit\b", plain)):   # also printf- or variable-built
        return _block("human gate", "approval commits are created only by a human approval.",
                      "ask the human to approve in their terminal (`<plugin>/bin/sdlc approve NNNN intent|spec|plan`, "
                      "the exact path is in the refusal message).")
    if any(r.search(plain) for r in ENV_RES):
        return _block("human gate", "changing CLAUDECODE / CLAUDE_CODE_CHILD_SESSION (or clearing the environment) "
                      "would let human-only commands run as the agent.",
                      "leave the environment alone; human-only steps are run by the human.")
    if any(r.search(plain) for r in ENGINE_RES) or _dynamic_engine_call(cmd, plain):
        return _block("human gate", "`sdlc approve|close|unlock|hook|legacy-approvals` are human-only (or hook-only).",
                      "stop and ask the human: they type `Intent|Spec|Plan Approved NNNN` in the prompt, "
                      "or run the command in their own terminal.")
    locked, reason, st = lock(root)
    on_main = current_branch(root) == config(root)["main_branch"]
    return _check_command(cmd, Path(cwd), root, locked, reason, st, on_main, depth=0)


PWD_RE = re.compile(r"\$\{PWD\}|\$PWD\b|\$\(\s*pwd\s*\)|`\s*pwd\s*`|(?<![\w/])~\+")
GLOB_CHARS = re.compile(r"[*?\[]")


BRACE_RE = re.compile(r"(?<!\$)\{([^{}]*,[^{}]*)\}")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
VAR_RE = re.compile(r"\$\{(\w+)\}|\$(\w+)")
DECLARERS = {"export", "declare", "typeset", "local", "readonly"}


def _braces(word):
    """Bash brace expansion of `{a,b}` lists, innermost first (a superset is fine here; `${…}` is left alone)."""
    m = BRACE_RE.search(word)
    if not m:
        return [word]
    out = []
    for alt in m.group(1).split(","):
        out += [w for w in _braces(word[:m.start()] + alt + word[m.end():]) if w not in out]
    return out


def _expand(target, cwd):
    """A write target as the shell would see it: $PWD / $(pwd) / ~+ resolved, braces and globs expanded."""
    out = []
    for t in _braces(PWD_RE.sub(lambda _m: str(cwd), target)):
        if not GLOB_CHARS.search(t):
            out.append(t)
            continue
        pattern = t if Path(t).is_absolute() else str(Path(cwd) / t)
        out += glob.glob(pattern) or [t]
    return out


def _find_hits_aiops(args, cwd, root):
    """True if a destructive `find` could reach `.aiops`: a start path inside it, or an ancestor of it whose
    name/path filters (or lack of filters) match something in the `.aiops` tree."""
    if not any(a in FIND_ACTIONS for a in args):
        return False
    starts = args[:next((i for i, a in enumerate(args) if a.startswith("-") or a in ("(", "!")), len(args))] or ["."]
    names = [(args[i + 1], a == "-iname") for i, a in enumerate(args[:-1]) if a in ("-name", "-iname")]
    paths = [(args[i + 1], a.startswith("-i")) for i, a in enumerate(args[:-1])
             if a in ("-path", "-ipath", "-wholename", "-iwholename")]
    aiops = root / ".aiops"
    for start in starts:
        rel = _rel(root, start, cwd)
        if rel is None:
            continue
        if _aiops_protected(rel):
            return True
        base = (root / rel).resolve() if rel != "." else root
        if not (aiops == base or base in aiops.parents):
            continue
        if not names and not paths:
            return True                                 # everything below the start, .aiops included
        entries = [aiops] + list(aiops.rglob("*"))
        for e in entries:
            shown = f"{start.rstrip('/')}/{e.relative_to(base).as_posix()}"
            if any(_fnmatch(e.name, n, ci) for n, ci in names) or any(_fnmatch(shown, q, ci) for q, ci in paths):
                return True
    return False


def _fnmatch(name, pattern, ci):
    """find's matching: -name/-path are case-sensitive, their -i* forms are not."""
    return fnmatchcase(name.lower(), pattern.lower()) if ci else fnmatchcase(name, pattern)


PATCH_PATH_RE = re.compile(r"^(?:diff --git a/(\S+) b/(\S+)|(?:---|\+\+\+) ([^\t\n ]+)|rename (?:from|to) (\S+))", re.M)
PATCH_VALUE_OPTS = {"-p", "-o", "--output", "-r", "--reject-file", "-B", "--prefix", "-D", "--ifdef", "-F", "--fuzz",
                    "-z", "--suffix", "-V", "--version-control", "--exclude", "--include"}
AM_CONTROL = {"--continue", "--abort", "--skip", "--quit", "--show-current-patch", "--resolved", "-r"}


def _patch_check(args, cwd, root, git_am=False):
    """Why applying this patch is refused: "aiops" if it could write into the .aiops tree (any `-pN` strip level,
    under any `--directory`/`-d`), "stdin" if the patch can't be read, else None."""
    if git_am and any(a in AM_CONTROL or a.startswith("--show-current-patch") for a in args):
        return None
    dirs, files, stdin, i = [""], [], False, 0
    while i < len(args):
        a = args[i]
        if a.startswith(("--directory=", "--input=")):
            (dirs if a.startswith("--d") else files).append(a.split("=", 1)[1])
        elif a in ("-d", "--directory", "-i", "--input") and i + 1 < len(args):
            (dirs if a in ("-d", "--directory") else files).append(args[i + 1])
            i += 1
        elif re.match(r"^-[di].+", a):
            (dirs if a[1] == "d" else files).append(a[2:])
        elif a in PATCH_VALUE_OPTS:
            i += 1
        elif a == "-":
            stdin = True
        elif not a.startswith("-"):
            files.append(a)
        i += 1
    for f in files:
        rel = _rel(root, f, cwd)
        if rel and _aiops_protected(rel):
            return "aiops"                             # `patch .aiops/…/plan.md < x`: the file patched in place
    readable = [Path(cwd) / f for f in files if (Path(cwd) / f).is_file()]
    if stdin or not readable:
        return "stdin"
    for f in readable:
        for m in PATCH_PATH_RE.finditer(f.read_text(errors="replace")):
            for g in filter(None, m.groups()):
                if g.startswith('"') and g.endswith('"'):   # git's C-quoted names: "a/.aio\160s/…"
                    g = g[1:-1].encode("latin-1", "backslashreplace").decode("unicode_escape")
                parts = g.split("/")
                for k in range(len(parts)):            # every -pN strip level
                    for d in dirs:
                        rel = _rel(root, "/".join(filter(None, [d] + parts[k:])), cwd)
                        if rel and _aiops_protected(rel):
                            return "aiops"
    return None


def _extract_dirs(name, args):
    """Where `tar -x` / `unzip` extract to ("." when no directory is given), or [] if the command doesn't extract."""
    if name == "unzip":
        if any(a in ("-l", "-t", "-v", "-Z", "-p") for a in args):
            return []
        dirs = [args[i + 1] for i, a in enumerate(args[:-1]) if a == "-d"] + [a[2:] for a in args if a.startswith("-d")
                                                                              and len(a) > 2]
        return dirs or ["."]
    if name == "tar":
        if not any(a in ("--extract", "--get") or re.match(r"^-[A-Za-z]*x", a) for a in args) \
                and not (args and not args[0].startswith("-") and "x" in args[0]):
            return []
        dirs = [args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-C", "--directory")] + \
            [a[2:] for a in args if a.startswith("-C") and len(a) > 2] + \
            [a.split("=", 1)[1] for a in args if a.startswith("--directory=")]
        return dirs or ["."]
    return []


SIGNING_CONFIG_RE = re.compile(r"^(user\.signingkey|gpg\..+|core\.(hookspath|fsmonitor|attributesfile|sshcommand|editor|pager)|sequence\.editor|"
                               r"include\..+|includeif\..+|filter\..+|alias\..+|diff\..+)$", re.I)
GIT_CONFIG_READS = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "-l", "--list"}   # not --path/-z: formats
GIT_CONFIG_WRITES = {"--unset", "--unset-all", "--replace-all", "--add", "--rename-section", "--remove-section",
                     "-e", "--edit"}
GIT_CONFIG_VALUE_OPTS = {"-f", "--file", "--blob", "--type", "--default", "--comment", "--value"}
GIT_CONFIG_SUB_WRITES = {"set", "unset", "rename-section", "remove-section", "edit"}


def _git_config_writes_signing(rest, cwd, root):
    """`git config …` that sets or removes a key able to run code or change signing, or writes a file under
    `.git/` (`-f .git/config`). Reads stay allowed. Knows the `git config set|unset|get` subcommand form."""
    opts, words, files, i = [], [], [], 0
    while i < len(rest):
        a = rest[i]
        if a in GIT_CONFIG_VALUE_OPTS and i + 1 < len(rest):
            files += [rest[i + 1]] if a in ("-f", "--file") else []
            opts.append(a)
            i += 2
            continue
        if a.startswith("--file="):
            files.append(a.split("=", 1)[1])
        (opts if a.startswith("-") else words).append(a)
        i += 1
    write = any(o in GIT_CONFIG_WRITES for o in opts)
    if words and words[0] in GIT_CONFIG_SUB_WRITES:
        write, words = True, words[1:]
    elif words and words[0] in ("get", "list"):
        return False
    if not write and any(o in GIT_CONFIG_READS for o in opts):
        return False
    write = write or len(words) >= 2                       # `git config key value`
    in_git_dir = any((r := _rel(root, f, cwd)) is not None and (r == ".git" or r.startswith(".git/")) for f in files)
    if write and (in_git_dir or (not words and not files)):   # `git config -e` / `git config edit` opens .git/config
        return True
    return write and bool(words) and bool(SIGNING_CONFIG_RE.match(words[0]))


def _secret_template(rel):
    """`.env.example|.sample|.template` and public keys are documentation, not secrets (mirrors hooks/lib.sh)."""
    name = rel.rsplit("/", 1)[-1]
    return name in (".env.example", ".env.sample", ".env.template") or name.endswith(".pub")


def _in_plugin(target, cwd, root):
    """True for a write into the installed plugin (not when the project *is* the plugin checkout)."""
    if PLUGIN_ROOT.resolve() == root.resolve():
        return False
    p = Path(target).expanduser()
    p = (Path(cwd) / p) if not p.is_absolute() else p
    try:
        p.resolve().relative_to(PLUGIN_ROOT.resolve())
        return True
    except ValueError:
        return False


def _check_command(cmd, cwd, root, locked, reason, st, on_main, depth):
    assigned = {}
    for words, redirs in segments(tokenize(PWD_RE.sub(lambda _m: shlex.quote(str(cwd)), cmd))):
        words, redirs = ([VAR_RE.sub(lambda m: assigned.get(m[1] or m[2], m[0]), w) for w in ws]
                         for ws in (words, redirs))
        bare = [w for w in (words[1:] if words[:1] and words[0] in DECLARERS else words) if not w.startswith("-")]
        if bare and not redirs and all(ASSIGN_RE.match(w) for w in bare):   # `d=.aiops; rm -rf $d`
            assigned.update(w.split("=", 1) for w in bare)
            continue
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
        targets = [e for t in redirs + write_targets(words, cwd) for e in _expand(t, cwd)]
        if words and Path(words[0]).name == "find" and _find_hits_aiops(words[1:], cwd, root):
            return _block("artifacts", "this `find` would delete or rewrite part of the .aiops tree.",
                          "narrow it (e.g. `-not -path './.aiops/*'`), or ask the human to remove artifacts.")
        if words:
            targets += _extract_dirs(Path(words[0]).name, words[1:])
        for t in targets:
            if t.startswith("/dev/"):
                continue
            if _in_plugin(t, cwd, root):
                return _block("toolchain", f"`{' '.join(words)[:80]}` writes into the installed plugin ({t}).",
                              "the plugin's code is what the human runs to approve; change it through its own repo.")
            rel = _rel(root, t, cwd)
            if rel is not None and (rel == ".git" or rel.startswith(".git/")):
                return _block("toolchain", f"shell writes to '{rel}' (git config, hooks) can hijack signing.",
                              "use git commands; ask the human for config or hook changes.")
            if rel is None:   # outside the repo: still never write secret material (~/.ssh/config, ~/.aws/…)
                p = Path(t).expanduser()
                p = p if p.is_absolute() else Path(cwd) / p
                if glob_hit(str(p), globs(root, "secret-paths")) and not _secret_template(p.name):
                    return _block("protected", f"'{p}' is secret material; shell writes count too.",
                                  "ask the human to change credentials themselves.")
                continue
            if _aiops_protected(rel):
                return _block("artifacts", f"shell writes to '{rel}' bypass the gate guard.",
                              "edit artifacts with the Edit/Write tools; engine state changes go through `sdlc`.")
            hit = glob_hit(rel, globs(root, "protected-paths")) or \
                (not _secret_template(rel) and glob_hit(rel, globs(root, "secret-paths")))
            if hit:
                return _block("protected", f"'{rel}' is protected ({hit[1] or hit[0]}); shell writes count too.",
                              "propose the change in chat; a human edits protected files.")
            if locked and _code_paths(root, [rel]):
                return _block("read-only lock", f"`{' '.join(words)[:80]}` writes '{rel}': {reason}.",
                              lock_procedure(st))
        if not words:
            continue
        name, args = Path(words[0]).name, words[1:]
        why = _patch_check(args, cwd, root) if name == "patch" else None
        if why:
            return _block("artifacts", "this `patch` touches .aiops/, which bypasses the gate guard." if why == "aiops"
                          else "`patch` from a pipe can't be inspected for .aiops/ changes.",
                          "edit artifacts with the Edit/Write tools, or pass the patch file by name (`-i` or `<`).")
        if name == "gh" and args[:1] == ["api"] and any(re.search(r"/pulls/\d+/merge\b|/merges\b", a) for a in args):
            return _block("final gate", "merging through the GitHub API is the human's decision.",
                          "leave the PR for a CODEOWNER to review and merge.")
        if name == "git":
            sub, rest, gcwd = _git_sub(args, cwd)
            if sub == "config" and _git_config_writes_signing(rest, gcwd, root):
                return _block("toolchain", "git signing, hook, monitor, filter and include settings are human-owned "
                              "(they decide who signs approvals, and what runs inside an approval).",
                              "ask the human to change git config themselves (globally).")
            why = _patch_check(rest, gcwd, root, git_am=sub == "am") if sub in ("apply", "am") else None
            if why:
                return _block("artifacts", f"`git {sub}` with a patch touching .aiops/ bypasses the gate guard."
                              if why == "aiops" else f"`git {sub}` from stdin can't be inspected for .aiops/ changes.",
                              "edit artifacts with the Edit/Write tools, or apply a patch file by name.")
            if sub in GIT_TREE_WRITERS:
                rels = [r for r in (_rel(root, a, gcwd) for a in rest if not a.startswith("-")) if r]
                hit = next((r for r in rels if _aiops_protected(r)), None)
                if hit:
                    return _block("artifacts", f"`git {sub}` on '{hit}' would delete or rewrite an artifact outside the "
                                  "gate guard.", "edit artifacts with the Edit/Write tools; ask the human to remove one.")
                pglobs = globs(root, "protected-paths")
                prot = next((r for r in rels if glob_hit(r, pglobs)
                             or any(g.startswith(r.rstrip("/") + "/") for g, _ in pglobs)), None)   # a directory
                if prot:
                    return _block("protected", f"`git {sub}` would rewrite '{prot}', a protected path.",
                                  "propose the change in chat; a human edits protected files.")
            if on_main and sub in GIT_MAIN_FORBIDDEN:
                return _block("final gate", f"`git {sub}` on {config(root)['main_branch']}: merging is the human's decision.",
                              "leave the branch for the human to review and merge (/zouj-ai-sdlc:pr).")
            if sub == "commit":
                for i, a in enumerate(rest):
                    f = rest[i + 1] if a in ("-F", "--file") and i + 1 < len(rest) else \
                        a.split("=", 1)[1] if a.startswith("--file=") else None
                    path = (gcwd / f) if f and f != "-" else None
                    if path and path.is_file() and "AIOps-Approval" in path.read_text(errors="replace"):
                        return _block("human gate", "approval commits are created only by a human approval.",
                                      "ask the human to type the approval phrase (e.g. `Plan Approved 0001`).")
            if not locked:
                continue
            checkout_paths = sub == "checkout" and _code_paths(root, [
                r for r in (_rel(root, a, gcwd) for a in rest if not a.startswith("-") and (gcwd / a).is_file()) if r])
            if sub in GIT_LOCKED or (sub == "checkout" and "--" in rest) or checkout_paths:
                return _block("read-only lock", f"`git {sub}` changes the working tree: {reason}.", lock_procedure(st))
            if sub == "add":
                paths = [a for a in rest if not a.startswith("-")]
                if not paths or any(a in ("-A", "--all", "-u", "--update") for a in rest) or "." in paths:
                    rels = _git_changed(root, staged_only=False)
                else:
                    rels = [_rel(root, p, gcwd) for p in paths]
                if bad := _code_paths(root, rels):
                    return _block("read-only lock", f"`git add` would stage code ({', '.join(bad[:3])}): {reason}.",
                                  lock_procedure(st))
            if sub == "commit":
                all_flag = any(re.match(r"^-[a-zA-Z]*a", a) or a == "--all" for a in rest)
                rels = _git_changed(root, staged_only=not all_flag) + \
                    [_rel(root, p, gcwd) for p in _git_commit_pathspecs(rest)]
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
        if name in ("patch", "unzip") or (name == "tar" and _extract_dirs(name, args)):
            return _block("read-only lock", f"`{name}` writes files: {reason}.", lock_procedure(st))
    return None


__all__ = ["check_edit", "check_bash", "check_artifact", "lock_procedure", "active_dir", "evaluate"]
