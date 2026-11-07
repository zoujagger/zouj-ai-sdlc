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
    """[(start, end, delimiter, quoted)] of `<<WORD` markers that are real: outside quotes ('…', "…", $'…'), comments and
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
            marks.append((m.start(), m.end(), m.group(3), bool(m.group(2))))
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
        for start, end, _d, _q in reversed(marks):
            line = line[:start] + " " + line[end:]
        out.append(line)
        i += 1
        for _start, _end, delim, _q in marks:
            while i < len(lines) and lines[i].strip() != delim:
                i += 1
            i += 1   # the delimiter line itself
    return "\n".join(out)


ESCAPE_MARK = {"(": "\x01", ")": "\x02", ";": "\x03"}


def _prescan(cmd):
    r"""cmd as bash reads it, in one left-to-right pass: comments dropped (an unquoted `#` at the start of a word),
    unquoted backslash-newline continuations joined, and heredoc bodies removed up to their delimiter line (in an
    unquoted heredoc body a continuation is joined before the delimiter is compared; a quoted one is never joined).
    Quotes ('…', "…", $'…') are tracked across lines, so an apostrophe in a comment or a heredoc body changes
    nothing (0005 review: R1, R2 and the comment-quote residual)."""
    lines, out, logical, quote, i = cmd.split("\n"), [], "", None, 0
    while i < len(lines):
        line, buf, j, cont = lines[i], [], 0, False
        i += 1
        while j < len(line):
            c = line[j]
            if quote == "'":
                buf.append(c)
                quote = None if c == "'" else quote
                j += 1
                continue
            if quote == "$'":
                if c == "\\" and j + 1 < len(line):
                    buf.append(line[j:j + 2])
                    j += 2
                    continue
                buf.append(c)
                quote = None if c == "'" else quote
                j += 1
                continue
            if c == "\\":
                if j + 1 < len(line):
                    buf.append(line[j:j + 2])
                    j += 2
                    continue
                cont = True                                # backslash-newline (unquoted or in "…"): join
                break
            if quote == '"':
                buf.append(c)
                quote = None if c == '"' else quote
                j += 1
                continue
            prev = (logical + "".join(buf))[-1:]
            if c == "#" and prev in ("", " ", "\t", ";", "&", "|", "(", ")"):
                break                                      # a comment, to the end of the line
            if line.startswith("$'", j):
                quote = "$'"
                buf.append("$'")
                j += 2
                continue
            if c in "'\"":
                quote = c
            buf.append(c)
            j += 1
        logical += "".join(buf)
        if cont:
            continue
        if quote is not None:                              # a quoted word spans the newline
            logical += "\n"
            continue
        marks = _heredoc_marks(logical)
        for start, end, _delim, _quoted in reversed(marks):
            logical = logical[:start] + " " + logical[end:]
        out.append(logical)
        logical = ""
        for _start, _end, delim, quoted in marks:          # skip each body, through its delimiter line
            while i < len(lines):
                body = lines[i]
                i += 1
                while not quoted and body.endswith("\\") and not body.endswith("\\\\") and i < len(lines):
                    body = body[:-1] + lines[i]
                    i += 1
                if body.strip() == delim:
                    break
    if logical:
        out.append(logical)
    return "\n".join(out)


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
    if tok and set(tok) <= set("();&|<>") and set(tok) & set("<>"):   # `)>file`: the `)` is an operator
        k = 0
        while k < len(tok) and tok[k] in "();|":
            k += 1
        return _split_punct(tok[:k]) + [tok[k:]] if 0 < k < len(tok) else [tok]
    if not tok or not set(tok) <= set("();&|<>") or tok in SEPARATORS or not set(tok) & set("();"):
        return [tok]
    out, i = [], 0
    while i < len(tok):
        op = next((o for o in OPERATORS if tok.startswith(o, i)), tok[i])
        out.append(op)
        i += len(op)
    return out


def tokenize(cmd):
    cmd = _prescan(cmd)
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


def scoped_segments(tokens):
    """segments() plus scope events: ("(", None) where a subshell or substitution opens, (")", None) where it closes,
    so a caller can keep a subshell's `cd` inside it."""
    out, words, redirs, i = [], [], [], 0
    while i < len(tokens):
        t = tokens[i]
        command_position = not words or all(w in RESERVED for w in words) or words[-1].endswith("()") \
            or (len(words) <= 2 and words[0] in ("coproc", "function"))
        if t in SEPARATORS and (t not in ("!", "{", "}") or command_position):
            if words or redirs:
                out.append((words, redirs))
            words, redirs = [], []
            if t in ("(", ")"):
                out.append((t, None))
        elif set(t) <= set("<>&|") and ">" in t:
            if words and words[-1].isdigit():
                words.pop()
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            i += 1
            if not (t.endswith("&") and target.lstrip("-").isdigit()) and target not in SEPARATORS:
                redirs.append(target)
        elif not (set(t) <= set("<")):
            words.append(t)
        i += 1
    if words or redirs:
        out.append((words, redirs))
    return out


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
