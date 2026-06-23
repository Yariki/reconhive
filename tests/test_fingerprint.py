"""Tests for the fingerprint engine, signatures, and HTTP probe."""
from __future__ import annotations

import asyncio

import pytest

from app.fingerprint.engine import FingerprintEngine, Observation
from app.fingerprint.http_probe import HttpResponse, probe_http, _parse_http
from app.fingerprint.service import fingerprint_service

ENGINE = FingerprintEngine()


def fp_banner(banner: str, port: int = 0):
    return ENGINE.identify(Observation(port=port, banner=banner))


def fp_http(port: int, *, server=None, powered_by=None, body=""):
    resp = HttpResponse(server=server, powered_by=powered_by, body_snippet=body)
    return ENGINE.identify(Observation(port=port, http=resp))


# --- SSH --------------------------------------------------------------------

def test_openssh():
    fp = fp_banner("SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13.5", port=22)
    assert fp.product == "OpenSSH"
    assert fp.version == "9.6p1"
    assert fp.service == "ssh"
    assert fp.cpe == ["cpe:2.3:a:openbsd:openssh:9.6p1:*:*:*:*:*:*:*"]
    assert "Ubuntu" in (fp.extra_info or "")
    assert fp.confidence >= 0.95


def test_dropbear():
    fp = fp_banner("SSH-2.0-dropbear_2022.83", port=22)
    assert fp.product == "Dropbear sshd"
    assert fp.version == "2022.83"


def test_generic_ssh_fallback():
    fp = fp_banner("SSH-2.0-CrushFTPSSHD", port=22)
    assert fp.service == "ssh"
    assert fp.product == "CrushFTPSSHD"
    assert fp.confidence < 0.95  # generic match


# --- FTP / SMTP / mail ------------------------------------------------------

def test_vsftpd():
    fp = fp_banner("220 (vsFTPd 3.0.5)", port=21)
    assert fp.product == "vsftpd" and fp.version == "3.0.5"
    assert fp.cpe == ["cpe:2.3:a:vsftpd_project:vsftpd:3.0.5:*:*:*:*:*:*:*"]


def test_proftpd():
    fp = fp_banner("220 ProFTPD 1.3.7a Server ready.", port=21)
    assert fp.product == "ProFTPD" and fp.version == "1.3.7a"


def test_postfix():
    fp = fp_banner("220 mail.example.com ESMTP Postfix (Ubuntu)", port=25)
    assert fp.product == "Postfix smtpd" and fp.service == "smtp"


def test_exim_version():
    fp = fp_banner("220 mx ESMTP Exim 4.96 Mon, 01 Jan 2024", port=25)
    assert fp.product == "Exim smtpd" and fp.version == "4.96"


def test_dovecot_pop3_and_imap():
    fp1 = fp_banner("+OK Dovecot ready.", port=110)
    assert fp1.product == "Dovecot pop3d" and fp1.service == "pop3"
    fp2 = fp_banner("* OK [CAPABILITY IMAP4rev1] Dovecot ready.", port=143)
    assert fp2.product == "Dovecot imapd" and fp2.service == "imap"


# --- HTTP servers (Server header field) -------------------------------------

def test_nginx():
    fp = fp_http(80, server="nginx/1.24.0")
    assert fp.product == "nginx" and fp.version == "1.24.0"
    assert fp.cpe == ["cpe:2.3:a:nginx:nginx:1.24.0:*:*:*:*:*:*:*"]


def test_apache():
    fp = fp_http(80, server="Apache/2.4.58 (Ubuntu)")
    assert fp.product == "Apache httpd" and fp.version == "2.4.58"


def test_iis_flags_windows():
    fp = fp_http(80, server="Microsoft-IIS/10.0")
    assert fp.product == "Microsoft IIS httpd" and fp.os == "Windows"


def test_php_powered_by():
    fp = fp_http(80, server="Apache/2.4.58", powered_by="PHP/8.2.7")
    # Server header wins (higher confidence) but the X-Powered-By path resolves too.
    assert fp.product in ("Apache httpd", "PHP")


# --- datastores -------------------------------------------------------------

def test_redis():
    fp = fp_banner("redis_version:7.2.4\r\nredis_mode:standalone", port=6379)
    assert fp.product == "Redis" and fp.version == "7.2.4"


def test_mariadb_handshake():
    fp = fp_banner("\n5.5.5-10.6.16-MariaDB-1:10.6.16+maria~ubu2204", port=3306)
    assert fp.product == "MariaDB" and fp.version == "10.6.16"


def test_mysql_handshake():
    fp = fp_banner("\n8.0.36\x00caching_sha2_password", port=3306)
    assert fp.product == "MySQL" and fp.version == "8.0.36"


def test_elasticsearch_body():
    body = '{"name":"node-1","version":{"number":"8.12.0","build_flavor":"default"}}'
    fp = fp_http(9200, body=body)
    assert fp.product == "Elasticsearch" and fp.version == "8.12.0"


# --- port priors & no-match -------------------------------------------------

def test_port_prior_postgresql():
    # PostgreSQL doesn't speak first; no banner -> fall back to port service.
    fp = ENGINE.identify(Observation(port=5432, banner=None))
    assert fp.service == "postgresql"
    assert fp.product is None
    assert fp.confidence == pytest.approx(0.3)


def test_unknown_port_no_match():
    fp = ENGINE.identify(Observation(port=49231, banner=None))
    assert fp.product is None and fp.confidence == 0.0


# --- HTTP probe parser (pure) ----------------------------------------------

def test_parse_http_response():
    raw = (
        b"HTTP/1.1 200 OK\r\n"
        b"Server: nginx/1.25.3\r\n"
        b"X-Powered-By: Express\r\n"
        b"Content-Type: text/html\r\n\r\n"
        b"<html><head><title>Dashboard</title></head><body>hi</body></html>"
    )
    resp = _parse_http(raw)
    assert resp.status == 200
    assert resp.server == "nginx/1.25.3"
    assert resp.powered_by == "Express"
    assert resp.title == "Dashboard"


# --- HTTP probe live (localhost) -------------------------------------------

@pytest.mark.asyncio
async def test_probe_http_live():
    async def handle(reader, writer):
        await reader.read(1024)  # consume the GET
        writer.write(
            b"HTTP/1.0 200 OK\r\nServer: nginx/1.24.0\r\n\r\n"
            b"<title>Welcome</title>"
        )
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        resp = await probe_http("127.0.0.1", port)
        assert resp is not None
        assert resp.server == "nginx/1.24.0"
        assert resp.title == "Welcome"
        fp = ENGINE.identify(Observation(port=80, http=resp))
        assert fp.product == "nginx" and fp.version == "1.24.0"
    finally:
        server.close()
        await server.wait_closed()


# --- glue: fingerprint_service banner-first path (no network) --------------

@pytest.mark.asyncio
async def test_fingerprint_service_banner_path():
    fp = await fingerprint_service("127.0.0.1", 22, "SSH-2.0-OpenSSH_9.6", http_probe_enabled=False)
    assert fp.product == "OpenSSH" and fp.version == "9.6"
