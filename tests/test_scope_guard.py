"""Exhaustive tests for the Scope Guard."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta, timezone

import pytest

from app.scope.exceptions import InvalidTargetError, OutOfScopeError
from app.scope.guard import EntryKind, ScopeEntry, ScopeGuard, Verdict, parse_target

NET = ipaddress.ip_network
UTC = timezone.utc


def allow(cidr: str, **kw) -> ScopeEntry:
    return ScopeEntry(NET(cidr), EntryKind.ALLOW, **kw)


def deny(cidr: str, **kw) -> ScopeEntry:
    return ScopeEntry(NET(cidr), EntryKind.DENY, **kw)


def test_host_in_allow_is_authorized():
    g = ScopeGuard.from_entries([allow("10.0.0.0/24")])
    d = g.evaluate("10.0.0.5")
    assert d.verdict is Verdict.AUTHORIZED and d.authorized


def test_host_not_in_allowlist_denied():
    g = ScopeGuard.from_entries([allow("10.0.0.0/24")])
    assert g.evaluate("10.0.1.5").verdict is Verdict.NOT_IN_ALLOWLIST


def test_deny_overrides_allow():
    g = ScopeGuard.from_entries([allow("10.0.0.0/16"), deny("10.0.5.0/24")])
    assert g.is_authorized("10.0.4.255")
    assert not g.is_authorized("10.0.5.10")
    assert g.evaluate("10.0.5.10").verdict is Verdict.DENIED


def test_assert_authorized_raises_out_of_scope():
    g = ScopeGuard.from_entries([allow("10.0.0.0/24")])
    g.assert_authorized("10.0.0.1")
    with pytest.raises(OutOfScopeError):
        g.assert_authorized("192.168.1.1")


def test_expired_allow_is_inactive():
    past = datetime.now(UTC) - timedelta(days=1)
    g = ScopeGuard.from_entries([allow("10.0.0.0/24", expires_at=past)])
    assert not g.is_authorized("10.0.0.5")


def test_active_allow_with_future_expiry():
    future = datetime.now(UTC) + timedelta(days=1)
    g = ScopeGuard.from_entries([allow("10.0.0.0/24", expires_at=future)])
    assert g.is_authorized("10.0.0.5")


def test_evaluate_rejects_range_as_single_host():
    g = ScopeGuard.from_entries([allow("10.0.0.0/8")])
    assert g.evaluate("10.0.0.0/24").verdict is Verdict.DENIED


def test_filter_full_coverage():
    g = ScopeGuard.from_entries([allow("10.0.0.0/16")])
    res = g.filter_targets(["10.0.0.0/24"])
    assert res.authorized == [NET("10.0.0.0/24")]
    assert res.rejected == [] and res.fully_authorized


def test_filter_partial_coverage():
    g = ScopeGuard.from_entries([allow("10.0.0.0/24")])
    res = g.filter_targets(["10.0.0.0/23"])
    assert res.authorized == [NET("10.0.0.0/24")]
    assert res.rejected == [NET("10.0.1.0/24")] and not res.fully_authorized


def test_filter_punches_deny_hole():
    g = ScopeGuard.from_entries([allow("10.0.0.0/24"), deny("10.0.0.0/26")])
    res = g.filter_targets(["10.0.0.0/24"])
    assert NET("10.0.0.0/26") not in res.authorized
    assert sum(n.num_addresses for n in res.authorized) == 256 - 64
    assert res.rejected == [NET("10.0.0.0/26")]


def test_filter_request_spanning_two_allows():
    g = ScopeGuard.from_entries([allow("10.0.0.0/24"), allow("10.0.1.0/24")])
    res = g.filter_targets(["10.0.0.0/23"])
    assert res.authorized == [NET("10.0.0.0/23")]
    assert res.rejected == []


def test_filter_request_entirely_outside():
    g = ScopeGuard.from_entries([allow("10.0.0.0/24")])
    res = g.filter_targets(["192.168.0.0/24"])
    assert res.authorized == [] and res.rejected == [NET("192.168.0.0/24")]


def test_filter_request_supernet_of_allow():
    g = ScopeGuard.from_entries([allow("10.0.5.0/24")])
    res = g.filter_targets(["10.0.0.0/16"])
    assert res.authorized == [NET("10.0.5.0/24")]
    assert sum(n.num_addresses for n in res.rejected) == 65536 - 256


def test_authorized_host_count():
    g = ScopeGuard.from_entries([allow("10.0.0.0/24")])
    assert g.filter_targets(["10.0.0.0/24"]).authorized_host_count() == 256


def test_ipv6_allow_and_deny():
    g = ScopeGuard.from_entries([allow("2001:db8::/48"), deny("2001:db8:0:1::/64")])
    assert g.is_authorized("2001:db8::1")
    assert not g.is_authorized("2001:db8:0:1::5")


def test_mixed_versions_dont_intersect():
    g = ScopeGuard.from_entries([allow("10.0.0.0/24")])
    res = g.filter_targets(["2001:db8::/64"])
    assert res.authorized == [] and res.rejected == [NET("2001:db8::/64")]


def test_parse_bare_ip_becomes_host_network():
    assert parse_target("10.0.0.1") == NET("10.0.0.1/32")
    assert parse_target("2001:db8::1") == NET("2001:db8::1/128")


def test_parse_invalid_raises():
    with pytest.raises(InvalidTargetError):
        parse_target("not-an-ip")
    with pytest.raises(InvalidTargetError):
        parse_target("")
