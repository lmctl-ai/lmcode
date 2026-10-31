#!/usr/bin/env python3
"""Extract `_lmcode_`/`_dsl_` block bodies from .lms sources, mirroring the outer block
rules (lmscript.ts compileDslBlock + the data-block lexer):

  - an opener line carries the marker (`_lmcode_` or `_dsl_`) with its options, ending in `;`
  - the body is the following lines up to a line that is exactly `end <same marker>`
  - ${...} splices outside heredoc bodies become the stand-in literal 0 (their value text is
    unknown statically; every spliceable literal is a primary)
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prelexer import find_heredocs  # noqa: E402

MARKER_RE = re.compile(r'(_lmcode_|_dsl_)')


def extract_blocks(text):
    """Return a list of (marker, body_text) for each block; raises ValueError on an
    unterminated block (which the outer language itself rejects)."""
    lines = text.split('\n')
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = MARKER_RE.search(line)
        if m and not line.startswith('end '):
            marker = m.group(1)
            head = line[m.end():]
            # The header runs to the mandatory ';' on the marker's own line.
            if ';' not in head:
                # not a block opener we recognize; skip the line
                i += 1
                continue
            body_start = i + 1
            cursor = body_start
            while cursor < len(lines) and lines[cursor] != f'end {marker}':
                cursor += 1
            if cursor >= len(lines):
                raise ValueError(f'unterminated block {marker} opened at line {i + 1}')
            blocks.append((marker, '\n'.join(lines[body_start:cursor])))
            i = cursor + 1
            continue
        i += 1
    return blocks
