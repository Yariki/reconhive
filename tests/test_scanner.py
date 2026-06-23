"""Tests for the async scanner, rate limiter, and helpers.

Self-contained: spins up real localhost listeners, no external network.
Run: pytest tests/test_scanner.py -v
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
import time

import pytest

from app.scan.ports import parse_port_spec, resolve_ports
from app.scan.ratelimit import RateLimiter
from app.scan.runner import expand_targets
from app.scan.scanner import PortResult, TcpConnectScanner
from app.scope.exceptions import OutOfScopeError
from app.scope.guard import EntryKind, ScopeEntry, ScopeGuard

NET = ipaddress.ip_network


def guard_allowing_loopback() -> ScopeGuard:
    return ScopeGuard.from_entries([ScopeEntry(NET("127.0.0.0/8"), EntryKind.ALLOW)])


def guard_denying_everything() -> ScopeGuard:
    return ScopeGuard.from_entries([])  # empty allowlist


@pytest.mark.asyncio
async def test_scan_host_reports_each_port_result(monkeypatch):
    scanner = TcpConnectScanner(guard_allowing_loopback())
    reported = []

    async def fake_scan_port(ip, port):
        return PortResult(port, "open" if port == 22 else "closed")

    async def on_port(ip, result):
        reported.append((ip, result.port, result.state))

    monkeypatch.setattr(scanner, "_scan_port", fake_scan_port)
    result = await scanner.scan_host("127.0.0.1", [22, 80], on_port)

    assert len(result.ports) == 2
    assert set(reported) == {
        ("127.0.0.1", 22, "open"),
        ("127.0.0.1", 80, "closed"),
    }


async def _start_listener(banner: bytes | None = None):
    """Start a localhost TCP server. Returns (server, port, counter_getter)."""
    connections = {"count": 0}

    async def handle(reader, writer):
        connections["count"] += 1
        if banner is not None:
            writer.write(banner)
            await writer.drain()
        await asyncio.sleep(0.05)
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port, connections


def _free_port() -> int:
    """Grab then release a port so a connect to it is refused (closed)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# --- the critical safety test ----------------------------------------------

@pytest.mark.asyncio
async def test_out_of_scope_host_sends_no_packets():
    """A host outside scope must raise AND never open a socket."""
    server, port, conns = await _start_listener()
    try:
        scanner = TcpConnectScanner(guard_denying_everything())
        with pytest.raises(OutOfScopeError):
            await scanner.scan_host("127.0.0.1", [port])
        # Proof the gate fired BEFORE any network contact:
        assert conns["count"] == 0
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_is_alive_also_gated():
    scanner = TcpConnectScanner(guard_denying_everything())
    with pytest.raises(OutOfScopeError):
        await scanner.is_alive("8.8.8.8")


# --- functional scanning ----------------------------------------------------

@pytest.mark.asyncio
async def test_open_port_detected():
    server, port, conns = await _start_listener()
    try:
        scanner = TcpConnectScanner(guard_allowing_loopback())
        result = await scanner.scan_host("127.0.0.1", [port])
        assert result.alive
        assert [p.port for p in result.open_ports] == [port]
        assert result.ports[0].latency_ms is not None
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_closed_port_detected():
    port = _free_port()
    scanner = TcpConnectScanner(guard_allowing_loopback())
    result = await scanner.scan_host("127.0.0.1", [port])
    assert result.open_ports == []
    assert result.ports[0].state in ("closed", "filtered")


@pytest.mark.asyncio
async def test_banner_grabbed():
    server, port, conns = await _start_listener(banner=b"SSH-2.0-OpenSSH_9.6\r\n")
    try:
        scanner = TcpConnectScanner(guard_allowing_loopback())
        result = await scanner.scan_host("127.0.0.1", [port])
        assert result.open_ports[0].banner is not None
        assert "SSH-2.0" in result.open_ports[0].banner
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_mixed_open_and_closed():
    server, open_port, conns = await _start_listener()
    closed_port = _free_port()
    try:
        scanner = TcpConnectScanner(guard_allowing_loopback())
        result = await scanner.scan_host("127.0.0.1", [open_port, closed_port])
        states = {p.port: p.state for p in result.ports}
        assert states[open_port] == "open"
        assert states[closed_port] in ("closed", "filtered")
    finally:
        server.close()
        await server.wait_closed()


# --- rate limiter -----------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limiter_paces():
    # 20 tokens/sec, no burst -> 10 acquisitions should take ~0.45s+
    limiter = RateLimiter(20.0, burst=1.0)
    start = time.monotonic()
    for _ in range(10):
        await limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.4  # ~9 intervals of 0.05s


@pytest.mark.asyncio
async def test_rate_limiter_disabled_is_noop():
    limiter = RateLimiter(0)
    start = time.monotonic()
    for _ in range(1000):
        await limiter.acquire()
    assert time.monotonic() - start < 0.1


# --- helpers ----------------------------------------------------------------

def test_parse_port_spec_ranges():
    assert parse_port_spec("22,80,443") == [22, 80, 443]
    assert parse_port_spec("80,8000-8002") == [80, 8000, 8001, 8002]
    assert parse_port_spec("443-440") == [440, 441, 442, 443]  # reversed ok


def test_parse_port_spec_rejects_out_of_range():
    with pytest.raises(ValueError):
        parse_port_spec("70000")


def test_resolve_ports_defaults_to_top_ports():
    assert 443 in resolve_ports(None)
    assert resolve_ports({"ports": "22,80"}) == [22, 80]


def test_expand_targets():
    assert expand_targets(["10.0.0.1"]) == ["10.0.0.1"]
    # /30 has 2 usable hosts (excludes net + broadcast)
    assert expand_targets(["10.0.0.0/30"]) == ["10.0.0.1", "10.0.0.2"]
