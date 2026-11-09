"""Static shell parsing shared by the gate guard (guards.py) and the always-on secret scan (secret_scan.py).
Stdlib only and free of engine state, so a hook can import it without loading the engine."""
import re
import shlex

# the delimiter is a bash word: any run of non-metacharacters, quotes and escapes included (0005 review round 6)
HEREDOC_MARK_RE = re.compile(r"""(?<!<)<<(-?)(?!<)[ \t]*((?:[^\s;&|()<>'"\\]|\\.|'[^']*'|"(?:[^"\\]|\\.)*")+)""")
RESET = "\x00reset"   # tokenize(): a second reading of the command starts here, from the session's cwd
SEPARATORS = {";", "&&", "||", "|", "&", "|&", "(", ")", ";;", "{", "}", "!", "\n"}
RESERVED = {"if", "then", "else", "elif", "do", "while", "until", "time", "!", "{"}   # what `!`/`{` may follow


def _delimiter(raw):
    """(delimiter, quoted) of a heredoc word: quote removal as bash does it; any quoting makes the body literal."""
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if c == "\\" and i + 1 < len(raw):
            out.append(raw[i + 1])
            i += 2
        elif c in "'\"":
            j = raw.index(c, i + 1)
            out.append(raw[i + 1:j])
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out), any(q in raw for q in "'\"\\")


def _command_position(words):
    """True when the next word starts a command: only reserved words so far (and `time`'s own options), or right
    after `name()` / `coproc NAME` / `function f`."""
    k = 0
    while k < len(words):
        if words[k] in RESERVED or (words[k] in ("-p", "--") and k and words[k - 1] in ("time", "-p")):
            k += 1
        else:
            break
    return k == len(words) or words[-1].endswith("()") or (len(words) <= 2 and words[0] in ("coproc", "function"))
ESCAPED = {"\x01": r"\(", "\x02": r"\)", "\x03": r"\;"}   # `find \( … \) -exec … \;`: literal words


def _arith_end(line, i, pair="()"):
    """Index just past the `))` (or `]`) closing an arithmetic expression whose `((` (or `[`) starts at i."""
    depth = 0
    for j in range(i, len(line)):
        depth += {pair[0]: 1, pair[1]: -1}.get(line[j], 0)
        if depth == 0:
            return j + 1
    return len(line)


def _heredoc_marks(line, comments=True):
    """[(start, end, delimiter, quoted)] of `<<WORD` markers that are real: outside quotes ('…', "…", $'…'), comments and
    arithmetic ($((…)), ((…)), $[…], where `<<` is a shift). Substitutions nested in "…" ("$(…)", "${…}", "`…`")
    are followed, so a quote inside them doesn't end the outer one (0005 review round 6)."""
    marks, i, stack = [], 0, []          # stack: the open contexts, innermost last: ' " $' $( ${ ` (
    while i < len(line):
        c, top = line[i], (stack[-1] if stack else None)
        if top in ("'", "$'"):
            if c == "\\" and top == "$'":
                i += 2
                continue
            if c == "'":
                stack.pop()
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if top == '"' and c == '"':
            stack.pop()
            i += 1
            continue
        if line.startswith("$((", i) or line.startswith("$[", i) or (
                top != '"' and line.startswith("((", i) and (i == 0 or line[i - 1] in " \t;&|(")):
            i = _arith_end(line, i + 1 if c == "$" else i, "[]" if line.startswith("$[", i) else "()")
            continue
        if line.startswith("$(", i) or line.startswith("${", i):
            stack.append(line[i:i + 2])
            i += 2
            continue
        if c == "`":
            if top == "`":
                stack.pop()
            else:
                stack.append("`")
            i += 1
            continue
        if top == '"':
            i += 1
            continue
        if top == "${" and c == "}" or top in ("$(", "(") and c == ")":
            stack.pop()
        elif c == "(" and top in ("$(", "("):
            stack.append("(")
        elif line.startswith("$'", i):
            stack.append("$'")
            i += 2
            continue
        elif c in "'\"":
            stack.append(c)
        elif comments and c == "#" and (i == 0 or line[i - 1] in " \t;&|(") and top in (None, "$(", "(", "`"):
            break                                   # the rest of the line is a comment
        elif top in (None, "$(", "(", "`") and (m := HEREDOC_MARK_RE.match(line, i)):
            delim, quoted = _delimiter(m.group(2))
            marks.append((m.start(), m.end(), delim, quoted))
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
            j = i
            while j < len(lines) and lines[j].strip() != delim:
                j += 1
            i = j + 1 if j < len(lines) else i   # no delimiter line: read the rest as commands (fail closed)
    return "\n".join(out)


