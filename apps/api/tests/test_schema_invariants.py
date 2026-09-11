"""Guards on the tenant-isolation boundary (decisions.md D-0004).

The failure these prevent: someone adds a table holding compliance data, forgets the RLS
policy, and the only thing standing between tenants becomes a `WHERE` clause. CI catches
the drift instead of a customer catching it.
"""

from __future__ import annotations

import ast
from pathlib import Path

from demarc.db.models import DATA_PLANE_TABLES, Base

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0001_initial_identity_and_audit.py"
)


def _migration_constant(name: str) -> tuple[str, ...]:
    """Read a module-level tuple out of the migration without importing it.

    Parsing rather than executing keeps this test free of an Alembic dependency and
    avoids running migration code as a side effect of collection.
    """
    tree = ast.parse(MIGRATION.read_text())
    for node in tree.body:
        targets = [node.target] if isinstance(node, ast.AnnAssign) else getattr(node, "targets", [])
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                assert node.value is not None
                return tuple(ast.literal_eval(node.value))
    raise AssertionError(f"{name} not found in {MIGRATION.name}")


def test_migration_and_model_registry_agree_on_the_data_plane() -> None:
    assert set(_migration_constant("DATA_PLANE_TABLES")) == set(DATA_PLANE_TABLES), (
        "DATA_PLANE_TABLES in demarc.db.models and in the migration have diverged. "
        "A table listed in one but not the other is either unprotected or unreachable."
    )


def test_every_table_is_assigned_to_exactly_one_plane() -> None:
    data_plane = set(_migration_constant("DATA_PLANE_TABLES"))
    auth_plane = set(_migration_constant("AUTH_PLANE_TABLES"))
    declared = data_plane | auth_plane
    actual = set(Base.metadata.tables) - {"alembic_version"}

    unassigned = actual - declared
    assert not unassigned, (
        f"Tables not assigned to a plane: {sorted(unassigned)}. "
        "Add each to DATA_PLANE_TABLES (compliance data, gets RLS) or AUTH_PLANE_TABLES."
    )

    overlap = data_plane & auth_plane
    assert not overlap, f"Tables in both planes: {sorted(overlap)}"


def test_every_data_plane_table_carries_org_id() -> None:
    """RLS keys on `org_id`. A data-plane table without it cannot be isolated."""
    for name in DATA_PLANE_TABLES:
        table = Base.metadata.tables[name]
        assert "org_id" in table.columns, f"{name} is on the data plane but has no org_id column"
        assert not table.columns["org_id"].nullable, f"{name}.org_id must be NOT NULL"


def test_audit_log_has_no_updated_at() -> None:
    """Append-only rows have no update path, so an `updated_at` would be a lie."""
    assert "updated_at" not in Base.metadata.tables["audit_log"].columns
