"""Search DSL lexer.

Turns a query string into raw tokens. Grammar (Shodan-flavoured):

    term           := negation? (filter | freetext)
    negation       := '-'
    filter         := field ':' op? value
    op             := '>' | '<' | '>=' | '<='
    value          := quoted | bareword            (bareword stops at space)
    freetext       := quoted | bareword

Examples:
    port:443 product:nginx country:UA "admin panel" -port:22 port:>1024
"""
from __future__ import annotations

from dataclasses import dataclass

_OPS = (">=", "<=", ">", "<")
_QUOTES = "\"'"


@dataclass(frozen=True, slots=True)
class RawToken:
    negate: bool
    field: str | None      # None => free-text term
    op: str                # ':' for default, or one of _OPS
    value: str
    quoted: bool


def _read_quoted(q: str, i: int) -> tuple[str, int]:
    quote = q[i]
    i += 1
    start = i
    while i < len(q) and q[i] != quote:
        i += 1
    val = q[start:i]
    if i < len(q):
        i += 1  # consume closing quote
    return val, i


def tokenize(query: str) -> list[RawToken]:
    tokens: list[RawToken] = []
    i, n = 0, len(query)

    while i < n:
        if query[i].isspace():
            i += 1
            continue

        negate = False
        if query[i] == "-":
            negate = True
            i += 1
            if i >= n:
                break

        # Quoted free-text term.
        if query[i] in _QUOTES:
            val, i = _read_quoted(query, i)
            tokens.append(RawToken(negate, None, ":", val, True))
            continue

        # Read up to ':' or whitespace to see if this is a field.
        j = i
        while j < n and query[j] not in ": \t":
            j += 1

        if j < n and query[j] == ":":
            field = query[i:j].lower()
            i = j + 1
            op = ":"
            for o in _OPS:
                if query[i:i + len(o)] == o:
                    op = o
                    i += len(o)
                    break
            if i < n and query[i] in _QUOTES:
                val, i = _read_quoted(query, i)
                quoted = True
            else:
                start = i
                while i < n and not query[i].isspace():
                    i += 1
                val = query[start:i]
                quoted = False
            tokens.append(RawToken(negate, field, op, val, quoted))
        else:
            # Bare free-text word.
            val = query[i:j]
            i = j
            tokens.append(RawToken(negate, None, ":", val, False))

    return tokens
