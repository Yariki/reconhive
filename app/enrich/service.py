"""Enrichment orchestrator: combine IP classification + GeoIP for a host, and
fetch TLS certs for TLS-bearing services. Kept async + injectable for testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .geoip import GeoIPEnricher
from .netclass import classify_ip
from .tls import fetch_tls_cert

# Ports we attempt a TLS handshake on. Plus anything fingerprinted as a *s
# service (https, imaps, pop3s, smtps) is treated as TLS too.
TLS_PORTS: frozenset[int] = frozenset(
    {443, 465, 563, 636, 853, 990, 993, 995, 5061, 5601, 8443, 9243, 9443}
)


@dataclass(slots=True)
class HostEnrichment:
    country: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    asn: int | None = None
    as_org: str | None = None
    tags: list[str] = field(default_factory=list)


class Enricher:
    def __init__(
        self,
        geoip: GeoIPEnricher | None = None,
        *,
        tls_enabled: bool = True,
    ) -> None:
        self._geoip = geoip
        self._tls_enabled = tls_enabled

    def enrich_host(self, ip: str) -> HostEnrichment:
        cls = classify_ip(ip)
        enr = HostEnrichment(tags=list(cls["tags"]))
        # GeoIP only makes sense for globally routable addresses.
        if cls["is_global"] and self._geoip is not None and self._geoip.enabled:
            geo = self._geoip.lookup(ip)
            enr.country = geo.get("country")
            enr.city = geo.get("city")
            enr.latitude = geo.get("latitude")
            enr.longitude = geo.get("longitude")
            enr.asn = geo.get("asn")
            enr.as_org = geo.get("as_org")
        return enr

    def is_tls_port(self, port: int, service: str | None) -> bool:
        if port in TLS_PORTS:
            return True
        return bool(service) and service.endswith("s") and service not in ("dns",)

    async def enrich_service_tls(
        self, ip: str, port: int, *, server_name: str | None = None
    ) -> dict | None:
        if not self._tls_enabled:
            return None
        return await fetch_tls_cert(ip, port, server_name=server_name)

    def close(self) -> None:
        if self._geoip is not None:
            self._geoip.close()
