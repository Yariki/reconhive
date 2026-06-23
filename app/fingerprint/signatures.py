"""Fingerprint signatures.

A signature matches a regex against one named text field of an observation
(``banner``, ``http_server``, ``http_powered_by``, ``http_body``) and yields a
structured product/version/CPE via backreference templates -- the same idea as
Nmap's ``nmap-service-probes`` ``p//v//`` match lines, kept small and curated.

CPE templates use ``{version}`` (resolved to the detected version, or ``*``).
Product/version/extra_info templates use ``\\1`` backrefs into the match.

``ports`` scopes a signature: a signature with non-empty ``ports`` is only
tried when the observed port is in that set -- this lets greedy patterns (e.g.
the MySQL handshake version) stay safely pinned to their port.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as _field


@dataclass(frozen=True, slots=True)
class Signature:
    service: str                       # protocol/service name, e.g. "ssh"
    pattern: re.Pattern[str]
    field: str = "banner"              # which observation field to match
    product: str | None = None         # may contain \1 backrefs
    version: str | None = None
    extra_info: str | None = None
    cpe: str | None = None             # template with {version}
    os: str | None = None
    device_type: str | None = None
    ports: frozenset[int] = _field(default_factory=frozenset)
    confidence: float = 0.95


def _sig(service, regex, *, field="banner", flags=re.IGNORECASE,
         ports=(), **kw) -> Signature:
    return Signature(
        service=service,
        pattern=re.compile(regex, flags),
        field=field,
        ports=frozenset(ports),
        **kw,
    )


# Common service names keyed by port -- the low-confidence fallback when no
# signature matches (e.g. PostgreSQL/RDP/SMB which don't speak first).
PORT_SERVICES: dict[int, str] = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "domain",
    80: "http", 110: "pop3", 111: "rpcbind", 135: "msrpc", 139: "netbios-ssn",
    143: "imap", 161: "snmp", 389: "ldap", 443: "https", 445: "microsoft-ds",
    465: "smtps", 587: "submission", 631: "ipp", 993: "imaps", 995: "pop3s",
    1433: "ms-sql-s", 1521: "oracle", 1723: "pptp", 2049: "nfs",
    2375: "docker", 2376: "docker-tls", 3000: "http", 3306: "mysql",
    3389: "ms-wbt-server", 5060: "sip", 5432: "postgresql", 5601: "kibana",
    5672: "amqp", 5900: "vnc", 5985: "wsman", 6379: "redis", 7001: "weblogic",
    8000: "http-alt", 8008: "http", 8080: "http-proxy", 8081: "http",
    8088: "http", 8443: "https-alt", 8888: "http", 9000: "http",
    9090: "http", 9200: "elasticsearch", 9300: "elasticsearch",
    11211: "memcached", 15672: "rabbitmq-mgmt", 27017: "mongodb",
}

# Ports we will actively HTTP-probe (request-first). TLS ports get a TLS probe.
HTTP_PORTS: frozenset[int] = frozenset(
    {80, 81, 591, 3000, 5000, 8000, 8008, 8080, 8081, 8088, 8888, 9000, 9090}
)
HTTPS_PORTS: frozenset[int] = frozenset({443, 8443, 9443, 5601, 9200})


SIGNATURES: list[Signature] = [
    # --- SSH (server announces on connect) ---
    _sig("ssh", r"^SSH-\d+\.\d+-OpenSSH[_-]([\w.]+)\s*(.*)$", flags=0,
         product="OpenSSH", version=r"\1", extra_info=r"\2",
         cpe="cpe:2.3:a:openbsd:openssh:{version}:*:*:*:*:*:*:*", confidence=0.98),
    _sig("ssh", r"^SSH-\d+\.\d+-dropbear[_-]?([\w.]*)", flags=0,
         product="Dropbear sshd", version=r"\1",
         cpe="cpe:2.3:a:dropbear_ssh_project:dropbear_ssh:{version}:*:*:*:*:*:*:*",
         confidence=0.97),
    _sig("ssh", r"^SSH-(\d+\.\d+)-(.+?)\s*$", flags=0,
         product=r"\2", extra_info=r"protocol \1", confidence=0.55),

    # --- FTP ---
    _sig("ftp", r"220.*\(vsFTPd ([\w.]+)\)", product="vsftpd", version=r"\1",
         cpe="cpe:2.3:a:vsftpd_project:vsftpd:{version}:*:*:*:*:*:*:*", confidence=0.97),
    _sig("ftp", r"220[- ]ProFTPD ([\w.]+)", product="ProFTPD", version=r"\1",
         cpe="cpe:2.3:a:proftpd:proftpd:{version}:*:*:*:*:*:*:*", confidence=0.96),
    _sig("ftp", r"220.*Pure-FTPd", product="Pure-FTPd",
         cpe="cpe:2.3:a:pureftpd:pure-ftpd:*:*:*:*:*:*:*:*", confidence=0.9),
    _sig("ftp", r"220.*FileZilla Server[^\d]*([\d.]+)?",
         product="FileZilla Server", version=r"\1", confidence=0.9),
    _sig("ftp", r"^220[ -]", product=None, confidence=0.4),

    # --- SMTP ---
    _sig("smtp", r"220.*ESMTP Postfix", product="Postfix smtpd",
         cpe="cpe:2.3:a:postfix:postfix:*:*:*:*:*:*:*:*", confidence=0.95),
    _sig("smtp", r"220.*Exim ([\d.]+)", product="Exim smtpd", version=r"\1",
         cpe="cpe:2.3:a:exim:exim:{version}:*:*:*:*:*:*:*", confidence=0.96),
    _sig("smtp", r"220.*Sendmail ([\w./-]+)", product="Sendmail", version=r"\1",
         cpe="cpe:2.3:a:proofpoint:sendmail:{version}:*:*:*:*:*:*:*", confidence=0.94),
    _sig("smtp", r"220.*Microsoft ESMTP", product="Microsoft Exchange smtpd",
         confidence=0.9, os="Windows"),
    _sig("smtp", r"^220[ -].*SMTP", product=None, confidence=0.4),

    # --- POP3 / IMAP ---
    _sig("pop3", r"\+OK.*Dovecot", product="Dovecot pop3d",
         cpe="cpe:2.3:a:dovecot:dovecot:*:*:*:*:*:*:*:*", confidence=0.93),
    _sig("imap", r"\* OK.*Dovecot", product="Dovecot imapd",
         cpe="cpe:2.3:a:dovecot:dovecot:*:*:*:*:*:*:*:*", confidence=0.93),
    _sig("pop3", r"^\+OK", product=None, confidence=0.4),
    _sig("imap", r"^\* OK", product=None, confidence=0.4),

    # --- HTTP servers (matched against the Server header) ---
    _sig("http", r"^nginx(?:/([\d.]+))?", field="http_server",
         product="nginx", version=r"\1",
         cpe="cpe:2.3:a:nginx:nginx:{version}:*:*:*:*:*:*:*", confidence=0.95),
    _sig("http", r"^Apache(?:/([\d.]+))?", field="http_server",
         product="Apache httpd", version=r"\1",
         cpe="cpe:2.3:a:apache:http_server:{version}:*:*:*:*:*:*:*", confidence=0.95),
    _sig("http", r"^Microsoft-IIS/([\d.]+)", field="http_server",
         product="Microsoft IIS httpd", version=r"\1", os="Windows",
         cpe="cpe:2.3:a:microsoft:internet_information_services:{version}:*:*:*:*:*:*:*",
         confidence=0.95),
    _sig("http", r"^lighttpd(?:/([\d.]+))?", field="http_server",
         product="lighttpd", version=r"\1",
         cpe="cpe:2.3:a:lighttpd:lighttpd:{version}:*:*:*:*:*:*:*", confidence=0.93),
    _sig("http", r"^Caddy", field="http_server", product="Caddy httpd",
         confidence=0.9),
    _sig("http", r"^openresty(?:/([\d.]+))?", field="http_server",
         product="OpenResty", version=r"\1", confidence=0.9),
    _sig("http", r"^Werkzeug/([\d.]+)", field="http_server",
         product="Werkzeug httpd", version=r"\1", confidence=0.9),
    _sig("http", r"^gunicorn(?:/([\d.]+))?", field="http_server",
         product="gunicorn", version=r"\1", confidence=0.9),
    _sig("http", r"^Apache-Coyote", field="http_server",
         product="Apache Tomcat", confidence=0.85),
    _sig("http", r".+", field="http_server", product=r"\g<0>", confidence=0.5),

    # --- web framework hints from X-Powered-By ---
    _sig("http", r"^PHP/([\d.]+)", field="http_powered_by",
         product="PHP", version=r"\1",
         cpe="cpe:2.3:a:php:php:{version}:*:*:*:*:*:*:*", confidence=0.8),
    _sig("http", r"^Express", field="http_powered_by",
         product="Express", confidence=0.75),
    _sig("http", r"^ASP\.NET", field="http_powered_by",
         product="Microsoft ASP.NET", os="Windows", confidence=0.8),

    # --- datastores ---
    _sig("redis", r"redis_version:([\d.]+)", ports=(6379,),
         product="Redis", version=r"\1",
         cpe="cpe:2.3:a:redis:redis:{version}:*:*:*:*:*:*:*", confidence=0.95),
    # MySQL/MariaDB greeting (binary, version is ASCII): pin to port 3306.
    _sig("mysql", r"([0-9]+\.[0-9]+\.[0-9]+)-MariaDB", ports=(3306,),
         product="MariaDB", version=r"\1",
         cpe="cpe:2.3:a:mariadb:mariadb:{version}:*:*:*:*:*:*:*", confidence=0.9),
    _sig("mysql", r"\n([0-9]+\.[0-9]+\.[0-9]+[\w.-]*)", ports=(3306,), flags=0,
         product="MySQL", version=r"\1",
         cpe="cpe:2.3:a:oracle:mysql:{version}:*:*:*:*:*:*:*", confidence=0.85),
    _sig("mongodb", r"MongoDB", ports=(27017,), product="MongoDB",
         cpe="cpe:2.3:a:mongodb:mongodb:*:*:*:*:*:*:*:*", confidence=0.7),

    # --- Elasticsearch (JSON body from HTTP probe) ---
    _sig("elasticsearch", r'"number"\s*:\s*"([\d.]+)"', field="http_body",
         ports=(9200,), product="Elasticsearch", version=r"\1",
         cpe="cpe:2.3:a:elastic:elasticsearch:{version}:*:*:*:*:*:*:*", confidence=0.9),

    # --- Telnet ---
    _sig("telnet", r"^\xff[\xfb-\xfe]", flags=0, product=None,
         extra_info="telnet option negotiation", confidence=0.6),
]
