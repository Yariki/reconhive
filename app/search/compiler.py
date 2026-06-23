"""Search DSL compiler: AST -> parameterized SQLAlchemy ``Select``.

Every result is a ``Service`` with its ``Host`` eager-loaded (one row per
service, like a Shodan "banner"). Queries are ALWAYS scoped to one engagement.
Each field has a single builder that coerces its value and raises
``SearchSyntaxError`` on bad input -- there is no raw string interpolation, so
the DSL can't be used for injection.
"""
from __future__ import annotations

import ipaddress
import uuid
from typing import Callable

from sqlalchemy import Select, and_, cast, func, not_, or_, select
from sqlalchemy.dialects.postgresql import CIDR, INET
from sqlalchemy.orm import contains_eager
from sqlalchemy.sql.elements import ColumnElement

from ..db.models import Host, Service, Transport
from .exceptions import SearchSyntaxError
from .parser import FilterClause, Query, parse

_FALSEY = {"false", "no", "0", "off"}


def _as_int(value: str, field: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise SearchSyntaxError(f"{field} expects an integer, got {value!r}") from None


def _numeric(col, op: str, value: str, field: str) -> ColumnElement:
    """Handle '=', comparisons, and 'a-b' ranges for an integer column."""
    if op == ":" and "-" in value and not value.startswith("-"):
        lo_s, _, hi_s = value.partition("-")
        lo, hi = _as_int(lo_s, field), _as_int(hi_s, field)
        return col.between(min(lo, hi), max(lo, hi))
    n = _as_int(value, field)
    return {
        ":": col == n, "=": col == n,
        ">": col > n, "<": col < n, ">=": col >= n, "<=": col <= n,
    }[op]


def _ilike(col, value: str) -> ColumnElement:
    return col.ilike(f"%{value}%")


def _transport(_op: str, value: str) -> ColumnElement:
    try:
        return Service.transport == Transport(value.lower())
    except ValueError:
        raise SearchSyntaxError(f"transport must be tcp or udp, got {value!r}") from None


def _ip_eq(_op: str, value: str) -> ColumnElement:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        raise SearchSyntaxError(f"invalid ip {value!r}") from None
    return Host.ip == cast(value, INET)


def _net(_op: str, value: str) -> ColumnElement:
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError:
        raise SearchSyntaxError(f"invalid CIDR {value!r}") from None
    return Host.ip.op("<<=")(cast(value, CIDR))


def _bool_present(col_expr: ColumnElement, value: str) -> ColumnElement:
    present = value.lower() not in _FALSEY
    return col_expr if present else not_(col_expr)


# field -> builder(op, value) -> condition
FIELDS: dict[str, Callable[[str, str], ColumnElement]] = {
    "port": lambda op, v: _numeric(Service.port, op, v, "port"),
    "asn": lambda op, v: _numeric(Host.asn, op, v, "asn"),
    "transport": _transport,
    "product": lambda _op, v: _ilike(Service.product, v),
    "version": lambda _op, v: _ilike(Service.version, v),
    "banner": lambda _op, v: _ilike(Service.banner, v),
    "org": lambda _op, v: _ilike(Host.as_org, v),
    "os": lambda _op, v: _ilike(Host.os_guess, v),
    "hostname": lambda _op, v: _ilike(Host.hostname, v),
    "city": lambda _op, v: _ilike(Host.city, v),
    "country": lambda _op, v: Host.country == v.upper(),
    "service": lambda _op, v: Service.data["fingerprint"]["service"].astext.ilike(f"%{v}%"),
    "cpe": lambda _op, v: func.array_to_string(Service.cpe, " ").ilike(f"%{v}%"),
    "tag": lambda _op, v: Host.tags.contains([v]),
    "ip": _ip_eq,
    "net": _net,
    "cidr": _net,
    "has_tls": lambda _op, v: _bool_present(Service.tls.isnot(None), v),
    "has_cpe": lambda _op, v: _bool_present(func.cardinality(Service.cpe) > 0, v),
}


def _build_filter(clause: FilterClause) -> ColumnElement:
    cond = FIELDS[clause.field](clause.op, clause.value)
    return not_(cond) if clause.negate else cond


def compile_query(
    query: Query | str,
    engagement_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> Select:
    if isinstance(query, str):
        query = parse(query)

    stmt = (
        select(Service)
        .join(Service.host)
        .options(contains_eager(Service.host))
        .where(Host.engagement_id == engagement_id)
    )

    conditions = [_build_filter(c) for c in query.filters]

    tsquery = None
    pos_terms = [t.value for t in query.text_terms if not t.negate]
    neg_terms = [t.value for t in query.text_terms if t.negate]
    if pos_terms:
        tsquery = func.websearch_to_tsquery("english", " ".join(pos_terms))
        conditions.append(Service.search_vector.op("@@")(tsquery))
    for term in neg_terms:
        conditions.append(
            not_(Service.search_vector.op("@@")(
                func.websearch_to_tsquery("english", term)
            ))
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    if tsquery is not None:
        stmt = stmt.order_by(
            func.ts_rank(Service.search_vector, tsquery).desc(),
            Service.last_seen.desc(),
        )
    else:
        stmt = stmt.order_by(Service.last_seen.desc())

    return stmt.limit(limit).offset(offset)
