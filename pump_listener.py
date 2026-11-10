"""JARVIS Pump.fun event collector. Read-only, no trading or wallet access.

Run on a continuously running host (not GitHub Actions).
Set PUMPPORTAL_API_KEY as an environment variable if your provider requires it.
"""
import asyncio
import datetime
import json
import os
import sqlite3
import sys
from pathlib import Path

import websockets

DB_PATH = Path(os.environ.get("JARVIS_DB", "pump_events.sqlite3"))
API_KEY = os.environ.get("PUMPPORTAL_API_KEY", "").strip()
BASE_URL = "wss://pumpportal.fun/api/data"
URL = BASE_URL + ("?api-key=" + API_KEY if API_KEY else "")
RETRY_SECONDS = 5


def init_db(db):
    db.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        received_at_utc TEXT NOT NULL,
        event_type TEXT NOT NULL,
        mint TEXT,
        payload_json TEXT NOT NULL
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_mint ON events(mint)")
    db.commit()


def classify(data):
    # PumpPortal creation events include txType=create; migration
    # event fields can vary, so retain full original payload.
    event_type = str(data.get("txType") or data.get("type") or data.get("event") or "unknown")
    mint = data.get("mint") or data.get("tokenAddress")
    if mint is not None and not isinstance(mint, str):
        mint = None
    return event_type[:80], mint


async def listen():
    with sqlite3.connect(DB_PATH) as db:
        init_db(db)
        while True:
            try:
                async with websockets.connect(URL, ping_interval=20, ping_timeout=20,
                                              max_size=2**20) as ws:
                    for method in ("subscribeNewToken", "subscribeMigration"):
                        await ws.send(json.dumps({"method": method}))
                    print("JARVIS Pump listener connected (read-only)", flush=True)
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            if not isinstance(data, dict):
                                continue
                            kind, mint = classify(data)
                            received = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            db.execute(
                                "INSERT INTO events (received_at_utc,event_type,mint,payload_json) VALUES (?,?,?,?)",
                                (received, kind, mint, json.dumps(data, separators=(",", ":"))),
                            )
                            db.commit()
                            if mint:
                                print(json.dumps({"received_at_utc": received, "event": kind,
                                                  "mint": mint}, ensure_ascii=False), flush=True)
                        except (json.JSONDecodeError, ValueError) as exc:
                            print("Invalid event:", type(exc).__name__, file=sys.stderr, flush=True)
            except (OSError, websockets.exceptions.WebSocketException) as exc:
                print("Connection interrupted:", type(exc).__name__, file=sys.stderr, flush=True)
            await asyncio.sleep(RETRY_SECONDS)


if __name__ == "__main__":
    asyncio.run(listen())
