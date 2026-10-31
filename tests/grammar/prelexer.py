#!/usr/bin/env python3
"""Pre-lexer for lmcode bodies, mirroring the parts of dsl.ts's tokenizer that are not
regular: heredocs (<<TAG / <<~TAG) and, for lmscript-wrapped sources, ${} splices.

Heredocs are the one lmcode lexical form a regular expression cannot honestly tokenize
(the closing line must equal the tag), so -- exactly like dsl.ts itself, which also handles
them procedurally -- they are replaced here by sentinel tokens \x00HD<n>\x00 before the
Lark lexer runs. An unterminated heredoc leaves a sentinel that matches no terminal, so the
parse fails exactly as the compiler fails.
"""
import re

HEREDOC_OPEN_RE = re.compile(r'<<~?[A-Za-z_][A-Za-z0-9_]*')
QW_OPEN_RE = re.compile(r'q[wif]\(')
BOUNDARY = set(' \t,)]};')
SENTINEL_RE = re.compile(r'\x00HD[0-9]+\x00')

QW_KIND_RE = {
    'qw': re.compile(r'^[^ \t\r\n\f\v()\'"\\\x00-\x1f\x7f]+$'),
    'qi': re.compile(r'^-?(0|[1-9][0-9]*)$'),
    'qf': re.compile(r'^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$'),
}

# dsl.ts: a `json` literal is the IDENT `json` immediately followed by a heredoc token (and
# `json` not being a declared local/function/context name -- that part is name resolution,
# static by construction). A Lark string terminal "json" would shadow every variable named
# json (the corpus calls json(4) as a function), so the pre-lexer fuses the pair into one
# sentinel, exactly like the heredoc sentinels.
JSON_FUSE_RE = re.compile(r'\bjson[ \t]*(\x00HD[0-9]+\x00)')


def fuse_json(text):
    """json + heredoc sentinel -> one \x00JSONn\x00 sentinel. Skipped after '.' or a word
    character (a method name or a longer identifier), mirroring _qw_skip."""
    out = []
    pos = 0
    count = 0
    while True:
        m = JSON_FUSE_RE.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        before = text[:m.start()].rstrip()
        if before and (before[-1].isalnum() or before[-1] in '._'):
            out.append(text[pos:m.end()])
            pos = m.end()
            continue
        out.append(text[pos:m.start()] + f'\x00JSON{count}\x00')
        count += 1
        pos = m.end()
    return ''.join(out), count


def _qw_skip(text, pos):
    """dsl.ts only starts a qw/qi/qf literal when the previous token is not '.' or 'fn'
    (a name or a call before it makes qw an identifier). Approximated on text: the
    preceding non-whitespace text may not end with a word character, '.' or ')'."""
    before = text[:pos].rstrip()
    if not before:
        return False
    last = before[-1]
    if last in '.)':
        return True
    if last.isalnum() or last == '_':
        return True
    return False


def collapse_qw(text):
    """Replace qw/qi/qf literals with sentinel tokens, validating the word list exactly as
    dsl.ts's quoteLiteral does. An unterminated or invalid literal becomes a broken sentinel
    (matches no terminal -> the parse fails, as the compiler fails)."""
    out = []
    pos = 0
    count = 0
    broken = False
    while True:
        m = QW_OPEN_RE.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        name = m.group(0)[:2]
        if _qw_skip(text, m.start()) or '\x00' in text[pos:m.start()]:
            out.append(text[pos:m.end()])
            pos = m.end()
            continue
        # scan to the balanced close, respecting strings and #-comments (mirrors dsl.ts)
        i = m.end()
        depth = 1
        quote = False
        esc = False
        heredoc_inside = False
        while i < len(text) and depth:
            ch = text[i]
            if quote:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    quote = False
            elif ch == '"':
                quote = True
            elif ch == '#':
                nl = text.find('\n', i)
                i = len(text) if nl < 0 else nl
                continue
            elif text.startswith('<<', i):
                heredoc_inside = True
                break
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            i += 1
        if depth:
            out.append(text[pos:m.start()] + f'\x00BADQW\x00')
            out.append(text[m.end():])
            broken = True
            break
        if heredoc_inside:
            # dsl.ts abandons quote-literal mode when the body mentions << (the name becomes
            # an identifier and the parentheses an ordinary call). Left uncollapsed here; the
            # grammar then judges it as a call. No corpus file does this.
            out.append(text[pos:m.end()])
            pos = m.end()
            continue
        span = text[m.end():i - 1]
        if '\x00' in span:
            out.append(text[pos:m.end()])
            pos = m.end()
            continue
        # validate words per kind (comments already stripped word-wise: split on # first)
        words = []
        for row in span.split('\n'):
            row = row.split('#', 1)[0]
            words.extend(w for w in re.split(r'[ \t\r\n\f\v]+', row) if w)
        pat = QW_KIND_RE[name]
        bad = any(not pat.match(w) or ('${' in w) or ('<<' in w) for w in words)
        out.append(text[pos:m.start()])
        if bad:
            out.append('\x00BADQW\x00')
            broken = True
        else:
            out.append(f'\x00{name.upper()}{count}\x00')
            count += 1
        pos = i
    return ''.join(out), count, broken


