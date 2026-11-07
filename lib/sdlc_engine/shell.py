"""Static shell parsing shared by the gate guard (guards.py) and the always-on secret scan (secret_scan.py).
Stdlib only and free of engine state, so a hook can import it without loading the engine."""
import re
import shlex

HEREDOC_MARK_RE = re.compile(r"(?<!<)<<(-?)(?!<)\s*(['\"]?)(\w+)\2")
SEPARATORS = {";", "&&", "||", "|", "&", "|&", "(", ")", ";;", "{", "}", "!", "\n"}
RESERVED = {"if", "then", "else", "elif", "do", "while", "until", "time", "!", "{"}   # what `!`/`{` may follow
ESCAPED = {"\x01": r"\(", "\x02": r"\)", "\x03": r"\;"}   # `find \( … \) -exec … \;`: literal words


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


ESCAPE_MARK = {"(": "\x01", ")": "\x02", ";": "\x03"}


def _join_continuations(cmd):
    r"""cmd without its unquoted backslash-newline pairs, as bash joins them before anything else (0005 review round 5:
    `rm -rf \<newline>.aiops` is one command). Single quotes keep theirs; an escaped backslash isn't a continuation."""
    out, i, quote = [], 0, None
    while i < len(cmd):
        c = cmd[i]
        if quote in ("'",):
            out.append(c)
            quote = None if c == "'" else quote
            i += 1
            continue
        if c == "\\" and i + 1 < len(cmd):
            if cmd[i + 1] == "\n" and quote != "$'":
                i += 2                                     # joined
                continue
            out.append(cmd[i:i + 2])
            i += 2
            continue
        if quote is None and cmd.startswith("$'", i):
            quote = "$'"
            out.append("$'")
            i += 2
            continue
        if quote == "$'" and c == "'":
            quote = None
        elif quote is None and c in "'\"":
            quote = c
        elif quote == '"' and c == '"':
            quote = None
        out.append(c)
        i += 1
    return "".join(out)


def _ansi_c(body):
    """The text of a $'…' body: the escapes bash decodes, the rest literal."""
    simple = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "v": "\v",
              "\\": "\\", "'": "'", '"': '"', "?": "?"}
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            n = body[i + 1]
            m = re.match(r"x([0-9a-fA-F]{1,2})|([0-7]{1,3})|u([0-9a-fA-F]{1,4})|U([0-9a-fA-F]{1,8})", body[i + 1:])
            if n in simple:
                out.append(simple[n])
                i += 2
                continue
            if m:
                out.append(chr(int(next(g for g in m.groups() if g), 8 if m.group(2) else 16)))
                i += 1 + m.end()
                continue
            out.append(n)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _mark_escapes(cmd):
    r"""cmd with each unquoted, unescaped `\(`, `\)` or `\;` replaced by its mark. A backslash escapes exactly one
    character, so `\\;` is a literal backslash and a real separator (0005 review round 4); quotes are honoured."""
    out, i, quote = [], 0, None
    while i < len(cmd):
        c = cmd[i]
        if quote == "'":
            out.append(c)
            quote = None if c == "'" else quote
            i += 1
            continue
        if quote is None and cmd.startswith("$'", i):   # $'…': backslash escapes inside; re-quote it plainly for shlex
            j, body = i + 2, []
            while j < len(cmd) and cmd[j] != "'":
                body.append(cmd[j:j + 2] if cmd[j] == "\\" else cmd[j])
                j += 2 if cmd[j] == "\\" else 1
            out.append(shlex.quote(_ansi_c("".join(body))))
            i = j + 1
            continue
        if c == "\\" and i + 1 < len(cmd):
            nxt = cmd[i + 1]
            out.append(ESCAPE_MARK[nxt] if quote is None and nxt in ESCAPE_MARK else c + nxt)
            i += 2
            continue
        if c == '"':
            quote = None if quote == '"' else ('"' if quote is None else quote)
        elif c == "'" and quote is None:
            quote = "'"
        out.append(c)
        i += 1
    return "".join(out)


OPERATORS = (";;", "&&", "||", "|&", ";", "&", "|", "(", ")")


def _split_punct(tok):
    """`);`, `)&&`, `)|`… (shlex merges adjacent punctuation) as their separate operators. Redirections, which
    segments() reads as one token, and `;;` stay whole."""
    if not tok or not set(tok) <= set("();&|<>") or tok in SEPARATORS or not set(tok) & set("();") or set(tok) & set("<>"):
        return [tok]
    out, i = [], 0
    while i < len(tok):
        op = next((o for o in OPERATORS if tok.startswith(o, i)), tok[i])
        out.append(op)
        i += len(op)
    return out


def tokenize(cmd):
    cmd = strip_heredocs(_join_continuations(cmd))
    cmd = _mark_escapes(cmd)                           # keep escaped ( ) ; as words, not separators
    lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        toks = list(lex)
    except ValueError:   # unbalanced quotes ($'…' confuses shlex): split crudely but keep command boundaries
        toks = re.findall(r"[;&|]+|[^\s;&|]+", cmd.replace("\n", " ; "))
    for mark, text in ESCAPED.items():
        toks = [t.replace(mark, text) for t in toks]
    return [p for t in toks for p in _split_punct(t)]


def segments(tokens):
    """Split tokens into simple commands; return [(words, redirect_targets)]."""
    out, words, redirs, i = [], [], [], 0
    while i < len(tokens):
        t = tokens[i]
        command_position = not words or all(w in RESERVED for w in words) or words[-1].endswith("()") \
            or (len(words) <= 2 and words[0] in ("coproc", "function"))
        if t in SEPARATORS and (t not in ("!", "{", "}") or command_position):   # `!`/`{`/`}` only in command
            out.append((words, redirs))                                           # position: `find . ! -name x`
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
