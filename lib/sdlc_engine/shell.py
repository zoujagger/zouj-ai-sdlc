"""Static shell parsing shared by the gate guard (guards.py) and the always-on secret scan (secret_scan.py).
Stdlib only and free of engine state, so a hook can import it without loading the engine."""
import re
import shlex

HEREDOC_MARK_RE = re.compile(r"(?<!<)<<(-?)(?!<)\s*(['\"]?)(\w+)\2")
SEPARATORS = {";", "&&", "||", "|", "&", "|&", "(", ")", ";;", "{", "}", "!", "\n"}


def _arith_end(line, i):
    """Index just past the `))` closing an arithmetic expression whose `((` starts at i."""
    depth = 0
    for j in range(i, len(line)):
        depth += {"(": 1, ")": -1}.get(line[j], 0)
        if depth == 0:
            return j + 1
    return len(line)


def _heredoc_marks(line):
    """[(start, end, delimiter)] of `<<WORD` markers that are real: outside quotes ('…', "…", $'…'), comments and
    arithmetic ($((…)), ((…)), where `<<` is a shift)."""
    marks, i, quote = [], 0, None
    while i < len(line):
        c = line[i]
        if quote:
            if c == "\\" and quote in ('"', "$'"):
                i += 2
                continue
            if c == quote[-1]:
                quote = None
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if line.startswith("$'", i):
            quote = "$'"
            i += 2
            continue
        if line.startswith("$((", i) or (line.startswith("((", i) and (i == 0 or line[i - 1] in " \t;&|(")):
            i = _arith_end(line, i + 1 if c == "$" else i)
            continue
        if c in "'\"":
            quote = c
        elif c == "#" and (i == 0 or line[i - 1] in " \t;&|("):
            break                                   # the rest of the line is a comment
        elif m := HEREDOC_MARK_RE.match(line, i):
            marks.append((m.start(), m.end(), m.group(3)))
            i = m.end()
            continue
        i += 1
    return marks


def strip_heredocs(cmd):
    """Drop heredoc bodies but keep the rest of each marker line, so `cat <<EOF > file` still shows its redirect.
    Only markers outside quotes and comments count: `echo '<<EOF'` must not hide the lines after it."""
    lines, out, i = cmd.split("\n"), [], 0
    while i < len(lines):
        line, marks = lines[i], _heredoc_marks(lines[i])
        for start, end, _ in reversed(marks):
            line = line[:start] + " " + line[end:]
        out.append(line)
        i += 1
        for _start, _end, delim in marks:
            while i < len(lines) and lines[i].strip() != delim:
                i += 1
            i += 1   # the delimiter line itself
    return "\n".join(out)


def tokenize(cmd):
    cmd = strip_heredocs(cmd)
    lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:   # unbalanced quotes ($'…' confuses shlex): split crudely but keep command boundaries
        return re.findall(r"[;&|]+|[^\s;&|]+", cmd.replace("\n", " ; "))


def segments(tokens):
    """Split tokens into simple commands; return [(words, redirect_targets)]."""
    out, words, redirs, i = [], [], [], 0
    while i < len(tokens):
        t = tokens[i]
        if t in SEPARATORS and not (t in ("!", "{", "}") and words):   # `!`/`{`/`}` only in command position:
            out.append((words, redirs))                                   # `find . ! -name x` keeps its `!`
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
