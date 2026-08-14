"""Operational commands.

    python -m demarc.cli seed          # demo organization for local development
    python -m demarc.cli verify-chain  # re-derive the audit chain for every org
    python -m demarc.cli status        # deployment state
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from demarc.core.config import get_settings
from demarc.core.logging import configure_logging, get_logger
from demarc.db.models.audit import AuditAction
from demarc.db.models.organization import MerchantLevel, Organization, SAQType
from demarc.db.session import auth_session, dispose_engine, org_session
from demarc.services import audit as audit_service
from demarc.services import auth as auth_service

log = get_logger(__name__)

# Mirrors the UI mockup's fictional tenant so local screens have plausible data.
DEMO_ORG_NAME = "Northgate Retail"
DEMO_OWNER_EMAIL = "engineer@northgate.example"
DEMO_OWNER_NAME = "Sam Okafor"
DEMO_PASSWORD = "demarc-local-dev-2026"  # noqa: S105 - local seed only, never shipped


async def _seed() -> int:
    settings = get_settings()
    if settings.is_production:
        print("Refusing to seed a production deployment.", file=sys.stderr)
        return 1

    async with auth_session() as session:
        if await auth_service.deployment_is_bootstrapped(session):
            org = await auth_service.get_org_by_slug(session, settings.single_tenant_org_slug)
            name = org.name if org else "?"
            print(f"Already seeded — organization {name} exists. Nothing to do.")
            return 0

        org, user = await auth_service.bootstrap_deployment(
            session,
            settings=settings,
            org_name=DEMO_ORG_NAME,
            org_slug=settings.single_tenant_org_slug,
            email=DEMO_OWNER_EMAIL,
            full_name=DEMO_OWNER_NAME,
            password=DEMO_PASSWORD,
            merchant_level=MerchantLevel.LEVEL_1,
            saq_type=SAQType.D_MERCHANT,
        )
        org_id, user_id = org.id, user.id

    async with org_session(org_id) as session:
        await audit_service.record(
            session,
            org_id=org_id,
            action=AuditAction.DEPLOYMENT_BOOTSTRAPPED,
            actor_user_id=user_id,
            actor_label=DEMO_OWNER_EMAIL,
            target_type="organization",
            target_id=str(org_id),
            detail={"seeded": True, "org_name": DEMO_ORG_NAME},
        )

    print(
        "Seeded local deployment.\n"
        f"  organization : {DEMO_ORG_NAME}\n"
        f"  sign in as   : {DEMO_OWNER_EMAIL}\n"
        f"  password     : {DEMO_PASSWORD}\n"
        "\nLocal development credentials. They are refused in production."
    )
    return 0


async def _verify_chain() -> int:
    async with auth_session() as session:
        org_ids = [
            (row.id, row.name)
            for row in (await session.execute(select(Organization))).scalars().all()
        ]

    if not org_ids:
        print("No organizations.")
        return 0

    exit_code = 0
    for org_id, name in org_ids:
        async with org_session(org_id) as session:
            result = await audit_service.verify_chain(session, org_id=org_id)
        marker = "ok  " if result.ok else "FAIL"
        print(f"[{marker}] {name}: {result.summary}")
        if not result.ok:
            exit_code = 1
    return exit_code


async def _status() -> int:
    settings = get_settings()
    async with auth_session() as session:
        bootstrapped = await auth_service.deployment_is_bootstrapped(session)
        orgs = (await session.execute(select(Organization))).scalars().all()

    print(f"environment     : {settings.environment.value}")
    print(f"deployment mode : {settings.deployment_mode.value}")
    print(f"bootstrapped    : {bootstrapped}")
    print(f"organizations   : {len(orgs)}")
    for org in orgs:
        print(f"  - {org.slug}: {org.name} ({org.saq_type.value})")
    return 0


COMMANDS = {"seed": _seed, "verify-chain": _verify_chain, "status": _status}


def main() -> int:
    parser = argparse.ArgumentParser(prog="demarc", description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args()

    configure_logging(get_settings())

    async def run() -> int:
        try:
            return await COMMANDS[args.command]()
        finally:
            await dispose_engine()

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
