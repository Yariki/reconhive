"""Search DSL parser: validate fields, split filters from free text.

Value coercion / range / comparison handling lives in the compiler (one place
per field), so the parser only checks that each field is known and groups
tokens into filter clauses vs free-text terms.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from .exceptions import SearchSyntaxError
from .lexer import tokenize

# Allowlist of queryable fields. Unknown fields are rejected (no silent SQL).
KNOWN_FIELDS: frozenset[str] = frozenset({
    "port", "transport", "product", "version", "service", "cpe", "banner",
    "country", "asn", "org", "os", "hostname", "city", "ip", "net", "cidr",
    "tag", "has_tls", "has_cpe",
})


@dataclass(frozen=True, slots=True)
class FilterClause:
    field: str
    op: str
    value: str
    negate: bool


@dataclass(frozen=True, slots=True)
class TextTerm:
    value: str
    negate: bool


@dataclass(slots=True)
class Query:
    filters: list[FilterClause] = dc_field(default_factory=list)
    text_terms: list[TextTerm] = dc_field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.filters and not self.text_terms


def parse(query_str: str) -> Query:
    q = Query()
    for tok in tokenize(query_str):
        if tok.field is None:
            if tok.value:
                q.text_terms.append(TextTerm(tok.value, tok.negate))
            continue
        if tok.field not in KNOWN_FIELDS:
            raise SearchSyntaxError(
                f"unknown field {tok.field!r}; known: {', '.join(sorted(KNOWN_FIELDS))}"
            )
        if tok.value == "" and tok.field not in ("has_tls", "has_cpe"):
            raise SearchSyntaxError(f"field {tok.field!r} requires a value")
        q.filters.append(FilterClause(tok.field, tok.op, tok.value, tok.negate))
    return q
