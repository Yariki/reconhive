"""GeoIP / ASN enrichment.

Backed by MaxMind GeoLite2 ``.mmdb`` files when available. These can't be
bundled (license + size), so the enricher degrades gracefully: if ``geoip2``
isn't installed or no DB path is configured, ``lookup`` returns ``{}`` and the
pipeline simply records no geo data. The reader is injectable for testing.

To enable: ``pip install geoip2`` and point the settings at GeoLite2-City.mmdb
and GeoLite2-ASN.mmdb.
"""
from __future__ import annotations

from typing import Any, Protocol


class _Reader(Protocol):
    def city(self, ip: str) -> Any: ...
    def asn(self, ip: str) -> Any: ...


class GeoIPEnricher:
    def __init__(
        self,
        city_db: str | None = None,
        asn_db: str | None = None,
        *,
        city_reader: Any | None = None,
        asn_reader: Any | None = None,
    ) -> None:
        self._city = city_reader
        self._asn = asn_reader
        if city_db and self._city is None:
            self._city = self._open(city_db)
        if asn_db and self._asn is None:
            self._asn = self._open(asn_db)

    @staticmethod
    def _open(path: str) -> Any | None:
        try:
            import geoip2.database  # noqa: PLC0415
        except ImportError:
            return None
        try:
            return geoip2.database.Reader(path)
        except (OSError, ValueError):
            return None

    @property
    def enabled(self) -> bool:
        return self._city is not None or self._asn is not None

    def lookup(self, ip: str) -> dict:
        out: dict = {}
        if self._city is not None:
            try:
                resp = self._city.city(ip)
                out["country"] = resp.country.iso_code
                out["city"] = resp.city.name
                if resp.location.latitude is not None:
                    out["latitude"] = resp.location.latitude
                    out["longitude"] = resp.location.longitude
            except Exception:  # geoip2.errors.AddressNotFoundError, etc.
                pass
        if self._asn is not None:
            try:
                resp = self._asn.asn(ip)
                out["asn"] = resp.autonomous_system_number
                out["as_org"] = resp.autonomous_system_organization
            except Exception:
                pass
        return {k: v for k, v in out.items() if v is not None}

    def close(self) -> None:
        for r in (self._city, self._asn):
            if r is not None and hasattr(r, "close"):
                r.close()
