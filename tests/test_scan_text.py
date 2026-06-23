"""Regression tests for binary protocol banner sanitization."""
from app.fingerprint import Observation, default_engine
from app.scan.text import decode_banner, sanitize_json, sanitize_text


def test_mysql_binary_handshake_is_safe_and_still_fingerprints():
    raw = (
        b"N\x00\x00\x00\n5.7.35-log\x00\xffM\x02\x00\x10"
        b"binary-data\x00mysql_native_password\x00"
    )

    banner = decode_banner(raw)
    assert banner is not None
    assert "\x00" not in banner
    assert "\\x00" in banner

    fingerprint = default_engine.identify(Observation(port=3306, banner=banner))
    assert fingerprint.product == "MySQL"
    assert fingerprint.version == "5.7.35-log"


def test_text_and_json_sanitizers_escape_nested_control_bytes():
    assert sanitize_text("hello\x00world\x01\n") == "hello\\x00world\\x01\n"
    assert sanitize_json({"banner": "a\x00b", "nested": ["c\x02d"]}) == {
        "banner": "a\\x00b",
        "nested": ["c\\x02d"],
    }
