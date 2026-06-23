"""Tests for bounded job progress snapshots."""
from app.fingerprint import Fingerprint
from app.enrich import HostEnrichment
from app.scan.progress import ScanProgress
from app.scan.scanner import PortResult


def test_progress_tracks_ports_and_discovered_services_with_limits():
    progress = ScanProgress(
        ["127.0.0.1"],
        [22, 80, 443],
        {"authorized_hosts": 1},
        result_limit=2,
        service_limit=1,
    )
    progress.phase = "scanning"
    progress.record_port("127.0.0.1", PortResult(22, "open", latency_ms=1.5))
    progress.record_port("127.0.0.1", PortResult(80, "closed"))
    progress.record_port("127.0.0.1", PortResult(443, "filtered"))
    progress.phase = "analyzing"
    progress.record_host_result(
        "127.0.0.1",
        True,
        [PortResult(22, "open")],
        {22: Fingerprint(service="ssh", product="OpenSSH", version="9.6")},
        HostEnrichment(country="UA", city="Kyiv", asn=64500, tags=["global"]),
        {22: {"subject": {"CN": "ssh.example"}}},
    )

    snapshot = progress.snapshot()
    assert snapshot["authorized_hosts"] == 1
    assert snapshot["ports_scanned"] == snapshot["ports_total"] == 3
    assert snapshot["hosts_scanned"] == snapshot["hosts_up"] == 1
    assert snapshot["port_states"] == {"open": 1, "closed": 1, "filtered": 1}
    assert [result["port"] for result in snapshot["port_results"]] == [80, 443]
    assert snapshot["port_results_truncated"] is True
    assert snapshot["services"] == [{
        "ip": "127.0.0.1",
        "port": 22,
        "transport": "tcp",
        "service": "ssh",
        "product": "OpenSSH",
        "version": "9.6",
        "confidence": 0.0,
        "banner": None,
        "tls": True,
        "tls_subject": "ssh.example",
    }]
    assert snapshot["host_results"] == [{
        "ip": "127.0.0.1",
        "alive": True,
        "open_ports": [22],
        "open_port_count": 1,
        "error": False,
    }]
    assert snapshot["enrichments"][0] == {
        "ip": "127.0.0.1",
        "country": "UA",
        "city": "Kyiv",
        "asn": 64500,
        "as_org": None,
        "tags": ["global"],
        "tls_ports": [22],
    }
