"""Deterministic, time-ordered IDs (Crockford-style ULID)."""
import secrets
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32 (no I,L,O,U)


def _b32(n: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_ALPHABET[n & 0x1F])
        n >>= 5
    return "".join(reversed(out))


def new_id() -> str:
    ts = int(time.time() * 1000)
    rand = secrets.randbits(80)
    return _b32(ts, 10) + _b32(rand, 16)


def now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
