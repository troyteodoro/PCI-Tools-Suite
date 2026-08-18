"""Which service is handed which credential is part of the security boundary.

Two rules from CLAUDE.md and PLAN.md §8/§9 are expressed in the compose files rather than
in code, so they are tested by parsing the compose files:

1. The crawl worker renders untrusted third-party JavaScript. It returns results through
   the queue and holds no database or object-storage credentials. The service arrives in
   M2; the rule is asserted now so it cannot arrive wrong.
2. Only the one-shot `migrate` job gets the owner/migration credential. A long-running
   service holding it would make the least-privilege split in docs/adr/0001 decorative.

Offline: parses YAML, starts nothing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

COMPOSE_FILES = [
    REPO_ROOT / "docker-compose.yml",
    REPO_ROOT / "compose.override.yml",
    REPO_ROOT / "compose.prod.yml",
    REPO_ROOT / "compose.ci.yml",
]

# Anything that grants reach into the database or the evidence store.
DATA_CREDENTIAL = re.compile(
    r"DATABASE_URL|POSTGRES_PASSWORD|POSTGRES_USER|S3_ACCESS_KEY|S3_SECRET|SECRET_KEY",
    re.IGNORECASE,
)

MIGRATION_CREDENTIAL = "DEMARC_MIGRATION_DATABASE_URL"


class _TolerantLoader(yaml.SafeLoader):
    """Compose's merge-suppressing `!reset` tag is not standard YAML."""


def _ignore_unknown_tag(loader: yaml.Loader, suffix: str, node: yaml.Node) -> None:
    return None


_TolerantLoader.add_multi_constructor("!", _ignore_unknown_tag)


def _services(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    # S506: _TolerantLoader derives from yaml.SafeLoader and only adds a constructor that
    # discards unknown `!` tags, so no arbitrary object can be instantiated. ruff matches
    # on the yaml.load call rather than the loader's base class.
    parsed = yaml.load(path.read_text(), Loader=_TolerantLoader) or {}  # noqa: S506
    return parsed.get("services") or {}


def _env_keys(service: dict[str, Any]) -> set[str]:
    """Compose accepts both mapping and `KEY=value` list forms."""
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return set(env)
    return {str(item).split("=", 1)[0] for item in env}


def _secret_names(service: dict[str, Any]) -> set[str]:
    names = set()
    for secret in service.get("secrets") or []:
        names.add(secret if isinstance(secret, str) else str(secret.get("source", "")))
    return names


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=lambda p: p.name)
def test_crawl_services_get_no_data_credentials(path: Path) -> None:
    """PLAN.md §8: the crawler container gets no database or storage credentials."""
    for name, service in _services(path).items():
        if "crawl" not in name:
            continue
        exposed = {k for k in _env_keys(service) if DATA_CREDENTIAL.search(k)}
        exposed |= {s for s in _secret_names(service) if DATA_CREDENTIAL.search(s)}
        assert not exposed, (
            f"{name} in {path.name} is handed {sorted(exposed)}. It renders untrusted "
            "third-party JavaScript; results come back through the queue only."
        )


@pytest.mark.parametrize("path", COMPOSE_FILES, ids=lambda p: p.name)
def test_only_the_migrate_job_holds_the_owner_credential(path: Path) -> None:
    """The owner role bypasses nothing (RLS is FORCEd) but it can still alter the schema.
    Only the one-shot migration job needs it."""
    for name, service in _services(path).items():
        if name == "migrate":
            continue
        holders = {k for k in _env_keys(service) if MIGRATION_CREDENTIAL in k}
        assert not holders, (
            f"{name} in {path.name} holds {MIGRATION_CREDENTIAL}. Only the one-shot "
            "`migrate` service may; a long-running service with it defeats the "
            "least-privilege split in docs/adr/0001."
        )


def test_the_compose_files_under_test_actually_exist() -> None:
    """Keeps the parametrized tests above from passing vacuously if a file is renamed."""
    missing = [p.name for p in COMPOSE_FILES if not p.exists()]
    assert not missing, f"compose files not found: {missing} (looked under {REPO_ROOT})"
