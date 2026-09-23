import asyncio
import os
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel

from mocks.common.db import get_conn, init_schema, log

BILLING_DDL = """
CREATE TABLE IF NOT EXISTS payments (
  payment_id TEXT PRIMARY KEY,
  order_id TEXT,
  amount REAL,
  status TEXT,
  idempotency_key TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS webhook_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payment_id TEXT,
  idempotency_key TEXT,
  payload TEXT,
  attempts INTEGER DEFAULT 0,
  status TEXT DEFAULT 'pending',
  next_attempt_at TEXT
);
CREATE TABLE IF NOT EXISTS logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  level TEXT,
  message TEXT,
  created_at TEXT
);
"""

app = FastAPI(title="Billing Provider")
init_schema("billing", BILLING_DDL)

ORDER_URL = os.getenv("ORDER_URL", "http://localhost:4001")
MAX_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 2


class CaptureRequest(BaseModel):
    order_id: str
    amount: float
    idempotency_key: str
    payment_id: str = ""


@app.get("/health")
def health():
    return {"status": "ok", "service": "billing-mock"}


@app.get("/state")
def state():
    conn = get_conn("billing")
    payments = [dict(r) for r in conn.execute("SELECT * FROM payments").fetchall()]
    conn.close()
    return {"payments": payments}


@app.get("/logs")
def logs(limit: int = 50):
    conn = get_conn("billing")
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()]
    conn.close()
    return {"logs": rows}


@app.post("/reset")
def reset():
    conn = get_conn("billing")
    conn.executescript("DELETE FROM payments; DELETE FROM webhook_queue; DELETE FROM logs;")
    conn.close()
    return {"reset": True}


@app.post("/payments/capture")
def capture(req: CaptureRequest):
    conn = get_conn("billing")
    payment_id = req.payment_id or f"PAY-{req.order_id}"
    conn.execute(
        "INSERT OR REPLACE INTO payments (payment_id, order_id, amount, status, idempotency_key, updated_at) "
        "VALUES (?, ?, ?, 'PAID', ?, datetime('now'))",
        (payment_id, req.order_id, req.amount, req.idempotency_key),
    )
    payload = (
        '{"idempotency_key":"%s","order_id":"%s","payment_id":"%s","amount":%s}'
        % (req.idempotency_key, req.order_id, payment_id, req.amount)
    )
    conn.execute(
        "INSERT INTO webhook_queue (payment_id, idempotency_key, payload, status) "
        "VALUES (?, ?, ?, 'pending')",
        (payment_id, req.idempotency_key, payload),
    )
    log(conn, "INFO", f"Captured {payment_id}, webhook queued")
    conn.close()
    return {"payment_id": payment_id, "status": "PAID"}


async def _webhook_worker():
    while True:
        try:
            conn = get_conn("billing")
            rows = conn.execute(
                "SELECT * FROM webhook_queue WHERE status='pending'"
            ).fetchall()
            for row in rows:
                import json as _json
                payload = _json.loads(row["payload"])
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        r = await client.post(f"{ORDER_URL}/webhook", json=payload)
                    if r.status_code == 200:
                        conn.execute("UPDATE webhook_queue SET status='delivered' WHERE id=?",
                                     (row["id"],))
                        log(conn, "INFO", f"Webhook delivered for {row['payment_id']} (attempt {row['attempts']+1})")
                    else:
                        _schedule_retry(conn, row, r.status_code)
                except Exception as e:
                    _schedule_retry(conn, row, str(e))
            conn.close()
        except Exception:
            pass
        await asyncio.sleep(RETRY_DELAY_SECONDS)


def _schedule_retry(conn, row, reason):
    attempts = row["attempts"] + 1
    if attempts >= MAX_ATTEMPTS:
        conn.execute("UPDATE webhook_queue SET status='abandoned', attempts=? WHERE id=?",
                     (attempts, row["id"]))
        log(conn, "ERROR", f"Webhook abandoned after {attempts} attempts: {reason}")
    else:
        conn.execute("UPDATE webhook_queue SET attempts=?, status='pending' WHERE id=?",
                     (attempts, row["id"]))
        log(conn, "WARN", f"Webhook retry #{attempts} for {row['payment_id']}: {reason}")


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(_webhook_worker())
    yield
    task.cancel()


app.router.lifespan_context = lifespan