ESCAPE_MARK = {"(": "\x01", ")": "\x02", ";": "\x03"}
# the `case` keywords as bash sees them: unquoted, unescaped, whole words. shlex removes quotes, so `\case` or
# `"case"` (an ordinary command in bash) must not start a case (0005 review round 7)
KEYWORD_MARK = {"case": "\x04", "esac": "\x05", "in": "\x06"}
KEYWORD = {v: k for k, v in KEYWORD_MARK.items()}
KEYWORD_RE = re.compile(r"(case|esac|in)(?=[\s;&|()]|$)")


def _prescan(cmd, comments=True):
    r"""cmd as bash reads it, in one left-to-right pass: comments dropped (an unquoted `#` at the start of a word),
    unquoted backslash-newline continuations joined, and heredoc bodies removed up to their delimiter line (in an
    unquoted heredoc body a continuation is joined before the delimiter is compared; a quoted one is never joined).
    Quotes ('…', "…", $'…') are tracked across lines, so an apostrophe in a comment or a heredoc body changes
    nothing (0005 review: R1, R2 and the comment-quote residual). `#` right after `)` is no comment: in `$(…)#`,
    `$((…))#`, `<(…)#` and `a=(…)#` it continues the word (review round 6). comments=False keeps every `#` as an
    ordinary word character, as main read it: the second reading tokenize() judges whenever this one dropped a
    comment, so a real separator that a misread comment hid still splits (review round 7)."""
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
            if comments and c == "#" and prev in ("", " ", "\t", ";", "&", "|", "("):
                if comments:
                    break                                  # a comment, to the end of the line
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
        marks = _heredoc_marks(logical, comments)
        for start, end, _delim, _quoted in reversed(marks):
            logical = logical[:start] + " " + logical[end:]
        out.append(logical)
        logical = ""
        for _start, _end, delim, quoted in marks:          # skip each body, through its delimiter line
            j, found = i, False
            while j < len(lines):
                body = lines[j]
                j += 1
                while not quoted and body.endswith("\\") and not body.endswith("\\\\") and j < len(lines):
                    body = body[:-1] + lines[j]
                    j += 1
                if body.strip() == delim:
                    found = True
                    break
            i = j if found else i                          # no delimiter line: read the rest (fail closed)
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
        if quote is None and (i == 0 or cmd[i - 1] in " \t\n;&|()") and (m := KEYWORD_RE.match(cmd, i)):
            out.append(KEYWORD_MARK[m.group(1)])
            i = m.end()
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
    """The tokens of cmd as bash reads it. When a comment was dropped, the tokens of a second reading that keeps
    every `#` as a word follow a RESET token, so a separator a misjudged comment hid still splits (0005 review
    rounds 6-7). Quotes nested in "$(…)" aren't followed by the pre-pass: see docs/architecture.md residuals."""
    first, second = _prescan(cmd), _prescan(cmd, comments=False)
    return _tokens(first) + ([RESET] + _tokens(second) if second != first else [])


def _tokens(cmd):
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


