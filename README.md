# PulseCheck Mocks

Three FastAPI + SQLite services that reproduce the PCHK-0001 saga failure.

## Boot
​```bash
uv sync
bash scripts/start_all.sh
​```

## Reproduce the incident
​```bash
uv run python scripts/seed_pchk_0001.py --reset
​```
You'll see: Billing: PAID · Order: PENDING · ERP: empty

## Apply the fix
​```bash
IDEMPOTENCY_STRATEGY=commit_check bash scripts/start_all.sh
uv run python scripts/seed_pchk_0001.py --reset
​```
Now all three agree: PAID / PAID / TRIGGERED.

## Test
​```bash
uv run pytest -v
​```