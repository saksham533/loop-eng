import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mocks.common.db import get_conn, init_schema, log
from mocks.order_service.idempotency import load_strategy

ORDER_DDL = """
CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY,
  customer_id TEXT,
  amount REAL,
  status TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS payment_attempts (
  idempotency_key TEXT PRIMARY KEY,
  order_id TEXT,
  payment_id TEXT,
  amount REAL,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS crashes (
  order_id TEXT PRIMARY KEY,
  crashed_at TEXT
);
CREATE TABLE IF NOT EXISTS logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  level TEXT,
  message TEXT,
  created_at TEXT
);
"""

app = FastAPI(title="Order Service")
init_schema("order", ORDER_DDL)

ERP_URL = os.getenv("ERP_URL", "http://localhost:4003")
SIMULATE_FIRST_CRASH = os.getenv("SIMULATE_FIRST_CRASH", "true").lower() == "true"


class WebhookPayload(BaseModel):
    idempotency_key: str
    order_id: str
    payment_id: str
    amount: float


@app.get("/health")
def health():
    return {"status": "ok", "service": "order-service"}


@app.get("/state")
def state():
    conn = get_conn("order")
    orders = [dict(r) for r in conn.execute("SELECT * FROM orders").fetchall()]
    conn.close()
    return {"orders": orders}


@app.get("/logs")
def logs(limit: int = 50):
    conn = get_conn("order")
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()]
    conn.close()
    return {"logs": rows}


@app.post("/reset")
def reset():
    conn = get_conn("order")
    conn.executescript("DELETE FROM orders; DELETE FROM payment_attempts; DELETE FROM crashes; DELETE FROM logs;")
    conn.close()
    return {"reset": True}


@app.post("/webhook")
def receive_webhook(payload: WebhookPayload):
    conn = get_conn("order")
    try:
        attempt = conn.execute(
            "SELECT * FROM payment_attempts WHERE idempotency_key = ?",
            (payload.idempotency_key,),
        ).fetchone()
        order = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (payload.order_id,)
        ).fetchone()

        strategy = load_strategy()
        decision = strategy.should_process(payload.idempotency_key, attempt, order)
        log(conn, "INFO", f"decision={decision.value} key={payload.idempotency_key}")

        if decision.value == "PROCESS_NEW":
            conn.execute(
                "INSERT INTO payment_attempts (idempotency_key, order_id, payment_id, amount, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (payload.idempotency_key, payload.order_id, payload.payment_id, payload.amount),
            )
            already_crashed = conn.execute(
                "SELECT 1 FROM crashes WHERE order_id = ?", (payload.order_id,)
            ).fetchone()
            if SIMULATE_FIRST_CRASH and not already_crashed:
                conn.execute(
                    "INSERT INTO crashes (order_id, crashed_at) VALUES (?, datetime('now'))",
                    (payload.order_id,),
                )
                log(conn, "ERROR", "Transient crash before status commit")
                raise HTTPException(500, "Transient failure during order processing")

            conn.execute("UPDATE orders SET status='PAID', updated_at=datetime('now') WHERE order_id=?",
                         (payload.order_id,))
            _trigger_erp(payload.order_id, payload.payment_id)
            log(conn, "INFO", "Order advanced to PAID, ERP triggered")
            return {"status": "processed", "decision": decision.value}

        if decision.value == "SKIP_AS_DUPLICATE":
            log(conn, "INFO", "Duplicate detected, skipping silently")
            return {"status": "duplicate_skipped", "decision": decision.value}

        if decision.value == "RECOVER_PARTIAL":
            log(conn, "INFO", "Partial commit detected, recovering")
            conn.execute("UPDATE orders SET status='PAID', updated_at=datetime('now') WHERE order_id=?",
                         (payload.order_id,))
            _trigger_erp(payload.order_id, payload.payment_id)
            return {"status": "recovered", "decision": decision.value}

    finally:
        conn.close()


def _trigger_erp(order_id: str, payment_id: str) -> None:
    try:
        httpx.post(f"{ERP_URL}/fulfillment/trigger",
                   json={"order_id": order_id, "payment_id": payment_id},
                   timeout=3.0)
    except Exception:
        pass
    