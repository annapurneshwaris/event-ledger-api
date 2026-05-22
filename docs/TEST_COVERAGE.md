# Test Coverage Report

Generated with `pytest --cov=app`. An HTML version is produced at
`htmlcov/index.html` via `pytest --cov=app --cov-report=html`.

## Summary

**25 tests, all passing. 97% line coverage.**

| Module | Statements | Missed | Coverage |
|---|---|---|---|
| `app/__init__.py` | 0 | 0 | 100% |
| `app/config.py` | 11 | 0 | 100% |
| `app/database.py` | 38 | 4 | 89% |
| `app/logging_config.py` | 23 | 1 | 96% |
| `app/main.py` | 57 | 2 | 96% |
| `app/schemas.py` | 47 | 0 | 100% |
| `app/service.py` | 52 | 0 | 100% |
| **TOTAL** | **228** | **7** | **97%** |

The service layer (all business logic — idempotency, balance, ordering, audit) is
at 100%. The few uncovered lines are framework glue: the `get_db` generator's
cleanup branch and a couple of defensive paths.

## Requirement → test mapping

The suite is organized so each spec requirement maps to a dedicated file.

### 1. Idempotency — `test_idempotency.py`
- `test_first_submission_returns_201` — first submission creates the event.
- `test_duplicate_submission_returns_200_and_original` — re-submitting the same
  `eventId` (even with different field values) returns the original with `200`.
- `test_duplicate_does_not_create_second_row` — three submissions, one stored row.
- `test_duplicate_does_not_alter_balance` — balance unaffected by duplicates.

### 2. Out-of-order tolerance — `test_out_of_order.py`
- `test_listing_is_chronological_regardless_of_arrival_order` — events submitted
  c→a→b list back a→b→c.
- `test_late_arriving_earlier_event_sorts_first` — a late event with an earlier
  timestamp sorts first.
- `test_balance_correct_regardless_of_order` — balance correct under shuffled arrival.

### 3. Balance computation — `test_balance.py`
- empty account is zero; credits minus debits; can go negative; isolated per
  account; rounds to two decimals (no float artifacts).

### 4. Validation & errors — `test_validation.py`
- missing required field; zero/negative amounts (parametrized); unknown type;
  blank account id; unexpected extra field; invalid timestamp; `404` on unknown
  event; field-level error details.

### Bonus — `test_concurrency_and_pagination.py`
- `test_concurrent_duplicate_posts_create_single_event` — 12 concurrent threads
  POST the same `eventId`; exactly one `201`, one stored row, correct balance.
- `test_pagination_returns_pages` — 25 events paginate correctly.
- `test_pagination_preserves_chronological_order` — pagination keeps chronological order.

## How to reproduce

```bash
pip install -r requirements-dev.txt
pytest --cov=app --cov-report=term-missing --cov-report=html
# open htmlcov/index.html
```
