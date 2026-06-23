"""Async TCP connect scanner.

Design choices
--------------
* **Connect scan**, not SYN scan: completes a full TCP handshake via
  ``asyncio.open_connection``. Needs no raw sockets / root, is portable, and
  is the right default for authorized engagements where stealth isn't the goal.
* **The scope gate lives here.** ``scan_host`` calls
  ``guard.assert_authorized(ip)`` before opening a single socket. Defense in
  depth: even if a bad target list reaches the scanner, nothing is sent to an
  out-of-scope host. ``OutOfScopeError`` propagates; it is never swallowed.
* **Concurrency** is bounded by a semaphore; **rate** by a token bucket. The
  two are independent knobs.
* A light **banner grab** happens opportunistically on the open socket (we
  already paid for the connection). Full fingerprinting is a later phase.

Port state semantics (connect scan):
* connected            -> ``open``
* connection refused   -> ``closed``   (host is up, port shut)
* timeout / no route   -> ``filtered`` (firewalled or host down)
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from ..scope.guard import ScopeGuard
from .ports import LIVENESS_PROBE_PORTS
from .ratelimit import RateLimiter
from .text import decode_banner


@dataclass(slots=True)
class PortResult:
    port: int
    state: str                      # open | closed | filtered
    transport: str = "tcp"
    banner: str | None = None
    latency_ms: float | None = None

    @property
    def is_open(self) -> bool:
        return self.state == "open"


@dataclass(slots=True)
class HostResult:
    ip: str
    alive: bool = False
    ports: list[PortResult] = field(default_factory=list)

    @property
    def open_ports(self) -> list[PortResult]:
        return [p for p in self.ports if p.is_open]


class TcpConnectScanner:
    def __init__(
        self,
        guard: ScopeGuard,
        *,
        concurrency: int = 200,
        rate_per_sec: float = 500.0,
        connect_timeout: float = 2.0,
        banner_timeout: float = 1.5,
        banner_bytes: int = 2048,
        grab_banners: bool = True,
    ) -> None:
        self._guard = guard
        self._sem = asyncio.Semaphore(concurrency)
        self._limiter = RateLimiter(rate_per_sec)
        self._connect_timeout = connect_timeout
        self._banner_timeout = banner_timeout
        self._banner_bytes = banner_bytes
        self._grab_banners = grab_banners

    # -- single port -------------------------------------------------------

    async def _scan_port(self, ip: str, port: int) -> PortResult:
        await self._limiter.acquire()
        async with self._sem:
            start = time.monotonic()
            writer = None
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=self._connect_timeout,
                )
            except asyncio.TimeoutError:
                return PortResult(port, "filtered")
            except (ConnectionRefusedError, OSError) as exc:
                # Refused => closed (host alive). Other OSErrors => filtered.
                state = "closed" if isinstance(exc, ConnectionRefusedError) else "filtered"
                return PortResult(port, state)

            latency = (time.monotonic() - start) * 1000.0
            banner: str | None = None
            if self._grab_banners:
                banner = await self._read_banner(reader)
            try:
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
            except (asyncio.TimeoutError, OSError):
                pass
            return PortResult(port, "open", banner=banner, latency_ms=round(latency, 2))

    async def _read_banner(self, reader: asyncio.StreamReader) -> str | None:
        try:
            data = await asyncio.wait_for(
                reader.read(self._banner_bytes), timeout=self._banner_timeout
            )
        except (asyncio.TimeoutError, OSError):
            return None
        if not data:
            return None
        return decode_banner(data)

    # -- single host (THE GATE) -------------------------------------------

    async def scan_host(
        self,
        ip: str,
        ports: list[int],
        on_port_result: Callable[[str, PortResult], Awaitable[None]] | None = None,
    ) -> HostResult:
        """Scan one host across ``ports``. Enforces scope before any socket.

        Raises ``OutOfScopeError`` if ``ip`` is not authorized -- and in that
        case no packet is sent.
        """
        self._guard.assert_authorized(ip)  # <-- hard gate, pre-socket

        async def scan_port(port: int) -> PortResult:
            result = await self._scan_port(ip, port)
            if on_port_result is not None:
                await on_port_result(ip, result)
            return result

        results = await asyncio.gather(*(scan_port(port) for port in ports))
        host = HostResult(ip=ip, ports=list(results))
        # Alive if anything responded (open or closed both prove the host is up).
        host.alive = any(r.state in ("open", "closed") for r in results)
        return host

    async def is_alive(self, ip: str, probe_ports: tuple[int, ...] = LIVENESS_PROBE_PORTS) -> bool:
        """Cheap liveness check via a few probe ports. Also gated."""
        self._guard.assert_authorized(ip)
        results = await asyncio.gather(*(self._scan_port(ip, p) for p in probe_ports))
        return any(r.state in ("open", "closed") for r in results)
