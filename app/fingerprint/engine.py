"""Fingerprint engine.

``identify(Observation) -> Fingerprint``. Pure (no I/O): given a banner and/or
parsed HTTP fields, returns the best structured match. The active HTTP probe
that populates ``Observation.http`` lives in ``http_probe.py``; wiring that to
the scanner lives in ``service.py``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .http_probe import HttpResponse
from .signatures import PORT_SERVICES, SIGNATURES, Signature

_BACKREF = re.compile(r"\\(\d+|g<\d+>)")


@dataclass(slots=True)
class Observation:
    port: int
    transport: str = "tcp"
    banner: str | None = None
    http: HttpResponse | None = None
    tls: dict | None = None

    def field_text(self, name: str) -> str:
        if name == "banner":
            return self.banner or ""
        if self.http is None:
            return ""
        return {
            "http_server": self.http.server or "",
            "http_powered_by": self.http.powered_by or "",
            "http_body": self.http.body_snippet or "",
        }.get(name, "")


@dataclass(slots=True)
class Fingerprint:
    service: str | None = None
    product: str | None = None
    version: str | None = None
    extra_info: str | None = None
    cpe: list[str] = field(default_factory=list)
    os: str | None = None
    device_type: str | None = None
    hostname: str | None = None
    confidence: float = 0.0
    source: str = "unknown"

    @property
    def identified(self) -> bool:
        return self.product is not None or self.confidence >= 0.5


def _resolve(template: str | None, m: re.Match[str]) -> str | None:
    """Expand \\1 / \\g<1> backrefs, treating absent groups as empty."""
    if template is None:
        return None

    def repl(mo: re.Match[str]) -> str:
        token = mo.group(1)
        idx = int(token[2:-1]) if token.startswith("g<") else int(token)
        try:
            return m.group(idx) or ""
        except (IndexError, re.error):
            return ""

    out = _BACKREF.sub(repl, template).strip()
    return out or None


def _build_cpe(template: str | None, version: str | None) -> list[str]:
    if not template:
        return []
    return [template.format(version=version or "*")]


def _score(sig: Signature, m: re.Match[str], version: str | None, port: int) -> float:
    score = sig.confidence
    if version:
        score += 0.02
    if sig.ports and port in sig.ports:
        score += 0.02
    return min(score, 1.0)


class FingerprintEngine:
    def __init__(self, signatures: list[Signature] | None = None) -> None:
        self._signatures = signatures if signatures is not None else SIGNATURES

    def identify(self, obs: Observation) -> Fingerprint:
        best: Fingerprint | None = None
        best_score = -1.0

        for sig in self._signatures:
            if sig.ports and obs.port not in sig.ports:
                continue
            text = obs.field_text(sig.field)
            if not text:
                continue
            m = sig.pattern.search(text)
            if not m:
                continue

            version = _resolve(sig.version, m)
            score = _score(sig, m, version, obs.port)
            if score <= best_score:
                continue

            best_score = score
            best = Fingerprint(
                service=sig.service,
                product=_resolve(sig.product, m),
                version=version,
                extra_info=_resolve(sig.extra_info, m),
                cpe=_build_cpe(sig.cpe, version),
                os=sig.os,
                device_type=sig.device_type,
                confidence=round(score, 3),
                source=f"{sig.service}:{sig.field}",
            )

        if best is not None:
            if best.service is None:
                best.service = PORT_SERVICES.get(obs.port)
            return best

        # No signature matched -> fall back to the port's conventional service.
        return Fingerprint(
            service=PORT_SERVICES.get(obs.port),
            confidence=0.3 if obs.port in PORT_SERVICES else 0.0,
            source="port-prior",
        )


# Module-level default engine for convenience.
default_engine = FingerprintEngine()
