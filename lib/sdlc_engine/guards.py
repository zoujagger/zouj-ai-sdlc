"""PreToolUse decisions. Each check returns None (allow) or a block message stating the reason and the procedure.

Rules (only in repos initialized with `.aiops/`):
  * Artifacts: agents create them as Draft, in order (spec needs an approved intent, plan an approved spec,
    review an approved plan), and never write a gate status or `approved-*` fields.
  * Read-only lock: in states 1-3 (and with no active intent) nothing outside `.aiops/` and the exempt globs
    may be written, by Edit/Write or by shell commands.
  * Always: no shell writes to artifacts or `.aiops/config|state`, no forged approvals, no merging into main.
"""
import glob
import os
import posixpath
import re
import shlex
from fnmatch import fnmatchcase
from pathlib import Path

from . import artifacts as A
from .shell import segments, tokenize
from .machine import (PLUGIN_ROOT, SCHEMAS, active_dir, config, current_branch, evaluate, gate, git, glob_hit, globs,
                      initialized, lock, phrase, project_root)

ARTIFACT_RE = re.compile(r"^\.aiops/(\d{4}-[a-z0-9-]+)/(intent|spec|plan|review)\.md$")
GUARDED_RE = re.compile(r"^\.aiops/(config(/|\.json$)|state(/|$)|install-state\.json$)")
INTENT_TREE_RE = re.compile(r"^\.aiops(/\d{4}-[a-z0-9-]+(/.*)?)?$")


def _aiops_protected(rel):
    """`.aiops` itself, an intent folder or anything in it, or engine state/config: never a shell target."""
    return bool(INTENT_TREE_RE.match(rel) or GUARDED_RE.match(rel))


def _block(rule_id, reason, procedure):
    """The block message: the rule id (defaults/rules), the reason and the procedure."""
    return f"BLOCKED [{rule_id}] by zouj-ai-sdlc: {reason}\nProcedure: {procedure} (details: `sdlc why {rule_id}`)"


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
        return _block("G-TOOL-01", f"'{path}' is inside the installed plugin, which the human runs to approve.",
                      "change the plugin through its own repo.")
    rel = _rel(root, path, cwd)
    if rel is None:
        return None
    if GUARDED_RE.match(rel):
        return _block("G-ART-01", f"'{rel}' is engine state or human-owned configuration.",
                      "propose the change in chat; a human edits .aiops/config. State changes go through `sdlc`.")
    m = ARTIFACT_RE.match(rel)
    if m:
        new = simulate(data.get("tool_name", ""), ti, root / rel)
        return None if new is None else check_artifact(root / ".aiops" / m.group(1), m.group(2), new)
    if rel.startswith(".aiops/") or glob_hit(rel, globs(root, "readonly-exempt")):
        return None
    locked, reason, st = lock(root)
    if locked:
        return _block("G-LOCK-01", f"cannot edit '{rel}': {reason}.", lock_procedure(st))
    return None


def check_artifact(d, kind, new_text):
    schema = SCHEMAS[kind]
    ident = d.name[:4]
    path = d / f"{kind}.md"
    new = A.parse(new_text)
    gate_value = schema["gate"]
    if new.get("id") and new.get("id") != ident:
        return _block("G-ART-02", f"`id: {new.get('id')}` in {kind}.md must match its folder ({ident}).",
                      "keep `id` equal to the folder number; artifacts can't be moved between intents.")
    if not path.is_file():
        if schema["requires"]:
            ok, why = gate(d, schema["requires"])
            if not ok:
                req = schema["requires"]
                return _block("G-GATE-01", f"{kind}.md needs an approved {req}.md first ({req}.md: {why}).",
                              f"finish {req}.md and ask the human to type `{phrase(req, ident)}`.")
        if gate_value and new.get("status") not in ("", "Draft"):
            return _block("G-GATE-02", f"a new {kind}.md must start as `status: Draft`.",
                          "write it as Draft; the human approves it by typing the approval phrase.")
        if any(new.get(f) for f in A.APPROVAL_FIELDS):
            return _block("G-GATE-03", "approved-* fields are written only by a human approval.",
                          "leave them out; they are stamped when the human approves.")
        return None
    old = A.parse(path.read_text())
    if old.get("id") != new.get("id"):
        return _block("G-ART-03", f"`id` in {kind}.md can't be changed.", "keep `id` equal to the folder number.")
    for f in A.APPROVAL_FIELDS:
        if old.get(f) != new.get(f):
            return _block("G-GATE-04", f"`{f}` in {kind}.md can only be written by a human approval.",
                          f"leave approval fields untouched. The human types `{phrase(kind, ident)}`."
                          if gate_value else "leave approval fields untouched.")
    if gate_value and new.get("status") != old.get("status") and new.get("status") != "Draft":
        return _block("G-GATE-05", f"setting {kind}.md to `status: {new.get('status')}` is a human decision.",
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
HUMAN_WORD_RE = re.compile(rf"(^|[\s=;&|(]|:-){HUMAN_SUBS}(\s|$|[;&|)}}])")   # also a `${x:-approve}` default
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
    """Per simple command: a command word the parser can't read (`$s`, `${s}lc`, a glob/brace like `bin/sdl?`, after
    wrappers, keywords and assignments) whose first argument is a human-only subcommand, or is itself dynamic while
    a human-only word is assigned somewhere (`x=approve; $s $x`). Also text piped or sourced into a shell."""
    if not HUMAN_WORD_RE.search(plain):
        return False
    if SHELL_FED_RE.search(plain) and re.search(rf"([$`?*\[{{]\S*|sdl\S*)\s+{HUMAN_SUBS}\b", plain):
        return True
    human = re.compile(rf"^{HUMAN_SUBS}$")
    assigned = re.search(rf"\w+={HUMAN_SUBS}\b", plain)
    for words, _ in segments(tokenize(cmd)):
        i = 0
        while i < len(words) and (words[i] in WRAPPER_WORDS or re.match(r"^[A-Za-z_]\w*=", words[i])
                                  or re.match(r"^python[\d.]*$", Path(words[i]).name)
                                  or (i and words[i - 1] in WRAPPER_WORDS and words[i].startswith("-"))):
            i += 1
        if i + 1 < len(words) and Path(words[i]).name in SHELLS and re.search(r"[$`?*\[{]", words[i + 1]):
            i += 1                                           # `sh "$(command -v sdlc)" approve`
        head = [] if i >= len(words) else [words[i]] if re.match(r"^(\$\(|`)", words[i]) else words[i].split()
        if not head or not re.search(r"[$`?*\[{]", head[0]):
            continue
        rest = head[1:] + words[i + 1:]                      # `eval "$s approve …"` keeps its words in one token
        first = next((w for w in rest if not w.startswith("-")), "")
        if human.match(first) or (assigned and re.search(r"[$`]", first)) or re.search(r"\$[@*]|\$\{\w+:?[-=]", first):
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


# Commands that run the rest of their arguments as a command: their options that take a value, and how many plain
# operands come before the command (`timeout 5 rm …`, `flock /tmp/l rm …`). 0005 review round 1: a wrapper must
# never hide a write.
WRAPPER_OPTS = {
    "timeout": {"-s", "--signal", "-k", "--kill-after"}, "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "-P", "-u", "--class", "--classdata", "--pid", "--pgid", "--uid"},
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"}, "chrt": set(), "taskset": set(),
    "flock": {"-w", "--timeout", "-E", "--conflict-exit-code"}, "setsid": set(), "nohup": set(), "unbuffer": set(),
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-U", "-r", "-t", "-T", "-D", "--user", "--group", "--host", "--prompt",
             "--chdir", "--close-from", "--role", "--type", "--command-timeout"},
    "doas": {"-u", "-C"}, "command": set(), "builtin": set(), "time": {"-f", "--format", "-o", "--output"},
    "exec": {"-a"}, "xargs": {"-n", "-I", "-P", "-L", "-d", "-a", "-E", "-s", "--max-args", "--max-procs",
                              "--delimiter", "--arg-file", "--max-lines", "--max-chars", "--replace"},
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}, "busybox": set(),
    "strace": {"-o", "-e", "-p", "-s", "-u", "-P", "-E"}, "ltrace": {"-o", "-e", "-p", "-s", "-u"},
}
WRAPPER_OPERANDS = {"timeout": 1, "chrt": 1, "taskset": 1, "flock": 1}


