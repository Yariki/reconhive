"""Pure (no-DB) tests for the search DSL: lexer, parser, compiler SQL."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.dialects import postgresql

from app.search.compiler import compile_query
from app.search.exceptions import SearchSyntaxError
from app.search.lexer import tokenize
from app.search.parser import parse

EID = uuid.uuid4()


def _sql(query: str) -> str:
    stmt = compile_query(query, EID)
    return str(stmt.compile(dialect=postgresql.dialect())).lower()


# --- lexer ------------------------------------------------------------------

def test_tokenize_basic():
    toks = tokenize('port:443 product:nginx "admin panel" -port:22')
    assert (toks[0].field, toks[0].value, toks[0].negate) == ("port", "443", False)
    assert toks[2].field is None and toks[2].value == "admin panel" and toks[2].quoted
    assert toks[3].field == "port" and toks[3].negate


def test_tokenize_operators_and_ranges():
    toks = tokenize("port:>1024 port:8000-8100 asn:>=100")
    assert (toks[0].op, toks[0].value) == (">", "1024")
    assert (toks[1].op, toks[1].value) == (":", "8000-8100")
    assert (toks[2].op, toks[2].value) == (">=", "100")


def test_tokenize_quoted_field_value():
    toks = tokenize('org:"Example UA Telecom"')
    assert toks[0].field == "org" and toks[0].value == "Example UA Telecom"


# --- parser -----------------------------------------------------------------

def test_parse_splits_filters_and_text():
    q = parse('product:nginx free text "quoted bit"')
    assert [f.field for f in q.filters] == ["product"]
    assert [t.value for t in q.text_terms] == ["free", "text", "quoted bit"]


def test_parse_rejects_unknown_field():
    with pytest.raises(SearchSyntaxError):
        parse("bogus:value")


def test_parse_requires_value():
    with pytest.raises(SearchSyntaxError):
        parse("product:")


def test_parse_bool_field_no_value_ok():
    q = parse("has_tls:")
    assert q.filters[0].field == "has_tls"


# --- compiler SQL shape -----------------------------------------------------

def test_compile_scopes_to_engagement():
    sql = _sql("product:nginx")
    assert "hosts.engagement_id =" in sql
    assert "ilike" in sql


def test_compile_port_comparison():
    assert "services.port >" in _sql("port:>1024")


def test_compile_port_range_between():
    assert "between" in _sql("port:8000-8100")


def test_compile_cidr_uses_inet_containment():
    assert "<<=" in _sql("net:10.0.0.0/8")


def test_compile_freetext_uses_tsquery():
    sql = _sql("admin panel")
    assert "websearch_to_tsquery" in sql
    assert "ts_rank" in sql  # ranked ordering when free text present


def test_compile_negation_wraps_not():
    assert " not " in _sql("-product:nginx")


def test_compile_invalid_cidr_raises():
    with pytest.raises(SearchSyntaxError):
        compile_query("net:not-a-cidr", EID)


def test_compile_invalid_port_raises():
    with pytest.raises(SearchSyntaxError):
        compile_query("port:abc", EID)


def test_compile_has_tls_isnull():
    assert "is not null" in _sql("has_tls:true")
