#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

uv run uvicorn mocks.order_service.app:app --port 4001 --log-level warning &
uv run uvicorn mocks.billing_mock.app:app  --port 4002 --log-level warning &
uv run uvicorn mocks.erp_mock.app:app      --port 4003 --log-level warning &

echo "Order Service:  http://localhost:4001"
echo "Billing Mock:   http://localhost:4002"
echo "ERP Mock:       http://localhost:4003"
echo "Ctrl+C to stop all."

wait