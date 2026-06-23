"""Glue: build an Observation for an open port (optionally HTTP-probing) and
run the engine. Used by the scan runner; kept async + dependency-light so it
is testable against localhost listeners.
"""
from __future__ import annotations

from .engine import Fingerprint, FingerprintEngine, Observation, default_engine
from .http_probe import probe_http
from .signatures import HTTP_PORTS, HTTPS_PORTS


def _looks_httpish(port: int, banner: str | None) -> tuple[bool, bool]:
    """Return (should_probe, use_tls)."""
    if port in HTTPS_PORTS:
        return True, True
    if port in HTTP_PORTS:
        return True, False
    # Bare connect-scan banner that already looks like HTTP (rare) -> probe plain.
    if banner and banner.startswith("HTTP/"):
        return True, False
    return False, False


async def fingerprint_service(
    ip: str,
    port: int,
    banner: str | None,
    *,
    engine: FingerprintEngine | None = None,
    http_probe_enabled: bool = True,
    transport: str = "tcp",
) -> Fingerprint:
    engine = engine or default_engine
    obs = Observation(port=port, transport=transport, banner=banner)

    if http_probe_enabled:
        should, tls = _looks_httpish(port, banner)
        if should:
            obs.http = await probe_http(ip, port, tls=tls, host_header=ip)

    return engine.identify(obs)
