"""Tests for enrichment: IP classification, GeoIP (fake reader), TLS parsing."""

from __future__ import annotations

import asyncio
import datetime as dt
import ssl
import tempfile
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.config import Settings
from app.enrich import factory
from app.enrich.factory import build_enricher
from app.enrich.geoip import GeoIPEnricher
from app.enrich.netclass import classify_ip
from app.enrich.service import Enricher
from app.enrich.tls import fetch_tls_cert, parse_certificate


# --- netclass ---------------------------------------------------------------


def test_classify_private():
    c = classify_ip("10.1.2.3")
    assert c["scope"] == "private" and not c["is_global"]
    assert "rfc1918" in c["tags"] and "ipv4" in c["tags"]


def test_classify_loopback_and_cgnat():
    assert classify_ip("127.0.0.1")["scope"] == "loopback"
    assert classify_ip("100.64.0.1")["scope"] == "cgnat"


def test_classify_global():
    c = classify_ip("8.8.8.8")
    assert c["scope"] == "global" and c["is_global"]


def test_classify_ipv6_ula():
    c = classify_ip("fd00::1")
    assert c["version"] == 6 and "ula" in c["tags"]


# --- geoip with a fake reader ----------------------------------------------


class _FakeCity:
    def city(self, ip):
        class R:
            class country:
                iso_code = "UA"

            class city:
                name = "Kyiv"

            class location:
                latitude = 50.45
                longitude = 30.52

        return R()


class _FakeASN:
    def asn(self, ip):
        class R:
            autonomous_system_number = 13335
            autonomous_system_organization = "CLOUDFLARENET"

        return R()


def test_geoip_lookup_with_fake_readers():
    g = GeoIPEnricher(city_reader=_FakeCity(), asn_reader=_FakeASN())
    assert g.enabled
    out = g.lookup("1.1.1.1")
    assert out["country"] == "UA" and out["city"] == "Kyiv"
    assert out["asn"] == 13335 and out["as_org"] == "CLOUDFLARENET"


def test_geoip_disabled_returns_empty():
    g = GeoIPEnricher()
    assert not g.enabled
    assert g.lookup("1.1.1.1") == {}


def test_enricher_skips_geoip_for_private():
    g = GeoIPEnricher(city_reader=_FakeCity(), asn_reader=_FakeASN())
    enr = Enricher(geoip=g).enrich_host("10.0.0.5")
    assert enr.country is None  # private -> no geo lookup
    assert "rfc1918" in enr.tags


def test_enricher_geoip_for_global():
    g = GeoIPEnricher(city_reader=_FakeCity(), asn_reader=_FakeASN())
    enr = Enricher(geoip=g).enrich_host("1.1.1.1")
    assert enr.country == "UA" and enr.asn == 13335


def test_build_enricher_uses_configured_geoip_paths(monkeypatch):
    opened_paths = []

    def fake_open_reader(path: str | None):
        opened_paths.append(path)
        if path is None:
            return None
        if path.endswith("City.mmdb"):
            return _FakeCity()
        if path.endswith("ASN.mmdb"):
            return _FakeASN()
        return None

    monkeypatch.setattr(factory, "_open_reader", fake_open_reader)

    enricher = build_enricher(
        Settings(
            geoip_city_db="/geoip/GeoLite2-City.mmdb",
            geoip_asn_db="/geoip/GeoLite2-ASN.mmdb",
        )
    )
    enr = enricher.enrich_host("1.1.1.1")

    assert enr.country == "UA" and enr.city == "Kyiv"
    assert enr.asn == 13335 and enr.as_org == "CLOUDFLARENET"
    assert opened_paths == [
        "/geoip/GeoLite2-City.mmdb",
        "/geoip/GeoLite2-ASN.mmdb",
    ]


# --- TLS parsing against a real self-signed cert ---------------------------


def _make_self_signed(tmp: Path) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "recon.test"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ReconHive Test"),
        ]
    )
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=90))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("recon.test"), x509.DNSName("www.recon.test")]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp / "cert.pem"
    key_path = tmp / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


def test_parse_certificate_fields():
    with tempfile.TemporaryDirectory() as d:
        cert_path, _ = _make_self_signed(Path(d))
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        parsed = parse_certificate(cert.public_bytes(serialization.Encoding.DER))
        assert parsed["subject"]["CN"] == "recon.test"
        assert parsed["self_signed"] is True
        assert parsed["expired"] is False
        assert "recon.test" in parsed["subject_alt_names"]
        assert parsed["public_key"]["type"] == "RSA"
        assert parsed["public_key"]["bits"] == 2048
        assert len(parsed["fingerprint_sha256"]) == 64


@pytest.mark.asyncio
async def test_fetch_tls_cert_live():
    with tempfile.TemporaryDirectory() as d:
        cert_path, key_path = _make_self_signed(Path(d))
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(cert_path), str(key_path))

        async def handle(reader, writer):
            await asyncio.sleep(0.05)
            writer.close()

        server = await asyncio.start_server(handle, "127.0.0.1", 0, ssl=ctx)
        port = server.sockets[0].getsockname()[1]
        try:
            result = await fetch_tls_cert("127.0.0.1", port, server_name="recon.test")
            assert result is not None
            assert result["subject"]["CN"] == "recon.test"
            assert result["self_signed"] is True
            assert "tls_version" in result
            assert result["cipher"]["bits"] >= 128
        finally:
            server.close()
            await server.wait_closed()