def _strip_prefix(words):
    """The words after any leading keywords, assignments and wrappers (with their options and operands)."""
    i = 0
    while i < len(words):
        w = words[i]
        name = Path(w).name
        if name in WRAPPER_OPTS:
            i += 1
            while i < len(words) and words[i].startswith("-") and words[i] != "-":
                takes = words[i] in WRAPPER_OPTS[name]
                i += 2 if takes and "=" not in words[i] else 1
            i += WRAPPER_OPERANDS.get(name, 0)
            continue
        if w in PREFIXES or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w):
            i += 1
            continue
        break
    return words[i:]


GIT_CONFIG_ENV_RE = re.compile(r"^GIT_CONFIG(_GLOBAL|_SYSTEM)?=")


def _git_config_outside(rest, cwd, root, env_file):
    """True if this `git config` writes a file other than the repo's own: --global/--system (any abbreviation git
    accepts, e.g. --glob), -f/--file outside the repo, or GIT_CONFIG*= set before the command."""
    if env_file:
        return True
    for i, a in enumerate(rest):
        if len(a) >= 4 and ("--global".startswith(a) or "--system".startswith(a)):
            return True
        f = rest[i + 1] if a in ("-f", "--file") and i + 1 < len(rest) else \
            a.split("=", 1)[1] if a.startswith("--file=") else None
        if f is not None and _rel(root, os.path.expanduser(f), cwd) is None:
            return True
    return False


def _holds_toolchain(p):
    """True if the directory p is the home directory, or holds a toolchain, secret or plugin directory: a copy or an
    extraction into it can overwrite what runs when the human approves."""
    real = os.path.realpath(str(p))
    home = os.path.realpath(str(Path.home()))
    inside = [os.path.join(home, d) for d in (".ssh", ".config", ".claude", ".aws", "bin", ".local/bin", ".gnupg")]
    inside += [os.path.realpath(str(PLUGIN_ROOT))] + _writable_path_dirs()
    return real == home or home.startswith(real + "/") or any(c == real or c.startswith(real + "/") for c in inside)


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
        return [a for a in nonopt if (Path(cwd) / os.path.expanduser(HOME_VAR_RE.sub(str(Path.home()), a))).is_file()]
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


# `sdlc init|setup` anywhere on the line: fed to a shell (`echo … | sh`, `<<<`), behind a runner the guard doesn't know
# (`setarch`, `uv run`) or after `find -execdir`, it still runs. A line that only mentions it is matched too.
SCAFFOLD_RE = re.compile(r"(^|[^\w-])sdlc\s+(-\S+\s+)*(init|setup|upgrade|repair|uninstall)\b")
# a real uninstall is human-only; its --dry-run is open to anyone (group 3: the rest of that simple command)
UNINSTALL_RE = re.compile(r"(^|[\s;&|(/])sdlc\s+(-\S+\s+)*uninstall\b([^;&|\n]*)")
RELOCATE_RE = re.compile(r"(^|[\s;&|(])(cd|pushd|popd)(\s|$)"
                         r"|\b(GIT_[A-Z_]+|CLAUDE_PROJECT_DIR|HOME|SDLC_HOOK_PROFILE|AIOPS_INTENT)="
                         r"|(^|\s)(-C\S*|--chdir\S*|-execdir|-okdir)(\s|$)")


