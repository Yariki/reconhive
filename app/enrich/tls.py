"""TLS certificate enrichment.

Opens a TLS connection (no verification -- we inspect, we don't trust),
extracts the peer certificate in DER form, and parses it with ``cryptography``
into a flat dict suitable for the ``services.tls`` JSONB column.
"""
from __future__ import annotations

import asyncio
import ssl
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtensionOID, NameOID


def _name_attrs(name: x509.Name) -> dict:
    out: dict[str, str] = {}
    for oid, key in (
        (NameOID.COMMON_NAME, "CN"),
        (NameOID.ORGANIZATION_NAME, "O"),
        (NameOID.ORGANIZATIONAL_UNIT_NAME, "OU"),
        (NameOID.COUNTRY_NAME, "C"),
    ):
        vals = name.get_attributes_for_oid(oid)
        if vals:
            out[key] = vals[0].value
    return out


def _sans(cert: x509.Certificate) -> list[str]:
    try:
        ext = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        )
    except x509.ExtensionNotFound:
        return []
    names: list[str] = []
    names.extend(ext.value.get_values_for_type(x509.DNSName))
    names.extend(str(ip) for ip in ext.value.get_values_for_type(x509.IPAddress))
    return names


def _pubkey_info(cert: x509.Certificate) -> dict:
    key = cert.public_key()
    if isinstance(key, rsa.RSAPublicKey):
        return {"type": "RSA", "bits": key.key_size}
    if isinstance(key, ec.EllipticCurvePublicKey):
        return {"type": "EC", "curve": key.curve.name, "bits": key.curve.key_size}
    return {"type": type(key).__name__}


def parse_certificate(der: bytes) -> dict:
    """Parse a DER-encoded cert into a JSONB-ready dict."""
    cert = x509.load_der_x509_certificate(der)
    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc
    now = datetime.now(timezone.utc)

    subject = _name_attrs(cert.subject)
    issuer = _name_attrs(cert.issuer)

    return {
        "subject": subject,
        "issuer": issuer,
        "serial": format(cert.serial_number, "x"),
        "version": cert.version.name,
        "not_before": not_before.isoformat(),
        "not_after": not_after.isoformat(),
        "expired": now > not_after,
        "not_yet_valid": now < not_before,
        "days_until_expiry": (not_after - now).days,
        "self_signed": cert.subject == cert.issuer,
        "subject_alt_names": _sans(cert),
        "signature_algorithm": cert.signature_algorithm_oid._name,
        "public_key": _pubkey_info(cert),
        "fingerprint_sha256": cert.fingerprint(hashes.SHA256()).hex(),
    }


async def fetch_tls_cert(
    ip: str,
    port: int,
    *,
    server_name: str | None = None,
    timeout: float = 5.0,
) -> dict | None:
    """Connect, grab the peer certificate, and parse it. None on failure."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    writer = None
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port, ssl=ctx, server_hostname=server_name),
            timeout=timeout,
        )
        ssl_obj = writer.get_extra_info("ssl_object")
        if ssl_obj is None:
            return None
        der = ssl_obj.getpeercert(binary_form=True)
        if not der:
            return None
        result = parse_certificate(der)
        result["tls_version"] = ssl_obj.version()
        cipher = ssl_obj.cipher()
        if cipher:
            result["cipher"] = {"name": cipher[0], "protocol": cipher[1], "bits": cipher[2]}
        return result
    except (asyncio.TimeoutError, OSError, ssl.SSLError, ValueError):
        return None
    finally:
        if writer is not None:
            try:
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
            except (asyncio.TimeoutError, OSError, ssl.SSLError):
                pass
