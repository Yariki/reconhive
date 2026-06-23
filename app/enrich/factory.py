"""Runtime construction for optional enrichment dependencies."""

from __future__ import annotations

from typing import Any

from ..config import Settings, get_settings
from .geoip import GeoIPEnricher
from .service import Enricher

def _open_reader(path: str | None) -> Any | None:
    if path is None:
        return None
    try:
        import geoip2.database  # noqa: PLC0415
    except ImportError:
        return None
    try:
        return geoip2.database.Reader(path)
    except (OSError, ValueError):
        return None


def build_enricher(settings: Settings | None = None) -> Enricher:
    """Build the scan enricher from application settings."""
    settings = settings or get_settings()
    geoip = None
    if settings.geoip_city_db or settings.geoip_asn_db:
        city_reader = _open_reader(settings.geoip_city_db)
        asn_reader = _open_reader(settings.geoip_asn_db)
        geoip = GeoIPEnricher(
            city_db=settings.geoip_city_db,
            asn_db=settings.geoip_asn_db,   
            city_reader=city_reader,
            asn_reader=asn_reader,
        )
    return Enricher(geoip=geoip)
