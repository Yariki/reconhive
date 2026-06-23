"""Port specifications and a default top-ports list."""
from __future__ import annotations

from typing import Iterable

# A compact, pragmatic "top ports" set for discovery sweeps. Not exhaustive;
# the job can always pass an explicit list via params["ports"].
TOP_PORTS: tuple[int, ...] = (
    21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 161, 389, 443, 445,
    465, 587, 631, 993, 995, 1025, 1433, 1521, 1723, 2049, 2375, 2376,
    3000, 3306, 3389, 5060, 5432, 5601, 5672, 5900, 5985, 6379, 7001,
    8000, 8008, 8080, 8081, 8088, 8443, 8888, 9000, 9090, 9200, 9300,
    11211, 15672, 27017,
)

# Ports likely to elicit a TCP response, used for liveness probing.
LIVENESS_PROBE_PORTS: tuple[int, ...] = (80, 443, 22, 445, 3389, 8080)


def parse_port_spec(spec: str | Iterable[int]) -> list[int]:
    """Parse '22,80,443' or '1-1024' or '80,8000-8100' into a sorted port list.

    Accepts an iterable of ints directly too.
    """
    if not isinstance(spec, str):
        return sorted({int(p) for p in spec})

    ports: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo_s, hi_s = chunk.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
            if lo > hi:
                lo, hi = hi, lo
            ports.update(range(lo, hi + 1))
        else:
            ports.add(int(chunk))
    bad = [p for p in ports if not (0 <= p <= 65535)]
    if bad:
        raise ValueError(f"ports out of range: {sorted(bad)}")
    return sorted(ports)


def resolve_ports(params: dict | None) -> list[int]:
    """Pick the port list for a job from its params, defaulting to TOP_PORTS."""
    params = params or {}
    if "ports" in params and params["ports"]:
        return parse_port_spec(params["ports"])
    return list(TOP_PORTS)
