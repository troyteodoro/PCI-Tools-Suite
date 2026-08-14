"""The audit chain is evidence about evidence. These tests pin its behaviour.

No database required — `compute_entry_hash` is pure, which is the point: a chain exported
to a file must be verifiable years later without this application running.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from demarc.db.models.audit import GENESIS_HASH
from demarc.services.audit import compute_entry_hash

ORG = uuid.UUID("11111111-1111-1111-1111-111111111111")
AT = datetime(2026, 8, 13, 6, 0, tzinfo=UTC)


def entry(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "org_id": ORG,
        "seq": 1,
        "at": AT,
        "actor_user_id": None,
        "actor_label": "engineer@northgate.example",
        "action": "auth.login_succeeded",
        "target_type": None,
        "target_id": None,
        "detail": {},
        "source_ip": "203.0.113.7",
        "prev_hash": GENESIS_HASH,
    }
    return base | overrides


def test_hash_is_deterministic() -> None:
    assert compute_entry_hash(**entry()) == compute_entry_hash(**entry())  # type: ignore[arg-type]


def test_hash_is_64_hex_characters() -> None:
    value = compute_entry_hash(**entry())  # type: ignore[arg-type]
    assert len(value) == 64
    assert set(value) <= set("0123456789abcdef")


@pytest.mark.parametrize(
    "field,value",
    [
        ("seq", 2),
        ("actor_label", "someone.else@northgate.example"),
        ("action", "auth.login_failed"),
        ("target_id", "tampered"),
        ("detail", {"reason": "invalid_credentials"}),
        ("source_ip", "198.51.100.1"),
        ("prev_hash", "f" * 64),
    ],
)
def test_any_field_change_changes_the_hash(field: str, value: object) -> None:
    """If a field could be altered without changing the hash, it is not protected."""
    assert compute_entry_hash(**entry()) != compute_entry_hash(**entry(**{field: value}))  # type: ignore[arg-type]


def test_timestamp_is_covered_and_normalized_to_utc() -> None:
    """Backdating an entry must break its hash, but an equivalent instant must not."""
    shifted = compute_entry_hash(**entry(at=AT + timedelta(seconds=1)))  # type: ignore[arg-type]
    assert compute_entry_hash(**entry()) != shifted

    other_zone = AT.astimezone(tz=None).astimezone(UTC)
    assert compute_entry_hash(**entry(at=other_zone)) == compute_entry_hash(**entry())  # type: ignore[arg-type]


def test_detail_key_order_does_not_affect_the_hash() -> None:
    """Canonical JSON sorts keys, so re-serialization by any client agrees."""
    a = compute_entry_hash(**entry(detail={"alpha": 1, "beta": 2}))  # type: ignore[arg-type]
    b = compute_entry_hash(**entry(detail={"beta": 2, "alpha": 1}))  # type: ignore[arg-type]
    assert a == b


def test_chain_links_forward() -> None:
    """A three-entry chain: each entry commits to its predecessor's hash."""
    first = compute_entry_hash(**entry(seq=1, prev_hash=GENESIS_HASH))  # type: ignore[arg-type]
    second = compute_entry_hash(**entry(seq=2, prev_hash=first))  # type: ignore[arg-type]
    third = compute_entry_hash(**entry(seq=3, prev_hash=second))  # type: ignore[arg-type]

    assert len({first, second, third}) == 3

    # Rewriting entry one invalidates everything downstream, which is the property that
    # makes the log worth keeping.
    tampered_first = compute_entry_hash(**entry(seq=1, actor_label="mallory@example.com"))  # type: ignore[arg-type]
    assert compute_entry_hash(**entry(seq=2, prev_hash=tampered_first)) != second  # type: ignore[arg-type]


def test_organizations_produce_independent_chains() -> None:
    other_org = uuid.UUID("22222222-2222-2222-2222-222222222222")
    assert compute_entry_hash(**entry()) != compute_entry_hash(**entry(org_id=other_org))  # type: ignore[arg-type]
