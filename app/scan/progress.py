"""Bounded, JSON-safe progress snapshots for scan jobs."""
from __future__ import annotations

from collections import deque

from ..enrich import HostEnrichment
from ..fingerprint import Fingerprint
from .scanner import PortResult
from .text import sanitize_json, sanitize_text


class ScanProgress:
    """Accumulate useful progress without growing job stats without bound."""

    def __init__(
        self,
        ips: list[str],
        ports: list[int],
        base_stats: dict | None = None,
        *,
        result_limit: int = 500,
        service_limit: int = 200,
        host_limit: int = 200,
    ) -> None:
        self._base_stats = dict(base_stats or {})
        self._ports_per_host = len(ports)
        self._host_port_counts: dict[str, int] = {}
        self._port_results: deque[dict] = deque(maxlen=result_limit)
        self._services: deque[dict] = deque(maxlen=service_limit)
        self._hosts: deque[dict] = deque(maxlen=host_limit)
        self._enrichments: deque[dict] = deque(maxlen=host_limit)
        self._result_limit = result_limit
        self._service_limit = service_limit
        self._host_limit = host_limit

        self.phase = "preparing"
        self.hosts_total = len(ips)
        self.hosts_scanned = 0
        self.hosts_analyzed = 0
        self.hosts_up = 0
        self.ports_total = len(ips) * len(ports)
        self.ports_scanned = 0
        self.port_states = {"open": 0, "closed": 0, "filtered": 0}
        self.errors = 0
        self.port_results_truncated = False
        self.services_truncated = False
        self.hosts_truncated = False
        self.enrichments_truncated = False
        self.current_port: dict | None = None

    def record_port(self, ip: str, result: PortResult) -> None:
        self.ports_scanned += 1
        self.port_states[result.state] = self.port_states.get(result.state, 0) + 1

        count = self._host_port_counts.get(ip, 0) + 1
        self._host_port_counts[ip] = count
        if count == self._ports_per_host:
            self.hosts_scanned += 1

        entry = {
            "ip": ip,
            "port": result.port,
            "transport": result.transport,
            "state": result.state,
            "latency_ms": result.latency_ms,
        }
        self.current_port = entry
        if len(self._port_results) == self._result_limit:
            self.port_results_truncated = True
        self._port_results.append(entry)

    def record_scan_error(self, ip: str | None = None) -> None:
        self.hosts_scanned += 1
        self.errors += 1
        if ip is not None:
            self._append_host({
                "ip": ip,
                "alive": False,
                "open_ports": [],
                "open_port_count": 0,
                "error": True,
            })

    def _append_host(self, finding: dict) -> None:
        if len(self._hosts) == self._host_limit:
            self.hosts_truncated = True
        self._hosts.append(finding)

    def record_host_result(
        self,
        ip: str,
        alive: bool,
        open_ports: list[PortResult],
        fingerprints: dict[int, Fingerprint],
        enrichment: HostEnrichment,
        tls_map: dict[int, dict],
    ) -> None:
        self.hosts_analyzed += 1
        if alive:
            self.hosts_up += 1

        self._append_host({
            "ip": ip,
            "alive": alive,
            "open_ports": [result.port for result in open_ports],
            "open_port_count": len(open_ports),
            "error": False,
        })

        for result in open_ports:
            fingerprint = fingerprints.get(result.port)
            certificate = tls_map.get(result.port)
            subject = certificate.get("subject", {}) if certificate else {}
            finding = {
                "ip": ip,
                "port": result.port,
                "transport": result.transport,
                "service": fingerprint.service if fingerprint else None,
                "product": fingerprint.product if fingerprint else None,
                "version": fingerprint.version if fingerprint else None,
                "confidence": fingerprint.confidence if fingerprint else None,
                "banner": sanitize_text(result.banner),
                "tls": certificate is not None,
                "tls_subject": subject.get("CN"),
            }
            if len(self._services) == self._service_limit:
                self.services_truncated = True
            self._services.append(finding)

        enrichment_finding = {
            "ip": ip,
            "country": enrichment.country,
            "city": enrichment.city,
            "asn": enrichment.asn,
            "as_org": enrichment.as_org,
            "tags": list(enrichment.tags),
            "tls_ports": sorted(tls_map),
        }
        if len(self._enrichments) == self._host_limit:
            self.enrichments_truncated = True
        self._enrichments.append(enrichment_finding)

    def snapshot(self) -> dict:
        return sanitize_json({
            **self._base_stats,
            "phase": self.phase,
            "hosts_total": self.hosts_total,
            "hosts_scanned": self.hosts_scanned,
            "hosts_analyzed": self.hosts_analyzed,
            "hosts_up": self.hosts_up,
            "ports_total": self.ports_total,
            "ports_scanned": self.ports_scanned,
            "ports_per_host": self._ports_per_host,
            "port_states": dict(self.port_states),
            "open_services": self.port_states.get("open", 0),
            "errors": self.errors,
            "current_port": self.current_port,
            "port_results": list(self._port_results),
            "port_results_truncated": self.port_results_truncated,
            "services": list(self._services),
            "services_truncated": self.services_truncated,
            "host_results": list(self._hosts),
            "host_results_truncated": self.hosts_truncated,
            "enrichments": list(self._enrichments),
            "enrichments_truncated": self.enrichments_truncated,
        })
