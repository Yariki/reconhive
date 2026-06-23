"""ReconHive Scope Guard.

The authorization gate for every scan. Pure stdlib (``ipaddress``) so it has
no DB / network dependency and can be exhaustively unit-tested.

Core model
----------
Authorization is expressed as two sets of CIDR blocks per engagement:

* ``allow`` entries   -- ranges the client has authorized us to scan
* ``deny``  entries   -- carve-outs that OVERRIDE allow (SOW exclusions:
                          "scan 10.0.0.0/16 EXCEPT 10.0.5.0/24")

A target address ``T`` is in scope iff:

    T is contained in the union of active allow blocks
    AND T is NOT contained in any active deny block.

deny always wins. This matches how real engagement scoping works.

CIDR property exploited throughout: two CIDR blocks are either disjoint or
one fully contains the other. They never partially overlap.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Sequence

from .exceptions import InvalidTargetError, OutOfScopeError

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class EntryKind(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ScopeEntry:
    """A single authorization rule. ``expires_at`` is timezone-aware UTC."""

    cidr: IPNetwork
    kind: EntryKind
    engagement_id: str | None = None
    note: str = ""
    expires_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        return self.expires_at is None or self.expires_at > now


class Verdict(str, Enum):
    AUTHORIZED = "authorized"
    DENIED = "denied"
    NOT_IN_ALLOWLIST = "not_in_allowlist"


@dataclass(frozen=True, slots=True)
class Decision:
    """Result of a single-host authorization check. Auditable."""

    target: str
    verdict: Verdict
    reason: str
    matched_entry: ScopeEntry | None = None

    @property
    def authorized(self) -> bool:
        return self.verdict is Verdict.AUTHORIZED


@dataclass(slots=True)
class ScopeResult:
    """Result of partitioning a requested target spec at submission time."""

    authorized: list[IPNetwork] = field(default_factory=list)
    rejected: list[IPNetwork] = field(default_factory=list)

    @property
    def fully_authorized(self) -> bool:
        return bool(self.authorized) and not self.rejected

    def authorized_host_count(self) -> int:
        return sum(net.num_addresses for net in self.authorized)


def parse_target(value: str) -> IPNetwork:
    """Parse an IP or CIDR string into a network. Bare IPs become /32 or /128."""
    text = value.strip()
    if not text:
        raise InvalidTargetError("empty target")
    try:
        if "/" in text:
            return ipaddress.ip_network(text, strict=False)
        return ipaddress.ip_network(ipaddress.ip_address(text))
    except ValueError as exc:
        raise InvalidTargetError(f"cannot parse target {value!r}: {exc}") from exc


def _intersection(a: IPNetwork, b: IPNetwork) -> IPNetwork | None:
    """Intersection of two CIDR blocks: the smaller if nested, else None."""
    if a.version != b.version:
        return None
    if a.subnet_of(b):
        return a
    if b.subnet_of(a):
        return b
    return None


def _subtract(net: IPNetwork, holes: Sequence[IPNetwork]) -> list[IPNetwork]:
    """Return the portions of ``net`` not covered by any block in ``holes``."""
    remaining: list[IPNetwork] = [net]
    for hole in holes:
        nxt: list[IPNetwork] = []
        for piece in remaining:
            inter = _intersection(piece, hole)
            if inter is None:
                nxt.append(piece)
            elif inter == piece:
                pass
            elif inter.subnet_of(piece):
                nxt.extend(piece.address_exclude(inter))
        remaining = nxt
    return remaining


def _collapse(nets: Iterable[IPNetwork]) -> list[IPNetwork]:
    v4 = [n for n in nets if n.version == 4]
    v6 = [n for n in nets if n.version == 6]
    out: list[IPNetwork] = []
    if v4:
        out.extend(ipaddress.collapse_addresses(v4))
    if v6:
        out.extend(ipaddress.collapse_addresses(v6))
    return out


class ScopeGuard:
    """Immutable view over a set of scope entries.

    ``now`` is injected so expiry behaviour is deterministic and testable.
    """

    def __init__(
        self,
        allow: Sequence[ScopeEntry],
        deny: Sequence[ScopeEntry],
        *,
        now: datetime | None = None,
    ) -> None:
        self._now = now or datetime.now(timezone.utc)
        self._allow = [e for e in allow if e.is_active(self._now)]
        self._deny = [e for e in deny if e.is_active(self._now)]
        self._allow_nets = _collapse(e.cidr for e in self._allow)
        self._deny_nets = _collapse(e.cidr for e in self._deny)

    @classmethod
    def from_entries(
        cls, entries: Iterable[ScopeEntry], *, now: datetime | None = None
    ) -> "ScopeGuard":
        entries = list(entries)
        allow = [e for e in entries if e.kind is EntryKind.ALLOW]
        deny = [e for e in entries if e.kind is EntryKind.DENY]
        return cls(allow, deny, now=now)

    def evaluate(self, target: str | IPAddress) -> Decision:
        """Evaluate a single host. Never raises; returns an auditable Decision."""
        text = str(target)
        try:
            addr = ipaddress.ip_address(text)
        except ValueError:
            net = parse_target(text)
            if net.num_addresses != 1:
                return Decision(text, Verdict.DENIED,
                                "evaluate() takes a single host, not a range")
            addr = net.network_address

        for entry in self._deny:
            if addr in entry.cidr:
                return Decision(text, Verdict.DENIED,
                                f"matched deny rule {entry.cidr}", entry)
        for entry in self._allow:
            if addr in entry.cidr:
                return Decision(text, Verdict.AUTHORIZED,
                                f"covered by allow rule {entry.cidr}", entry)
        return Decision(text, Verdict.NOT_IN_ALLOWLIST,
                        "no active allow rule covers this host")

    def is_authorized(self, target: str | IPAddress) -> bool:
        return self.evaluate(target).authorized

    def assert_authorized(self, target: str | IPAddress) -> Decision:
        """Hard gate. Raises :class:`OutOfScopeError` if not authorized.

        Call this in the worker immediately before sending any packet.
        """
        decision = self.evaluate(target)
        if not decision.authorized:
            raise OutOfScopeError(str(target), decision.reason)
        return decision

    def filter_targets(self, requested: Iterable[str | IPNetwork]) -> ScopeResult:
        """Partition a requested target spec into authorized vs rejected nets."""
        result = ScopeResult()
        req_nets = [parse_target(r) if isinstance(r, str) else r for r in requested]

        for req in req_nets:
            covered: list[IPNetwork] = []
            for allow_net in self._allow_nets:
                inter = _intersection(req, allow_net)
                if inter is not None:
                    covered.append(inter)
            covered = _collapse(covered)

            authorized_pieces: list[IPNetwork] = []
            for block in covered:
                authorized_pieces.extend(_subtract(block, self._deny_nets))

            authorized_pieces = _collapse(authorized_pieces)
            result.authorized.extend(authorized_pieces)

            rejected_pieces = _subtract(req, authorized_pieces)
            result.rejected.extend(rejected_pieces)

        result.authorized = _collapse(result.authorized)
        result.rejected = _collapse(result.rejected)
        return result

    @property
    def allow_networks(self) -> list[IPNetwork]:
        return list(self._allow_nets)

    @property
    def deny_networks(self) -> list[IPNetwork]:
        return list(self._deny_nets)

    def __repr__(self) -> str:
        return (f"ScopeGuard(allow={len(self._allow_nets)} blocks, "
                f"deny={len(self._deny_nets)} blocks)")
