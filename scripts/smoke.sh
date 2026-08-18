#!/usr/bin/env bash
#
# End-to-end assertions against a running stack.
#
#   scripts/smoke.sh                 # against the local dev stack (make dev)
#   COMPOSE_FILES="-f docker-compose.yml -f compose.ci.yml" scripts/smoke.sh
#
# This covers what the offline unit suite cannot: the built images, the init SQL, the
# two-role split, forced RLS in a live database, container ordering, and the operational
# CLI the Makefile exposes. It is the only test of the deployment shape itself.
#
# Every check is an assertion with a message explaining what its failure would mean.

set -euo pipefail

COMPOSE_FILES=${COMPOSE_FILES:-}
# shellcheck disable=SC2086
dc() { docker compose $COMPOSE_FILES "$@"; }

# psql as POSTGRES_USER — the schema owner, and a superuser, so it is used only to read
# the catalog. Behavioural isolation checks go through app() below.
pg() { dc exec -T postgres psql -Atq -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-demarc}" -d "${POSTGRES_DB:-demarc}" "$@"; }
# psql as the least-privileged runtime role.
app() { dc exec -T postgres psql -Atq -U demarc_app -d "${POSTGRES_DB:-demarc}" "$@"; }

fail() { echo "::error::$*" >&2; exit 1; }
ok()   { echo "  ok  $*"; }

# ── the one-shot jobs completed ────────────────────────────────────────────────────
exit_code_of() {
  dc ps -a --format '{{.Service}} {{.ExitCode}}' | awk -v s="$1" '$1==s {print $2; found=1} END {if (!found) print "missing"}'
}

for job in migrate minio-init; do
  code=$(exit_code_of "$job")
  [ "$code" = "0" ] || fail "the $job one-shot exited $code; nothing downstream should have started"
  ok "$job exited 0"
done

# ── readiness actually reaches its dependencies ────────────────────────────────────
ready=$(dc exec -T api curl -fsS http://localhost:8000/readyz)
echo "$ready" | grep -q '"status":"ready"' || fail "/readyz did not report ready: $ready"
echo "$ready" | grep -q '"database":"ok"' || fail "/readyz reported ready without a database check: $ready"
ok "/readyz reports ready with a live database check"

# ── the image runs as the non-root user it claims ──────────────────────────────────
uid=$(dc exec -T api id -u | tr -d '\r')
[ "$uid" = "10001" ] || fail "the api container runs as uid $uid, not the non-root 10001"
ok "api runs as uid 10001"

# ── the evidence bucket exists and is versioned ────────────────────────────────────
# Evidence artifacts are immutable and content-addressed; versioning is what makes an
# accidental overwrite recoverable rather than silent.
bucket=${DEMARC_S3_BUCKET:-demarc-evidence}
versioning=$(dc run --rm --no-deps --entrypoint sh minio-init -c "
  mc alias set local http://minio:9000 '${DEMARC_S3_ACCESS_KEY_ID:-demarc}' '${DEMARC_S3_SECRET_ACCESS_KEY:-demarc-dev-secret}' >/dev/null &&
  mc version info local/$bucket" 2>&1 | tr -d '\r')
echo "$versioning" | grep -qi "enabled" || fail "versioning is not enabled on $bucket: $versioning"
ok "evidence bucket $bucket exists with versioning enabled"

# ── RLS is enabled, forced, and effective ──────────────────────────────────────────
dc exec -T api python -m demarc.cli seed >/dev/null
ok "seeded"

seeded_orgs=$(pg -c 'SELECT count(*) FROM organizations')
[ "$seeded_orgs" -ge 1 ] || fail "seeding reported success but organizations is empty"

# Assert the catalog flags directly. Note that the *behavioural* probe below runs as
# demarc_app, not as the owner: POSTGRES_USER is created a superuser by the postgres
# entrypoint, and a superuser bypasses RLS unconditionally whether FORCE is set or not.
# An owner-connection count would therefore prove nothing here — and on an empty table
# it would pass vacuously, which is worse than not checking.
flags=$(pg -c "SELECT relrowsecurity || ',' || relforcerowsecurity FROM pg_class WHERE relname = 'audit_log'")
[ "$flags" = "true,true" ] || fail \
  "audit_log has (relrowsecurity,relforcerowsecurity) = ($flags); both must be true — ENABLE without FORCE leaves the owner reading every tenant's rows"
ok "audit_log has RLS enabled and forced"

# The runtime role is a plain role: no superuser, no BYPASSRLS. If either creeps in, RLS
# becomes decorative no matter how the policies are written.
attrs=$(pg -c "SELECT rolsuper || ',' || rolbypassrls FROM pg_roles WHERE rolname = 'demarc_app'")
[ "$attrs" = "false,false" ] || fail \
  "demarc_app has (rolsuper,rolbypassrls) = ($attrs); a runtime role with either attribute bypasses every policy"
ok "demarc_app is neither superuser nor BYPASSRLS"

# With no tenant context, the runtime role sees nothing — and does not error. There is at
# least one audit entry at this point, so this cannot pass vacuously.
no_context=$(app -c 'SELECT count(*) FROM audit_log')
[ "$no_context" = "0" ] || fail \
  "demarc_app sees $no_context audit_log rows with no tenant context set; the policy is not isolating"
ok "demarc_app sees no audit_log rows without a tenant context"

# With a context set, the same role sees that org's chain.
in_context=$(app -c "
  SELECT set_config('demarc.org_id', (SELECT id::text FROM organizations LIMIT 1), false);
  SELECT count(*) FROM audit_log" | tail -1)
[ "$in_context" -ge 1 ] || fail "no audit_log rows visible even with a tenant context set; the chain is unreachable"
ok "audit_log is reachable under a tenant context ($in_context entries)"

# ── the audit log is append-only by grant, not by convention ───────────────────────
if app -v ON_ERROR_STOP=1 -c 'DELETE FROM audit_log' >/dev/null 2>&1; then
  fail "demarc_app can DELETE from audit_log; the hash chain is rewritable"
fi
ok "demarc_app holds no DELETE on audit_log"

# ── the operational CLI the Makefile exposes ───────────────────────────────────────
dc exec -T api python -m demarc.cli seed | grep -q 'Already seeded' \
  || fail "seed is not idempotent; running it twice should be a no-op"
ok "seed is idempotent"

dc exec -T api python -m demarc.cli status | grep -qE '^bootstrapped    : True' \
  || fail "status does not report the deployment as bootstrapped after seeding"
ok "status reports a bootstrapped deployment"

dc exec -T api python -m demarc.cli verify-chain | grep -q '^\[ok' \
  || fail "verify-chain could not re-derive the audit chain"
ok "verify-chain re-derives the audit chain"

echo
echo "smoke: all checks passed"
