---
name: ledger-conventions
description: >
  Conventions and invariants for the Event Ledger service. Load when implementing,
  reviewing, or testing any part of the ledger so all three agents share one source
  of truth on the data model, idempotency rules, and money handling.
---

# Event Ledger — Conventions & Invariants

These are the rules every agent (design, dev, qa) must respect. They exist so
work handed off between agents stays consistent.

## Core invariants
- **Events are immutable.** Never UPDATE or DELETE an event row. Corrections are
  modeled as new compensating events, never edits.
- **Balance is derived, never stored.** `balance = sum(CREDIT) - sum(DEBIT)`,
  computed at read time from the event set.
- **`eventId` is the primary key.** Idempotency is enforced by the storage engine.
  A duplicate is a primary-key collision, caught as an IntegrityError.
- **Ordering is by `event_timestamp`**, applied at query time. Arrival order is
  never persisted as meaningful state.

## Two timestamps, kept distinct
- `event_timestamp` — business time, when the transaction occurred upstream. The
  basis for all ordering and the out-of-order story.
- `received_at` — server ingest time. Never used for ordering.

## HTTP status semantics
- `201` new event stored · `200` duplicate eventId (return original) ·
  `422` validation failure (field-level detail) · `404` unknown event id.

## Money handling
- Validate `amount > 0` at the edge.
- Round derived balances to 2 decimals for presentation; prefer integer minor units
  or Decimal end-to-end in any production hardening.

## Observability & audit
- Structured JSON logs, one object per line, with a per-request correlation id.
- Every state-changing decision writes an `audit_log` row.

## Testing
- One test file per requirement area. Isolated in-memory DB per test.
- A concurrency test must prove exactly one winner among simultaneous duplicate POSTs.
