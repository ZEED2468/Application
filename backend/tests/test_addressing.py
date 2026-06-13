"""Tagged reply-address round-trip + signature tamper rejection."""

from app.core.ids import new_id
from app.email.addressing import decode_reply_address, encode_reply_address


def test_roundtrip():
    job_id = new_id()
    addr = encode_reply_address(job_id, "hunter-backend.example.com")
    assert addr.startswith("apply+")
    assert decode_reply_address(addr) == job_id


def test_tampered_signature_rejected():
    job_id = new_id()
    addr = encode_reply_address(job_id, "d.example.com")
    local, domain = addr.split("@")
    tampered = local[:-2] + "xx" + "@" + domain
    assert decode_reply_address(tampered) is None


def test_plain_address_returns_none():
    assert decode_reply_address("hello@example.com") is None
