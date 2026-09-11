# Demarc Constitution

This document is the set of rules that cannot be broken — by the generative coding
assistant or by any contributor. It is the first thing read in every working session,
before any task is picked up and before any code is written.

**Routing protocol.** Every prompt is handled in this order:

1. **This constitution.** Binding, never violated, never reinterpreted for convenience.
2. **`docs/tasks.md`.** Find the current task. Work proceeds task by task, in order.
3. **The spec and decision record behind the task.** Read the `docs/spec.md` sections and
   the `docs/decisions.md` entries the task references before touching code.
4. **Log before deviating.** Any decision, assumption, or discovered oversight is appended
   to `docs/decisions.md` — and reflected in spec.md / tasks.md — before work proceeds.

---

## 1. Product invariants

1. **Evidence artifacts are immutable and content-addressed.** Never update or delete —
   supersede: a corrected artifact is a new artifact with `superseded_by` set on the old
   one. `collected_at` (when the evidence was true) is distinct from `ingested_at` (when
   it arrived), and `collected_at` is the compliance-relevant date.

2. **No cardholder data, ever.** Luhn-validated PAN detection runs on every ingested
   file; matches are rejected with a specific message, not stored. The redaction pass on
   export is a second net, never the first.

3. **Rules are pure functions** over an injected `EvidenceGraph` snapshot with an
   injected clock (`ctx.now`). No I/O, no `datetime.now()`, no randomness. Every rule
   ships with fixture-based tests before it ships — a wrong rule tells someone they are
   compliant when they are not.

4. **The rules-pack version is stamped on every finding, verdict, and generated
   artifact.** A changed pack requires a version bump; re-running the same pack against
   the same evidence must yield byte-identical output. Reproducibility is the reason the
   engine is deterministic rather than an LLM.

5. **The UI never asserts compliance.** It reports what evidence exists, what is missing,
   and what a rule found. The QSA determines compliance. Compliance-asserting copy is
   gated in CI.

6. **The crawler container gets no database or storage credentials.** It renders
   untrusted third-party JavaScript on an egress-only network and returns results through
   the queue only.

7. **Tenant isolation is enforced by the database, not just the application.** Every
   org-scoped table carries `org_id`; never write a query that omits it. Every new
   data-plane table gets `ENABLE` + `FORCE ROW LEVEL SECURITY`, the tenant policy, and
   explicit grants, and must be registered in `DATA_PLANE_TABLES` so the isolation suite
   covers it. Auth-plane access (organizations, users, memberships, sessions) is confined
   to `demarc.services.auth`.

8. **The audit log is hash-chained and append-only**, enforced by grant in the database,
   not by convention. This tool's own output is evidence; its own integrity must be
   demonstrable.

## 2. Process rules

1. **Routing.** No work happens outside the routing protocol above. A task not in
   tasks.md is not worked until it is added — which itself requires a decisions.md entry.

2. **Risk-tiered TDD.** For the high-stakes surfaces — the rules engine, tenant
   isolation, evidence immutability, PAN detection, and the audit hash chain — the
   failing test is written **before** the implementation. Everywhere else, tests land in
   the same commit/PR as the code they cover.

3. **A gate must be proven to fail before it is trusted.** When adding any CI gate or
   test meant to block a class of defect, first confirm it fails against the broken
   state. A gate that cannot fail is worse than a missing one, because it reads as
   coverage.

4. **`docs/decisions.md` is append-only.** Entries are never edited or deleted; a wrong
   or outdated decision is superseded by a new entry that references it. Every decision
   that changes anything about the project — including silent-looking assumptions and
   oversights that force spec or task changes — gets an entry before or with the change.

5. **Changes to spec.md or tasks.md require a decisions.md entry** recording what changed
   and why.

6. **Migrations are generated, never hand-edited to match models.** Use
   `make revision M="…"`. `alembic check` gates the disagreement in CI.

7. **Dependency changes are a two-file operation.** After any `pyproject.toml` edit, run
   `make lock`; CI fails a PR that changes one without the other.

## 3. Agent governance

1. **Git discipline.** Never commit or push without an explicit user request. Never work
   directly on `main` — feature branches only.

2. **Verification before done.** A task is marked complete in tasks.md only when its
   acceptance criteria are met and the relevant gates (lint, typecheck, tests) have
   actually been run and pass. No "should work" completions; failures are reported as
   failures.

3. **No scope creep.** Work only the current task from tasks.md. Anything discovered en
   route — a bug, an improvement, an oversight — becomes a decisions.md entry and/or a
   new task, not an in-flight detour.

4. **Non-goals are binding.** Demarc is not an ASV scanner, not a pen-test tool, and not
   a compliance determination. It never stores cardholder data and does not remediate; it
   observes, compares, and reports.

## 4. Amendment

The assistant may **propose** an amendment to this constitution but never applies one on
its own initiative. An amendment happens only on explicit user approval, and every
amendment is logged in `docs/decisions.md`. Outside an approved amendment, this file is
read-only to the assistant.

---

*Sources: this document supersedes the "Rules that are not negotiable" list formerly in
CLAUDE.md and the rule content of PLAN.md §4, §7, §8, §12 and ADRs 0001–0002, whose
history is preserved in `docs/decisions.md`.*
