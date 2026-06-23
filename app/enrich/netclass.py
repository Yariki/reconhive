"""Pure IP classification.

No external database needed -- ``ipaddress`` already knows the special-purpose
ranges. Useful on its own (tagging internal hosts in a pentest) and as the
first cheap pass before any GeoIP lookup, which is meaningless for private IPs.
"""
from __future__ import annotations

import ipaddress

_CGNAT_V4 = ipaddress.ip_network("100.64.0.0/10")  # RFC 6598


def classify_ip(ip: str) -> dict:
    """Return {scope, version, is_global, tags} for an address."""
    addr = ipaddress.ip_address(ip)
    tags: list[str] = []

    if addr.is_loopback:
        scope = "loopback"
    elif addr.is_unspecified:
        scope = "unspecified"
    elif addr.is_link_local:
        scope = "link-local"
    elif addr.is_multicast:
        scope = "multicast"
    elif addr.version == 4 and addr in _CGNAT_V4:
        scope = "cgnat"
        tags.append("carrier-grade-nat")
    elif addr.is_private:
        scope = "private"
        tags.append("rfc1918" if addr.version == 4 else "ula")
    elif addr.is_reserved:
        scope = "reserved"
    elif addr.is_global:
        scope = "global"
    else:
        scope = "other"

    tags.append(f"ipv{addr.version}")
    tags.append(scope)
    return {
        "scope": scope,
        "version": addr.version,
        "is_global": bool(addr.is_global),
        "tags": tags,
    }