def _scaffold_elsewhere(cwd, plain):
    """The agent's `sdlc init|setup|upgrade|repair|uninstall` runs only in this session's repo. The hook knows the session's project
    (CLAUDE_PROJECT_DIR); the CLI, started from the agent's shell, doesn't. So a command that moves (cd, pushd, -C,
    env --chdir, find -execdir) or sets a variable the engine reads for its root (GIT_*, CLAUDE_PROJECT_DIR, HOME) is
    refused, and so is one whose working directory is in another repo. Matching the whole line also refuses a line that
    only mentions `sdlc setup` next to a `cd`: that fails closed, and splitting the command avoids it."""
    session = os.environ.get("CLAUDE_PROJECT_DIR")
    if not session or not SCAFFOLD_RE.search(plain):
        return None
    if RELOCATE_RE.search(plain) or project_root(cwd) != project_root(session):
        return _block("G-SCAF-01", "`sdlc init|setup|upgrade|repair|uninstall` run by the agent may act only on "
                      "this session's repo "
                      f"({project_root(session)}), from there, without cd, -C, --chdir, -execdir or GIT_*, "
                      "CLAUDE_PROJECT_DIR or HOME settings.",
                      "run it from the project as a command of its own; another repo is set up by the human in "
                      "their own terminal.")
    return None


