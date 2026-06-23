"""Active HTTP(S) probe.

Banner-grabbing only works for protocols that speak first (SSH, FTP, SMTP...).
HTTP stays silent until a request arrives, so we send a minimal ``GET`` and
parse the response. The probe assumes the caller has already authorized the
host (it targets an already-open, in-scope port).
"""
from __future__ import annotations

import asyncio
import re
import ssl
from dataclasses import dataclass, field

_TITLE_RE = re.compile(rb"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_STATUS_RE = re.compile(r"^HTTP/(\d(?:\.\d)?)\s+(\d{3})\s*(.*)$")


@dataclass(slots=True)
class HttpResponse:
    status: int | None = None
    reason: str | None = None
    http_version: str | None = None
    server: str | None = None
    powered_by: str | None = None
    location: str | None = None
    title: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body_snippet: str = ""


def _parse_http(raw: bytes) -> HttpResponse | None:
    sep = raw.find(b"\r\n\r\n")
    if sep == -1:
        sep = raw.find(b"\n\n")
        head, body = (raw[:sep], raw[sep + 2:]) if sep != -1 else (raw, b"")
    else:
        head, body = raw[:sep], raw[sep + 4:]

    head_text = head.decode("iso-8859-1", errors="replace")
    lines = head_text.split("\n")
    if not lines:
        return None

    resp = HttpResponse()
    status_m = _STATUS_RE.match(lines[0].strip())
    if status_m:
        resp.http_version = status_m.group(1)
        resp.status = int(status_m.group(2))
        resp.reason = status_m.group(3).strip() or None

    for line in lines[1:]:
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key:
            resp.headers[key] = val

    resp.server = resp.headers.get("server")
    resp.powered_by = resp.headers.get("x-powered-by")
    resp.location = resp.headers.get("location")

    title_m = _TITLE_RE.search(body[:8192])
    if title_m:
        resp.title = title_m.group(1).decode("utf-8", errors="replace").strip() or None

    resp.body_snippet = body[:4096].decode("utf-8", errors="replace")
    return resp


async def probe_http(
    ip: str,
    port: int,
    *,
    tls: bool = False,
    host_header: str | None = None,
    timeout: float = 4.0,
    max_bytes: int = 65_536,
) -> HttpResponse | None:
    """Send a minimal GET and parse the response. Returns None on failure."""
    ssl_ctx: ssl.SSLContext | None = None
    if tls:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE  # we fingerprint, we don't trust

    writer = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port, ssl=ssl_ctx), timeout=timeout
        )
        host = host_header or ip
        request = (
            f"GET / HTTP/1.0\r\n"
            f"Host: {host}\r\n"
            f"User-Agent: ReconHive/0.1 (authorized-scan)\r\n"
            f"Accept: */*\r\n"
            f"Connection: close\r\n\r\n"
        )
        writer.write(request.encode("ascii"))
        await asyncio.wait_for(writer.drain(), timeout=timeout)

        chunks: list[bytes] = []
        total = 0
        while total < max_bytes:
            chunk = await asyncio.wait_for(reader.read(8192), timeout=timeout)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        return _parse_http(b"".join(chunks))
    except (asyncio.TimeoutError, OSError, ssl.SSLError):
        return None
    finally:
        if writer is not None:
            try:
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
            except (asyncio.TimeoutError, OSError):
                pass
