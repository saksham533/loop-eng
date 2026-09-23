from fastapi import FastAPI
from pydantic import BaseModel

from mocks.common.db import get_conn, init_schema, log

ERP_DDL = """
CREATE TABLE IF NOT EXISTS fulfillments (
  order_id TEXT PRIMARY KEY,
  payment_id TEXT,
  status TEXT,
  triggered_at TEXT
);
CREATE TABLE IF NOT EXISTS logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  level TEXT,
  message TEXT,
  created_at TEXT
);
"""

app = FastAPI(title="ERP / Fulfillment")
init_schema("erp", ERP_DDL)


class TriggerRequest(BaseModel):
    order_id: str
    payment_id: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "erp-mock"}


@app.get("/state")
def state():
    conn = get_conn("erp")
    rows = [dict(r) for r in conn.execute("SELECT * FROM fulfillments").fetchall()]
    conn.close()
    return {"fulfillments": rows}


@app.get("/logs")
def logs(limit: int = 50):
    conn = get_conn("erp")
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()]
    conn.close()
    return {"logs": rows}


@app.post("/reset")
def reset():
    conn = get_conn("erp")
    conn.executescript("DELETE FROM fulfillments; DELETE FROM logs;")
    conn.close()
    return {"reset": True}


@app.post("/fulfillment/trigger")
def trigger(req: TriggerRequest):
    conn = get_conn("erp")
    conn.execute(
        "INSERT OR REPLACE INTO fulfillments (order_id, payment_id, status, triggered_at) "
        "VALUES (?, ?, 'TRIGGERED', datetime('now'))",
        (req.order_id, req.payment_id),
    )
    log(conn, "INFO", f"Fulfillment triggered for {req.order_id}")
    conn.close()
    return {"order_id": req.order_id, "status": "TRIGGERED"}