def check_bash(data):
    cmd = (data.get("tool_input") or {}).get("command", "")
    cwd = data.get("cwd") or "."
    plain = re.sub(r"[\\'\"]", "", cmd)
    elsewhere = _scaffold_elsewhere(cwd, plain)     # before the initialized check: the other repo may not be
    if elsewhere:
        return elsewhere
    root = project_root(cwd)
    if not cmd.strip():
        return None
    if not initialized(root):            # SDLC gates dormant; the safety checks run in every repo (0005, gap 2)
        return _check_command(cmd, Path(cwd), root, False, "", None, False, depth=0, gates=False)
    if TRAILER_RE.search(plain) or (FORMAT_TRAILER_RE.search(plain) and "Approval" in plain
                                    and re.search(r"\bgit\b", plain)):   # also printf- or variable-built
        return _block("G-GATE-06", "approval commits are created only by a human approval.",
                      "ask the human to approve in their terminal (`<plugin>/bin/sdlc approve NNNN intent|spec|plan`, "
                      "the exact path is in the refusal message).")
    if any(r.search(plain) for r in ENV_RES):
        return _block("G-ENV-02", "changing CLAUDECODE / CLAUDE_CODE_CHILD_SESSION (or clearing the environment) "
                      "would let human-only commands run as the agent.",
                      "leave the environment alone; human-only steps are run by the human.")
    if any("--dry-run" not in m.group(3).split("#", 1)[0].split() for m in UNINSTALL_RE.finditer(plain)):
        return _block("G-GATE-07", "`sdlc uninstall` removes the workflow's files; it is human-only.",
                      "preview it with `sdlc uninstall --dry-run`; the human runs the real uninstall in their own "
                      "terminal.")
    if any(r.search(plain) for r in ENGINE_RES) or _dynamic_engine_call(cmd, plain):
        return _block("G-GATE-07", "`sdlc approve|close|unlock|hook|legacy-approvals` are human-only (or hook-only).",
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


HOME_VAR_RE = re.compile(r"\$\{(HOME|XDG_CONFIG_HOME)\}|\$(HOME|XDG_CONFIG_HOME)\b")


def _expand(target, cwd):
    """A write target as the shell would see it: $PWD / $(pwd) / ~+ / ~ / $HOME / $XDG_CONFIG_HOME resolved, braces and
    globs expanded."""
    out = []
    target = HOME_VAR_RE.sub(lambda m: os.environ.get(m[1] or m[2]) or str(Path.home() / ".config"
                                                                           if (m[1] or m[2]) == "XDG_CONFIG_HOME"
                                                                           else Path.home()), target)
    target = os.path.expanduser(target) if target.startswith("~") and not target.startswith("~+") else target
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


INCOMING_GUARDED_RE = re.compile(r"^(\.aiops/(config(/|\.json$)|install-state\.json$)|\.claude/settings\.json$)")


def _incoming_problem(root, rels):
    """The first incoming path that is human-owned config or protected, else None. Intent folders (approvals) pass."""
    pglobs = globs(root, "protected-paths")
    for rel in rels:
        rel = posixpath.normpath(rel.lstrip("/"))
        if rel.startswith("../") or rel == "..":
            continue                                   # lands outside the repo
        if INCOMING_GUARDED_RE.match(rel) or glob_hit(rel, pglobs):
            return rel
    return None


def _archive_file(name, args):
    """The archive a `tar -x` / `unzip` reads, else None."""
    if name == "unzip":
        skip = False
        for a in args:
            if skip:
                skip = False
            elif a == "-d":
                skip = True
            elif not a.startswith("-"):
                return a
        return None
    for i, a in enumerate(args):                       # tar
        if a in ("-f", "--file") and i + 1 < len(args):
            return args[i + 1]
        if a.startswith("--file="):
            return a.split("=", 1)[1]
        if a.startswith("-") and not a.startswith("--") and "f" in a:      # -xzf x.tgz, -xzfx.tgz
            rest = a[a.index("f") + 1:]
            return rest or (args[i + 1] if i + 1 < len(args) else None)
        if i == 0 and not a.startswith("-") and "f" in a:                  # old style: `tar xfz x.tgz`
            return args[1] if len(args) > 1 else None
    return None


def _archive_members(path):
    """(member names, has link members) of a tar (any compression) or zip archive, or None if it can't be read."""
    import tarfile
    import zipfile
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
                return [i.filename for i in infos], any((i.external_attr >> 16) & 0o170000 == 0o120000 for i in infos)
        with tarfile.open(path) as t:
            members = t.getmembers()
            return [m.name for m in members], any(m.issym() or m.islnk() for m in members)
    except (OSError, tarfile.TarError, zipfile.BadZipFile, EOFError):
        return None


TAR_REWRITE_RE = re.compile(r"^(--transform|--xform|--absolute-names$|-P$|-[A-Za-z]*P[A-Za-z]*$)")


def _strip_count(args):
    for i, a in enumerate(args):
        if a.startswith("--strip-components=") or a.startswith("--strip="):
            return int(a.split("=", 1)[1]) if a.split("=", 1)[1].isdigit() else -1
        if a in ("--strip-components", "--strip") and i + 1 < len(args):
            return int(args[i + 1]) if args[i + 1].isdigit() else -1
    return 0


def _incoming_archive(name, args, cwd, root):
    """Why extracting this archive into the repo is refused (G-FILE-06), else None."""
    dests = [d for d in _extract_dirs(name, args) if _rel(root, d, cwd) is not None]
    if not dests:
        return None                                    # not extracting, or only outside the repo
    archive = _archive_file(name, args)
    listing = _archive_members(Path(cwd) / os.path.expanduser(archive)) if archive else None
    strip = _strip_count(args) if name == "tar" else 0
    if listing is not None:
        if listing[1]:
            return "the archive holds symlink or hardlink members, which can redirect where files land"
        if name == "tar" and any(TAR_REWRITE_RE.match(a) for a in args if a != args[0] or a.startswith("-")):
            return "`tar --transform` / `-P` rewrites where members land, so the archive can't be inspected"
        if strip < 0:
            return "`--strip-components` has no count the guard can read"
    members = None if listing is None else [
        "/".join(Path(m.lstrip("/")).parts[strip:]) for m in listing[0] if len(Path(m.lstrip("/")).parts) > strip]
    if members is None:
        # tar and unzip drop `..` member names, so an unreadable archive matters only where guarded paths lie below
        pglobs = globs(root, "protected-paths")
        for d in dests:
            base = _rel(root, d, cwd)
            prefix = "" if base in ("", ".") else base.rstrip("/") + "/"
            if not prefix or any(g.startswith(prefix) for g in (".aiops/", ".claude/")) \
                    or any(g.startswith(prefix) for g, _ in pglobs):
                return f"`{name}` reads an archive that can't be inspected ({archive or 'no archive named'})"
        return None
    real_root = os.path.realpath(str(root))
    for d in dests:
        base = _rel(root, d, cwd)
        landed = []
        for m in members:
            rel = posixpath.join(base, m)
            landed.append(rel)
            real = os.path.realpath(os.path.join(real_root, rel))          # through symlinks already in the repo
            if real.startswith(real_root + "/"):
                landed.append(os.path.relpath(real, real_root))
        hit = _incoming_problem(root, landed)
        if hit:
            return f"the archive would write '{hit}', which is human-owned or protected"
    return None


GIT_VALUE_OPTS = {   # options whose value is the next word (0005 review round 1: a value isn't a ref)
    "merge": {"-m", "-F", "-s", "-X", "--strategy", "--strategy-option", "--into-name", "--file", "--message",
              "--cleanup"},
    "rebase": {"-s", "-X", "--strategy", "--strategy-option", "-x", "--exec", "-C", "--onto"},
    "cherry-pick": {"-m", "--mainline", "-X", "--strategy", "--strategy-option"},
}


def _git_operands(sub, rest):
    """(operands, {option: value}) of a git subcommand, skipping option values."""
    ops, vals, i, takes = [], {}, 0, GIT_VALUE_OPTS.get(sub, set())
    while i < len(rest):
        a = rest[i]
        if a in takes and i + 1 < len(rest):
            vals[a] = rest[i + 1]
            i += 2
            continue
        if a.startswith("--") and "=" in a:
            vals[a.split("=", 1)[0]] = a.split("=", 1)[1]
        elif not a.startswith("-"):
            ops.append(a)
        i += 1
    return ops, vals


def _git_paths(root, *args):
    """Paths a git command lists with -z, or None if it fails."""
    out = git(root, *args)
    return None if out is None else [p for p in out.split("\0") if p]


def _incoming_git(sub, rest, root, on_main):
    """Why a stash pop/apply, merge, rebase, cherry-pick or pull is refused (G-FILE-06): it would bring in
    human-owned config or a protected path from somewhere a human didn't merge. The main branch (and origin/<main>)
    is trusted; intent folders (approval commits) always pass. Every operand is inspected. None if fine."""
    main = config(root)["main_branch"]
    trusted = {main, f"origin/{main}", f"refs/heads/{main}", f"refs/remotes/origin/{main}"}
    if any(a in ("--abort", "--continue", "--skip", "--quit") for a in rest):
        return None
    ops, vals = _git_operands(sub, rest)
    if sub == "pull":
        if on_main and ops in ([], ["origin"], ["origin", main]):   # a pull of main itself
            return None
        return "`git pull` brings in changes that can't be inspected before they land"
    if sub == "stash" and ops[:1] in (["pop"], ["apply"], ["branch"]):
        ref = (ops[2] if ops[0] == "branch" else ops[1]) if len(ops) > (2 if ops[0] == "branch" else 1) else "stash@{0}"
        paths = _git_paths(root, "stash", "show", "-z", "--name-only", "--include-untracked", ref)
        if paths is None:
            paths = _git_paths(root, "stash", "show", "-z", "--name-only", ref)
        if paths is None:
            return f"`git stash {ops[0]} {ref}` can't be inspected"
        hit = _incoming_problem(root, paths)
        return f"`git stash {ops[0]}` would write '{hit}', which is human-owned or protected" if hit else None
    if sub in ("merge", "rebase"):
        refs = ops + ([vals["--onto"]] if "--onto" in vals else [])
        if not refs:
            if git(root, "rev-parse", "-q", "--verify", "@{u}") is None:
                return None                              # no upstream: git refuses on its own
            refs = ["@{u}"]
        for n, ref in enumerate(refs):
            if ref in trusted:
                continue
            paths = _git_paths(root, "diff", "-z", "--name-only", f"HEAD...{ref}")
            if paths is not None and sub == "rebase" and n == 1:   # `rebase <upstream> <branch>` checks out <branch>
                more = _git_paths(root, "diff", "-z", "--name-only", "HEAD", ref)
                paths = None if more is None else paths + more
            if paths is None:
                return f"`git {sub} {ref}` can't be inspected (unknown ref: fetch it first)"
            hit = _incoming_problem(root, paths)
            if hit:
                return f"`git {sub} {ref}` would bring in '{hit}', which is human-owned or protected"
        return None
    if sub == "cherry-pick":
        mainline = vals.get("-m") or vals.get("--mainline") or "1"
        if any(".." in o or o.startswith("^") for o in ops):
            listed = git(root, "rev-list", *ops)
            commits = listed.split() if listed else None
        else:
            commits = [git(root, "rev-parse", "-q", "--verify", f"{o}^{{commit}}") for o in ops]
            commits = None if None in commits else commits
        if commits is None:
            return "`git cherry-pick` can't be inspected (unknown commit: fetch it first)"
        for c in commits:
            parents = (git(root, "rev-list", "--parents", "-n", "1", c) or "").split()[1:]
            if parents:
                base = f"{c}^{mainline}" if len(parents) > 1 else f"{c}^"
                paths = _git_paths(root, "diff", "-z", "--name-only", base, c)
            else:
                paths = _git_paths(root, "show", "-z", "--name-only", "--format=", c)
            if paths is None:
                return f"`git cherry-pick {c[:10]}` can't be inspected"
            hit = _incoming_problem(root, paths)
            if hit:
                return f"`git cherry-pick {c[:10]}` would bring in '{hit}', which is human-owned or protected"
    return None


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


def _writable_path_dirs():
    out = []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d and os.path.isabs(d) and os.access(d, os.W_OK):
            out.append(os.path.realpath(d))
    return out


def _toolchain_path(p, root):
    """Shell startup files, git's global config, installed plugins (defaults/toolchain-paths), ~/bin and every
    user-writable PATH directory: an agent's write there runs inside the human's next approval. The target is
    resolved (symlinks, `..`) and also probed as a directory (`cp x ~/.local/bin/`, `cp x ~/.config/fish`)."""
    real = os.path.realpath(str(p))
    probes = [real, real + "/x"]                           # a directory target, existing or not, counts as inside
    homebin = os.path.realpath(str(Path.home() / "bin"))
    dirs = _writable_path_dirs() + [homebin]
    return any(glob_hit(q, globs(root, "toolchain-paths")) or any(q == d or q.startswith(d + "/") for d in dirs)
               for q in probes)


WHOLE_TREE_RE = re.compile(r"^(\.|\./|:/.*|:\(.*|.*[*?\[].*)$")


def _rewrites_tree_from_rev(sub, rest):
    """`git checkout <rev> -- .` / `git restore -s <rev> ':/'`: older versions of everything, protected files included."""
    if sub == "restore":
        rev = any(a in ("-s", "--source") or a.startswith("--source=") or (a.startswith("-s") and len(a) > 2)
                  for a in rest)
    elif sub == "checkout" and "--" in rest:
        rev = any(not a.startswith("-") for a in rest[:rest.index("--")])
    elif sub == "checkout":                                  # `git checkout HEAD~1 .`: a rev, then paths
        operands = [a for a in rest if not a.startswith("-")]
        return len(operands) >= 2 and any(WHOLE_TREE_RE.match(p) for p in operands[1:])
    else:
        return False
    paths = rest[rest.index("--") + 1:] if "--" in rest else [a for a in rest if not a.startswith("-")]
    return rev and any(WHOLE_TREE_RE.match(p) for p in paths)


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


DELETERS = {"rm", "rmdir", "unlink", "shred"}
FIND_FILTERS = {"-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex", "-type",
                "-newer", "-mtime", "-mmin", "-size", "-empty", "-user", "-group", "-perm"}


def delete_targets(words):
    """The paths a simple command deletes or moves away: rm/rmdir/unlink/shred operands, mv sources, find -delete
    roots. Options end at `--`."""
    if not words:
        return []
    name, args = Path(words[0]).name, words[1:]
    ops, after = [], False
    for a in args:
        if after or not a.startswith("-") or a == "-":
            ops.append(a)
        elif a == "--":
            after = True
    if name in DELETERS:
        return ops
    if name == "mv":
        return ops if _target_directory(args) else ops[:-1]
    if name == "rsync" and any(a.startswith("--delete") for a in args):
        return ops[-1:]                                  # the destination loses what the source lacks
    if name == "find" and _find_deletes(args) and not _find_name_filters(args):   # unfiltered: the whole tree
        return _find_roots(args)
    return []


FIND_DELETING = {"rm", "rmdir", "unlink", "shred", "mv", "truncate"}


def _find_roots(args):
    return args[:next((i for i, a in enumerate(args) if a.startswith("-") or a in ("(", "!")), len(args))] or ["."]


def _find_deletes(args):
    """True if this find deletes: -delete, or -exec/-execdir/-ok running a deleting command."""
    return "-delete" in args or any(a in ("-exec", "-execdir", "-ok", "-okdir") and i + 1 < len(args)
                                    and Path(args[i + 1]).name in FIND_DELETING for i, a in enumerate(args))


def _find_name_filters(args):
    """[(test, pattern)] for -name/-iname/-path/-ipath/-wholename tests."""
    return [(a, args[i + 1]) for i, a in enumerate(args[:-1])
            if a in ("-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename")]


def _protected_files_under(root, rel):
    """Existing protected files (protected-paths globs) and git-tracked protected or secret files under rel."""
    from glob import glob as _glob
    prefix = "" if rel in ("", ".") else rel.rstrip("/") + "/"
    pglobs, sglobs = globs(root, "protected-paths"), globs(root, "secret-paths")
    found = set()
    for g, _ in pglobs:
        if g.startswith(prefix) or not prefix:
            for f in _glob(str(Path(root) / g), recursive=True):
                found.add(Path(f).relative_to(root).as_posix())
    for f in filter(None, (git(root, "ls-files", "-z", "--", rel or ".") or "").split("\0")):
        if glob_hit(f, pglobs) or (not _secret_template(f) and glob_hit(f, sglobs)):
            found.add(f)
    return sorted(found)


def _find_hits_protected(args, cwd, root):
    """A filtered find that deletes: the first protected file under its roots that a name/path test would reach."""
    if not _find_deletes(args):
        return None
    tests = _find_name_filters(args)
    for r in _find_roots(args):
        rel = _rel(root, r, cwd)
        if rel is None:
            continue
        for f in _protected_files_under(root, rel):
            for t, pat in tests:
                ci = t.startswith("-i")
                subject = f.rsplit("/", 1)[-1] if t in ("-name", "-iname") else f"./{f}"
                if _fnmatch(subject, pat, ci) or (t not in ("-name", "-iname") and _fnmatch(f, pat, ci)):
                    return f
    return None


def _contains_protected(root, target, cwd):
    """Why deleting the directory `target` is refused (G-FILE-05), else None: it is the repo, a directory above it or
    above home, or a directory with a protected-paths glob or a git-tracked protected or secret file under it.
    Untracked trees (node_modules, build output) are never walked; `rm link` (no trailing slash) is fine."""
    raw = Path(os.path.expanduser(str(target)))
    raw = raw if raw.is_absolute() else Path(cwd) / raw
    if not str(target).endswith("/") and raw.is_symlink():
        return None                                      # `rm link` removes the link, not what it points to
    p = Path(os.path.realpath(str(raw)))
    real_root = Path(os.path.realpath(str(root)))
    if p == real_root or p in real_root.parents:
        return f"'{target}' is the repository itself or a directory above it"
    home = Path(os.path.realpath(str(Path.home())))
    if p == home or p in home.parents:               # ~/.ssh, the global git config, the installed plugin
        return f"'{target}' is your home directory or a directory above it"
    try:
        rel = p.relative_to(real_root).as_posix()
    except ValueError:
        return None
    if not p.is_dir():
        return None
    prefix = rel.rstrip("/") + "/"
    pglobs, sglobs = globs(root, "protected-paths"), globs(root, "secret-paths")
    hit = next((g for g, _ in pglobs if g.startswith(prefix)), None)
    if hit:
        return f"'{rel}' contains a protected path ({hit})"
    tracked = (git(root, "ls-files", "-z", "--", rel) or "").split("\0")
    for f in filter(None, tracked):
        if glob_hit(f, pglobs):
            return f"'{rel}' contains the protected file '{f}'"
        if not _secret_template(f) and glob_hit(f, sglobs):
            return f"'{rel}' contains the tracked secret '{f}'"
    return None


def _check_command(cmd, cwd, root, locked, reason, st, on_main, depth, gates=True):
    """The first block for cmd, else None. gates=False (a repo without .aiops/) runs only the safety checks: writes
    into the installed plugin, writes outside the repo to secrets or the approval toolchain, `git config --global`
    of signing keys, and nesting."""
    assigned = {}
    dirstack, links = [], {}
    for words, redirs in segments(tokenize(PWD_RE.sub(lambda _m: shlex.quote(str(cwd)), cmd))):
        config_env = any(GIT_CONFIG_ENV_RE.match(w) for w in words)
        words, redirs = ([VAR_RE.sub(lambda m: assigned.get(m[1] or m[2], m[0]), w) for w in ws]
                         for ws in (words, redirs))
        bare = [w for w in (words[1:] if words[:1] and words[0] in DECLARERS else words) if not w.startswith("-")]
        if bare and not redirs and all(ASSIGN_RE.match(w) for w in bare):   # `d=.aiops; rm -rf $d`
            assigned.update(w.split("=", 1) for w in bare)
            continue
        words = _strip_prefix(words)
        if words and words[0] in ("cd", "pushd"):
            dest = next((a for a in words[1:] if not a.startswith("-")), "~")
            if words[0] == "pushd":
                dirstack.append(cwd)
            cwd = Path(dest).expanduser() if Path(dest).expanduser().is_absolute() else cwd / dest
            continue
        if words and words[0] == "popd":
            cwd = dirstack.pop() if dirstack else cwd
            continue
        if words and Path(words[0]).name == "ln" and any(re.match(r"^-[a-zA-Z]*s", a) or a == "--symbolic"
                                                          for a in words[1:]):
            lops = [a for a in words[1:] if not a.startswith("-")]
            if lops:                                     # a link made here: a later delete through it hits its target
                name = lops[-1] if len(lops) > 1 else Path(lops[0]).name
                links[os.path.normpath(str(cwd / name))] = os.path.normpath(str(cwd / lops[0]))
        inner = _nested_command(words)
        if inner is not None:
            if depth >= 3:
                return _block("G-BASH-01", "nested shells are too deep to inspect.", "run the command directly.")
            msg = _check_command(inner, cwd, root, locked, reason, st, on_main, depth + 1, gates)
            if msg:
                return msg
            continue
        if gates and words and Path(words[0]).name == "find":
            hit = _find_hits_protected(words[1:], cwd, root)
            if hit:
                return _block("G-FILE-05", f"`{' '.join(words)[:80]}` would delete the protected file '{hit}'.",
                              "narrow the find so it skips protected paths; a human removes protected files.")
        if gates:
            for t in (e for t in delete_targets(words) for e in _expand(t, cwd)):
                key = os.path.normpath(str(t if Path(t).is_absolute() else cwd / t))
                if t.endswith("/") and key in links:     # `ln -s .github q && rm -rf q/`
                    t = links[key] + "/"
                rel = _rel(root, t, cwd)
                if rel is not None and (_aiops_protected(rel) or rel == ".git" or rel.startswith(".git/")):
                    continue             # the .aiops / .git rules below name it more precisely
                hit = _contains_protected(root, t, cwd)
                if hit:
                    return _block("G-FILE-05", f"`{' '.join(words)[:80]}` deletes or moves {hit}.",
                                  "name the paths you mean, outside .aiops/, .git/ and protected paths; a human "
                                  "removes protected files.")
        targets = [e for t in redirs + write_targets(words, cwd) for e in _expand(t, cwd)]
        if gates and words and Path(words[0]).name == "find" and _find_hits_aiops(words[1:], cwd, root):
            return _block("G-ART-04", "this `find` would delete or rewrite part of the .aiops tree.",
                          "narrow it (e.g. `-not -path './.aiops/*'`), or ask the human to remove artifacts.")
        if words:
            targets += _extract_dirs(Path(words[0]).name, words[1:])
        for t in targets:
            if t.startswith("/dev/"):
                continue
            if _in_plugin(t, cwd, root):
                return _block("G-TOOL-02", f"`{' '.join(words)[:80]}` writes into the installed plugin ({t}).",
                              "the plugin's code is what the human runs to approve; change it through its own repo.")
            rel = _rel(root, t, cwd)
            if not gates and rel is not None:   # an uninitialized repo: no gates, but the safety checks still apply
                p = Path(t).expanduser()
                p = p if p.is_absolute() else Path(cwd) / p
                if glob_hit(str(p), globs(root, "secret-paths")) and not _secret_template(p.name):
                    return _block("G-SEC-01", f"'{p}' is secret material; shell writes count too.",
                                  "ask the human to change credentials themselves.")
                if _toolchain_path(p, root) or _holds_toolchain(p):
                    return _block("G-TOOL-04", f"'{p}' is part of what runs when the human approves (PATH, shell "
                                  "startup, git config, installed plugins).", "ask the human to change it themselves.")
                continue
            if rel is not None and (rel == ".git" or rel.startswith(".git/")):
                return _block("G-TOOL-03", f"shell writes to '{rel}' (git config, hooks) can hijack signing.",
                              "use git commands; ask the human for config or hook changes.")
            if rel is None:   # outside the repo: never secret material, nor what runs inside the human's approval
                p = Path(t).expanduser()
                p = p if p.is_absolute() else Path(cwd) / p
                if glob_hit(str(p), globs(root, "secret-paths")) and not _secret_template(p.name):
                    return _block("G-SEC-01", f"'{p}' is secret material; shell writes count too.",
                                  "ask the human to change credentials themselves.")
                if _toolchain_path(p, root) or _holds_toolchain(p):
                    return _block("G-TOOL-04", f"'{p}' is part of what runs when the human approves (PATH, shell "
                                  "startup, git config, installed plugins).", "ask the human to change it themselves.")
                continue
            if _aiops_protected(rel):
                return _block("G-ART-05", f"shell writes to '{rel}' bypass the gate guard.",
                              "edit artifacts with the Edit/Write tools; engine state changes go through `sdlc`.")
            prot_hit = glob_hit(rel, globs(root, "protected-paths"))
            hit = prot_hit or (not _secret_template(rel) and glob_hit(rel, globs(root, "secret-paths")))
            if prot_hit:
                return _block("G-FILE-01", f"'{rel}' is protected ({hit[1] or hit[0]}); shell writes count too.",
                              "propose the change in chat; a human edits protected files.")
            if hit:
                return _block("G-SEC-02", f"'{rel}' is secret material ({hit[1] or hit[0]}); shell writes count too.",
                              "use .env.example for names; ask the human to change real secrets.")
            if locked and _code_paths(root, [rel]):
                return _block("G-LOCK-02", f"`{' '.join(words)[:80]}` writes '{rel}': {reason}.",
                              lock_procedure(st))
        if not words:
            continue
        name, args = Path(words[0]).name, words[1:]
        if gates and name in ("tar", "unzip"):
            why = _incoming_archive(name, args, cwd, root)
            if why:
                return _block("G-FILE-06", f"{why}.", "extract outside the repo and copy what you need, or ask the "
                              "human to change human-owned config.")
        if not gates:
            if name == "git":
                sub, rest, gcwd = _git_sub(args, cwd)
                if sub == "config" and _git_config_outside(rest, gcwd, root, config_env) \
                        and _git_config_writes_signing(rest, gcwd, root):
                    return _block("G-TOOL-05", "git signing, hook, monitor, filter and include settings are "
                                  "human-owned (they decide who signs approvals, and what runs inside an approval).",
                                  "ask the human to change git config themselves (globally).")
            continue
        why = _patch_check(args, cwd, root) if name == "patch" else None
        if why:
            return _block("G-ART-06", "this `patch` touches .aiops/, which bypasses the gate guard." if why == "aiops"
                          else "`patch` from a pipe can't be inspected for .aiops/ changes.",
                          "edit artifacts with the Edit/Write tools, or pass the patch file by name (`-i` or `<`).")
        if name == "gh" and args[:1] == ["api"] and any(re.search(r"/pulls/\d+/merge\b|/merges\b", a) for a in args):
            return _block("G-MERGE-01", "merging through the GitHub API is the human's decision.",
                          "leave the PR for a CODEOWNER to review and merge.")
        if name == "git":
            sub, rest, gcwd = _git_sub(args, cwd)
            why = _incoming_git(sub, rest, root, on_main)
            if why:
                return _block("G-FILE-06", f"{why}.", "`git fetch`, then `git merge <ref>` (inspected) for code; a "
                              "human brings in changes to human-owned config.")
            if sub == "config" and _git_config_writes_signing(rest, gcwd, root):
                return _block("G-TOOL-05", "git signing, hook, monitor, filter and include settings are human-owned "
                              "(they decide who signs approvals, and what runs inside an approval).",
                              "ask the human to change git config themselves (globally).")
            why = _patch_check(rest, gcwd, root, git_am=sub == "am") if sub in ("apply", "am") else None
            if why:
                return _block("G-ART-07", f"`git {sub}` with a patch touching .aiops/ bypasses the gate guard."
                              if why == "aiops" else f"`git {sub}` from stdin can't be inspected for .aiops/ changes.",
                              "edit artifacts with the Edit/Write tools, or apply a patch file by name.")
            if sub in GIT_TREE_WRITERS:
                if _rewrites_tree_from_rev(sub, rest):
                    return _block("G-FILE-02", f"`git {sub}` from another revision with a whole-tree pathspec would "
                                  "rewrite protected files and artifacts.",
                                  "name the paths you need (outside protected paths and .aiops/).")
                rels = [r for r in (_rel(root, a, gcwd) for a in rest if not a.startswith("-")) if r]
                hit = next((r for r in rels if _aiops_protected(r)), None)
                if hit:
                    return _block("G-ART-08", f"`git {sub}` on '{hit}' would delete or rewrite an artifact outside the "
                                  "gate guard.", "edit artifacts with the Edit/Write tools; ask the human to remove one.")
                pglobs = globs(root, "protected-paths")
                prot = next((r for r in rels if glob_hit(r, pglobs)
                             or any(g.startswith(r.rstrip("/") + "/") for g, _ in pglobs)), None)   # a directory
                if prot:
                    return _block("G-FILE-03", f"`git {sub}` would rewrite '{prot}', a protected path.",
                                  "propose the change in chat; a human edits protected files.")
            if on_main and sub in GIT_MAIN_FORBIDDEN:
                return _block("G-MERGE-02", f"`git {sub}` on {config(root)['main_branch']}: merging is the human's decision.",
                              "leave the branch for the human to review and merge (/zouj-ai-sdlc:pr).")
            if sub == "commit":
                for i, a in enumerate(rest):
                    f = rest[i + 1] if a in ("-F", "--file") and i + 1 < len(rest) else \
                        a.split("=", 1)[1] if a.startswith("--file=") else None
                    path = (gcwd / f) if f and f != "-" else None
                    if path and path.is_file() and "AIOps-Approval" in path.read_text(errors="replace"):
                        return _block("G-GATE-06", "approval commits are created only by a human approval.",
                                      "ask the human to type the approval phrase (e.g. `Plan Approved 0001`).")
            if not locked:
                continue
            checkout_paths = sub == "checkout" and _code_paths(root, [
                r for r in (_rel(root, a, gcwd) for a in rest if not a.startswith("-") and (gcwd / a).is_file()) if r])
            if sub in GIT_LOCKED or (sub == "checkout" and "--" in rest) or checkout_paths:
                return _block("G-LOCK-03", f"`git {sub}` changes the working tree: {reason}.", lock_procedure(st))
            if sub == "add":
                paths = [a for a in rest if not a.startswith("-")]
                if not paths or any(a in ("-A", "--all", "-u", "--update") for a in rest) or "." in paths:
                    rels = _git_changed(root, staged_only=False)
                else:
                    rels = [_rel(root, p, gcwd) for p in paths]
                if bad := _code_paths(root, rels):
                    return _block("G-LOCK-04", f"`git add` would stage code ({', '.join(bad[:3])}): {reason}.",
                                  lock_procedure(st))
            if sub == "commit":
                all_flag = any(re.match(r"^-[a-zA-Z]*a", a) or a == "--all" for a in rest)
                rels = _git_changed(root, staged_only=not all_flag) + \
                    [_rel(root, p, gcwd) for p in _git_commit_pathspecs(rest)]
                if bad := _code_paths(root, rels):
                    return _block("G-LOCK-05", f"`git commit` would commit code ({', '.join(bad[:3])}): {reason}.",
                                  lock_procedure(st))
            continue
        if not locked:
            continue
        sub = next((a for a in args if not a.startswith("-")), "")
        if name.startswith("python") and args[:2] == ["-m", "pip"]:
            name, sub = "pip", (args[2] if len(args) > 2 else "")
        if name in PKG and sub in PKG[name]:
            return _block("G-LOCK-06", f"`{name} {sub}` changes dependencies: {reason}.", lock_procedure(st))
        if name == "make" and any(a in MAKE_WRITERS for a in args):
            return _block("G-LOCK-07", f"`make {' '.join(args)}` rewrites code: {reason}.", lock_procedure(st))
        if name in ("patch", "unzip") or (name == "tar" and _extract_dirs(name, args)):
            return _block("G-LOCK-08", f"`{name}` writes files: {reason}.", lock_procedure(st))
    return None


__all__ = ["check_edit", "check_bash", "check_artifact", "lock_procedure", "active_dir", "evaluate"]
