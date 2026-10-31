#!/usr/bin/env python3
"""Translate spec/grammar.ebnf (W3C EBNF subset) into a Lark grammar string.

The subset (kept deliberately small so this translator stays a mechanical proof that the
.ebnf file is machine-checkable, not a second grammar):

  name ::= body          one production per rule; the body may span lines until the next rule
  "..." / '...'          literals
  [a-z] [^...]           character classes (with #xN code points inside)
  #xN #xNNNN             code points (hex)
  A? A* A+ ( A B ) A|B   postfix operators, grouping, alternation
  (* ... *)              comments
  UPPERCASE rule name    a terminal (lexer) production
  lowercase rule name    a parser production
  (* checker: sentinel *)   on a terminal: the structure is documentary; the pre-lexer
                            implements it procedurally (like dsl.ts itself does) and the
                            token matches the sentinel /\x00HD[0-9]+\x00/
  (* checker: documentary *) on a terminal: omitted from the generated grammar entirely
  S / COMMENT            become %ignore directives
"""
import re
import sys

SENTINEL_RE = r'/\x00HD[0-9]+\x00/'

class EbnfError(Exception):
    pass

def strip_comments(text):
    return re.sub(r'\(\*.*?\*\)', '', text, flags=re.S)

def split_rules(text):
    rules = []
    current_name = None
    current_body = []
    for line in text.split('\n'):
        m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*::=', line)
        if m:
            if current_name is not None:
                rules.append((current_name, ' '.join(current_body)))
            current_name = m.group(1)
            current_body = [line[m.end():]]
        elif current_name is not None:
            current_body.append(line)
    if current_name is not None:
        rules.append((current_name, ' '.join(current_body)))
    return rules

# --- expression tokenizer for rule bodies ---
TOKEN_RE = re.compile(r'''
    \s*(?:
      (?P<comment>\(\*.*?\*\))           # nested comments are not supported by design
    | (?P<dquote>"(?:[^"\\]|\\.)*")
    | (?P<squote>'(?:[^'\\]|\\.)*')
    | (?P<class>\[(?:[^\[\]\\]|\\.)*\])
    | (?P<codepoint>\#x[0-9A-Fa-f]+)
    | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
    | (?P<op>[?*+()|])
    | (?P<bad>.)
    )''', re.X)

def tokenize_body(body):
    out = []
    pos = 0
    while pos < len(body):
        if body[pos:].strip() == '':
            break
        m = TOKEN_RE.match(body, pos)
        if not m or m.start() == m.end():
            raise EbnfError(f'cannot tokenize near: {body[pos:pos+40]!r}')
        pos = m.end()
        kind = m.lastgroup
        if kind == 'comment':
            continue
        if kind == 'bad':
            raise EbnfError(f'unexpected character {m.group()!r} in rule body')
        out.append((kind, m.group(kind)))
    return out

def hexpoint(tok):
    digits = tok[2:]
    if len(digits) <= 2:
        return '\\x' + digits.zfill(2)
    return '\\u' + digits.zfill(4)

def class_to_regex(tok):
    inner = tok[1:-1]
    inner = re.sub(r'#x[0-9A-Fa-f]+', lambda m: hexpoint(m.group(0)), inner)
    return '[' + inner + ']'

def literal_to_regex(tok):
    inner = tok[1:-1]
    inner = inner.replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\')
    return re.escape(inner)

def body_to_lark(tokens, resolve_name):
    """Translate a token list to a Lark expression. resolve_name maps an EBNF name to the
    Lark name (or None to drop). Sequences/alternation are flat-mapped."""
    parts = []
    for kind, text in tokens:
        if kind == 'name':
            mapped = resolve_name(text)
            if mapped is None:
                raise EbnfError(f'unresolved name reference {text!r}')
            parts.append(mapped)
        elif kind in ('dquote', 'squote'):
            parts.append(literal_to_regex(text))
        elif kind == 'class':
            parts.append(class_to_regex(text))
        elif kind == 'codepoint':
            parts.append(hexpoint(text))
        else:
            parts.append(text)
    return parts

def parse_rhs(tokens, rule_name='?'):
    """Parse | / ( ) and postfix into a nested tree."""
    pos = 0

    def parse_alt():
        nonlocal pos
        seqs = [parse_seq()]
        while pos < len(tokens) and tokens[pos] == ('op', '|'):
            pos += 1
            seqs.append(parse_seq())
        return ('alt', seqs)

    def parse_seq():
        nonlocal pos
        items = []
        while pos < len(tokens) and tokens[pos] not in [('op', '|'), ('op', ')')]:
            items.append(parse_postfix())
        return ('seq', items)

    def parse_postfix():
        nonlocal pos
        atom = parse_atom()
        while pos < len(tokens) and tokens[pos] in [('op', '?'), ('op', '*'), ('op', '+')]:
            atom = ('post', tokens[pos][1], atom)
            pos += 1
        return atom

    def parse_atom():
        nonlocal pos
        if pos >= len(tokens):
            raise EbnfError('unexpected end of rule body')
        tok = tokens[pos]
        pos += 1
        if tok == ('op', '('):
            node = parse_alt()
            if pos >= len(tokens) or tokens[pos] != ('op', ')'):
                raise EbnfError('unbalanced ( in rule body')
            pos += 1
            return node
        return ('atom', tok)

    tree = parse_alt()
    if pos != len(tokens):
        raise EbnfError('trailing tokens in rule body')
    return tree

