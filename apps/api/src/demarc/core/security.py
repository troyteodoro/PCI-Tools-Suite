"""Password hashing, opaque session tokens, and canonical hashing.

The canonical-hash helper here is deliberately shared by the audit chain and (later) the
evidence manifest: both need a byte-stable serialization that can be re-derived years
after the fact.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# OWASP-recommended baseline (2024): 19 MiB, 2 iterations, 1 degree of parallelism.
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)

TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def generate_session_token() -> str:
    """Opaque bearer token. Only its digest is ever stored."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def canonical_json(payload: Any) -> bytes:
    """Byte-stable JSON: sorted keys, no insignificant whitespace, UTF-8.

    Stability matters more than prettiness — this is what gets hashed.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
