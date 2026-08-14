"""Role semantics.

The auditor role is the one worth testing carefully: it must be able to read everything
an engineer can, and write nothing. Handing a QSA a login that can alter evidence would
undermine the evidence.
"""

from __future__ import annotations

import pytest

from demarc.db.models.user import Role


def test_rank_ordering() -> None:
    assert Role.VIEWER.rank < Role.AUDITOR.rank < Role.ENGINEER.rank < Role.OWNER.rank


@pytest.mark.parametrize("role", list(Role))
def test_every_role_satisfies_itself(role: Role) -> None:
    assert role.at_least(role)


def test_owner_satisfies_every_requirement() -> None:
    assert all(Role.OWNER.at_least(role) for role in Role)


def test_viewer_satisfies_only_viewer() -> None:
    assert Role.VIEWER.at_least(Role.VIEWER)
    assert not Role.VIEWER.at_least(Role.AUDITOR)
    assert not Role.VIEWER.at_least(Role.ENGINEER)


def test_read_only_roles() -> None:
    assert Role.AUDITOR.is_read_only
    assert Role.VIEWER.is_read_only
    assert not Role.ENGINEER.is_read_only
    assert not Role.OWNER.is_read_only


def test_auditor_outranks_viewer_but_still_cannot_write() -> None:
    """Rank and writability are independent axes, deliberately."""
    assert Role.AUDITOR.at_least(Role.VIEWER)
    assert Role.AUDITOR.is_read_only