def render_rule(tree, resolve_name):
    if tree[0] == 'alt':
        return ' | '.join(render_rule(s, resolve_name) for s in tree[1])
    if tree[0] == 'seq':
        return ' '.join(render_seq_item(i, resolve_name) for i in tree[1]) or '""'
    if tree[0] == 'post':
        return render_atom(tree[2], resolve_name) + tree[1]
    if tree[0] == 'atom':
        return render_atom(tree, resolve_name)
    raise EbnfError(f'bad node {tree[0]}')

def render_seq_item(tree, resolve_name):
    if tree[0] == 'alt':
        return '(' + render_rule(tree, resolve_name) + ')'
    return render_rule(tree, resolve_name)

def render_atom(tree, resolve_name):
    if tree[0] == 'atom':
        kind, text = tree[1]
        if kind == 'name':
            mapped = resolve_name(text)
            if mapped is None:
                raise EbnfError(f'unresolved name reference {text!r}')
            return mapped
        if kind in ('dquote', 'squote'):
            return literal_to_lark(text)
        raise EbnfError(f'non-rule atom {text!r} in a parser rule')
    return '(' + render_rule(tree, resolve_name) + ')'

def literal_to_lark(tok):
    inner = tok[1:-1]
    inner = inner.replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\')
    out = inner.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{out}"'

def render_terminal_regex(tree, terms, memo, stack):
    """Flatten a terminal production into one regex string, inlining terminal refs."""
    if tree[0] == 'alt':
        return '(?:' + '|'.join(render_terminal_regex(s, terms, memo, stack) for s in tree[1]) + ')'
    if tree[0] == 'seq':
        return ''.join(render_terminal_regex(i, terms, memo, stack) for i in tree[1])
    if tree[0] == 'post':
        inner = tree[2]
        if inner[0] == 'atom' and inner[1][0] in ('class', 'codepoint', 'name'):
            base = render_terminal_regex(inner, terms, memo, stack)
        else:
            base = '(?:' + render_terminal_regex(inner, terms, memo, stack) + ')'
        return base + tree[1]
    kind, text = tree[1]
    if kind == 'name':
        if text in stack:
            raise EbnfError(f'recursive terminal {text}')
        if text not in terms:
            raise EbnfError(f'terminal production references non-terminal {text!r}')
        return '(?:' + flatten_terminal(text, terms, memo, stack) + ')'
    if kind in ('dquote', 'squote'):
        return literal_to_regex(text)
    if kind == 'class':
        return class_to_regex(text)
    if kind == 'codepoint':
        return hexpoint(text)
    raise EbnfError(f'bad terminal atom {text!r}')

def flatten_terminal(name, terms, memo, stack):
    if name in memo:
        return memo[name]
    tree = parse_rhs(tokenize_body(terms[name]))
    regex = render_terminal_regex(tree, terms, memo, stack + [name])
    memo[name] = regex
    return regex

def translate(ebnf_text):
    # checker markers sit on their own line directly before the production they annotate:
    #   (* checker: sentinel *)     -- the pre-lexer implements it; emit a sentinel terminal
    #   (* checker: documentary *)  -- structure documentation only; emit nothing
    markers = {}
    for m in re.finditer(r'\(\*\s*checker:\s*(sentinel|documentary)(?::([A-Za-z]+))?\s*\*\)\s*([A-Za-z_][A-Za-z0-9_]*)\s*::=', ebnf_text):
        markers[m.group(3)] = (m.group(1), m.group(2))
    rules = split_rules(strip_comments(ebnf_text.split('(* checker: end *)')[0]))
    term_bodies = {n: b for n, b in rules if n.isupper()}
    rule_names = {n for n, _ in rules if not n.isupper()}

    out = []
    ignores = []
    memo = {}
    for name, body in rules:
        marker = markers.get(name)
        kind = marker[0] if marker else None
        if kind == 'documentary':
            out.append(f'// {name}: documentary (implemented by the pre-lexer)')
            continue
        if name in ('S', 'COMMENT'):
            tree = parse_rhs(tokenize_body(body))
            regex = render_terminal_regex(tree, term_bodies, memo, [])
            ignores.append(f'%ignore /{regex}/')
            continue
        if name.isupper():
            if kind == 'sentinel':
                tag = marker[1] or 'HD'
                out.append(f'{name}: /\\x00{tag}[0-9]+\\x00/')
                continue
            tree = parse_rhs(tokenize_body(body))
            regex = render_terminal_regex(tree, term_bodies, memo, [])
            if '/' in regex:
                raise EbnfError(f'terminal {name} regex contains /; extend the emitter')
            out.append(f'{name}: /{regex}/')
            continue
        tree = parse_rhs(tokenize_body(body))
        def resolve(n):
            if n in rule_names or n in term_bodies:
                return n
            return None
        out.append(f'{name}: {render_rule(tree, resolve)}')
    return '\n'.join(ignores + out) + '\n'

if __name__ == '__main__':
    src = open(sys.argv[1] if len(sys.argv) > 1 else 'spec/grammar.ebnf').read()
    sys.stdout.write(translate(src))