def _scan_line_for_openers(line):
    """Heredoc openers on one code line, skipping string literals and #-to-EOL comments."""
    found = []
    j = 0
    quote = False
    esc = False
    while j < len(line):
        ch = line[j]
        if quote:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                quote = False
            j += 1
            continue
        if ch == '"':
            quote = True
            j += 1
            continue
        if ch == '#':
            break
        m = HEREDOC_OPEN_RE.match(line, j)
        if m:
            nxt = line[m.end():m.end() + 1]
            if nxt == '' or nxt in BOUNDARY:
                found.append((m.start(), m.end(), m.group(0)))
                j = m.end()
                continue
        j += 1
    return found


def _is_closer(line, tag, dedent):
    if dedent:
        return line.endswith(tag) and line[:len(line) - len(tag)].strip(' \t') == ''
    return line == tag


def find_heredocs(lines):
    """Return (regions, ok): regions is a list of (opener_line, closer_line) inclusive line
    ranges; ok is False when an opener never closes (the compiler rejects those)."""
    regions = []
    ok = True
    i = 0
    while i < len(lines):
        openers = _scan_line_for_openers(lines[i])
        i += 1
        for _start, _end, opentext in openers:
            dedent = opentext.startswith('<<~')
            tag = opentext[3:] if dedent else opentext[2:]
            cursor = i
            closed = False
            while cursor < len(lines):
                if _is_closer(lines[cursor], tag, dedent):
                    closed = True
                    break
                cursor += 1
            if not closed:
                ok = False
                cursor = len(lines) - 1
            regions.append((i - 1, cursor))
            i = cursor + 1
    return regions, ok


def substitute_splices(text, heredoc_lines):
    """Replace ${...} with the int literal 0 outside heredoc bodies -- a parse-level
    stand-in for the compiler's pre-process substitution of a value as a DSL literal
    (R15; the value's text is unknown statically, and every spliceable literal is a
    primary). Balanced braces; no string awareness needed: the compiler splices inside
    string literals too."""
    out = []
    for n, line in enumerate(text.split('\n')):
        if n in heredoc_lines:
            out.append(line)
            continue
        buf = ''
        i = 0
        while i < len(line):
            if line.startswith('${', i):
                depth = 1
                j = i + 2
                while j < len(line) and depth:
                    if line[j] == '{':
                        depth += 1
                    elif line[j] == '}':
                        depth -= 1
                    j += 1
                if depth:
                    buf += line[i:]  # unbalanced: leave for the parser to reject
                    i = len(line)
                    break
                buf += '0'
                i = j
                continue
            buf += line[i]
            i += 1
        out.append(buf)
    return '\n'.join(out)


def prelex(text, splice=False):
    """Return (prepared_text, count_map, unterminated)."""
    lines = text.split('\n')
    regions, ok = find_heredocs(lines)
    body_lines = set()
    for start, end in regions:
        body_lines.update(range(start + 1, end + 1))
    if splice:
        text = substitute_splices('\n'.join(lines), body_lines)
        lines = text.split('\n')
        regions, ok2 = find_heredocs(lines)
        ok = ok and ok2
        body_lines = set()
        for start, end in regions:
            body_lines.update(range(start + 1, end + 1))
    out = []
    skip = set()
    hd_count = 0
    for start, end in regions:
        skip.update(range(start + 1, end + 1))  # body lines and the closer line
    for n, line in enumerate(lines):
        if n in skip:
            continue
        new_line = ''
        cursor = 0
        for s, e, _op in _scan_line_for_openers(line):
            new_line += line[cursor:s] + f'\x00HD{hd_count}\x00'
            hd_count += 1
            cursor = e
        new_line += line[cursor:]
        out.append(new_line)
    text = '\n'.join(out)
    text, json_count = fuse_json(text)
    text, qw_count, qw_broken = collapse_qw(text)
    return text, {'heredoc': hd_count, 'json': json_count, 'qw': qw_count, 'qw_broken': qw_broken}, not ok