def scoped_segments(tokens, cases=True):
    """segments() plus scope events: ("(", None) where a subshell, group or substitution opens, (")", None) where the
    matching `)` closes it, and (RESET, None) where tokenize()'s second reading starts. A `)` that ends a `case`
    pattern, or that pairs with no reported `(`, is no scope event (0005 review round 6). Only the real keywords
    (KEYWORD_MARK) drive the case state, and a `$(…)` in a pattern is segmented like any other (round 7).

    Invariant (rounds 8-9): every refinement over main's reading (case tracking, subshell scopes) is an extra
    reading after a RESET, never a replacement. Callers judge every reading and block if any blocks, so the union
    is at least as strict as main's flat, cwd-persisting reading by construction."""
    out, words, redirs, i, opened = [], [], [], 0, []   # opened: "(", "case-word", "pat" (in a pattern) or "case"
    saw_case = False

    redirected = False                                 # any redirection in this command, fd duplications included

    def flush():
        nonlocal words, redirs, redirected
        if words or redirs:
            out.append((words, redirs))
        words, redirs, redirected = [], [], False

    def word(t):
        return KEYWORD.get(t, t)

    while i < len(tokens):
        t = tokens[i]
        command_position = _command_position(words)
        top = opened[-1] if opened else None
        if t == RESET:
            flush()
            out.append((RESET, None))
            opened = []
        elif not cases and t in KEYWORD:
            words.append(word(t))
        elif top == "pat" and t == ")":                  # the end of a case pattern list: its words are judged
            opened[-1] = "case"                          # anyway, so a misread case hides nothing (round 8)
            flush()
        elif top == "pat" and t == "(" and not (i and tokens[i - 1].endswith(("$", "<", ">"))):
            pass                                         # the optional `(` before a pattern
        elif top == "pat" and t == "|":
            flush()                                      # between alternative patterns
        elif t == "\x04" and command_position and not redirected:   # `>&2 case` is a command (round 8)
            saw_case = True
            words.append("case")
            opened.append("case-word")
        elif t == "\x06" and top == "case-word":       # the case word may span lines and substitutions
            words, redirs = [], []
            opened[-1] = "pat"
        elif t == "\x05" and command_position and not redirected and top in ("case", "pat"):
            flush()
            opened.pop()
        elif t in (";;", ";&", ";;&") and top == "case":
            flush()
            opened[-1] = "pat"
        elif t in SEPARATORS and (t not in ("!", "{", "}") or command_position):   # `!`/`{`/`}` only in command
            flush()                                                                  # position: `find . ! -name x`
            if t == "(":
                opened.append("(")
                out.append(("(", None))
            elif t == ")" and opened and opened[-1] == "(":
                opened.pop()
                out.append((")", None))
        elif set(t) <= set("<>&|") and ">" in t:
            redirected = True
            if words and words[-1].isdigit():
                words.pop()            # the "2" in 2>file
            target = word(tokens[i + 1]) if i + 1 < len(tokens) else ""
            i += 1
            if not (t.endswith("&") and target.lstrip("-").isdigit()) and target not in SEPARATORS:
                redirs.append(target)
        elif not (set(t) <= set("<")):
            words.append(word(t))
        i += 1
    flush()
    if not cases:
        return out
    if saw_case:                        # case tracking reads dequoted words (`'a()' case`), so a line with a case is
        out = out + [(RESET, None)] + scoped_segments(tokens, cases=False)  # also judged with every `)` a scope end
    if any(r is None and w in ("(", ")") for w, r in out):   # scope tracking can't see a `)` bash reads inside a word
        out = out + [(RESET, None)] + [(w, r) for w, r in out if r is not None or w == RESET]   # (`)`, ${x/)/}):
    return out                          # also judged as main read it, every cd persisting (review round 9)


def segments(tokens):
    """Split tokens into simple commands; return [(words, redirect_targets)]."""
    return [(w, r) for w, r in scoped_segments(tokens) if r is not None]
