# JARVIS Pump.fun Listener (experimental)

A read-only WebSocket listener for **Pump.fun token creation and migration events**.

## Requirements

- Python 3.11+
- A host that stays running 24/7 (a VPS or always-on computer).
- `pip install -r requirements-listener.txt`
- `python pump_listener.py`

The provider may require a PumpPortal API key. If so, configure `PUMPPORTAL_API_KEY` in the host's environment. **Never commit keys or wallet secrets to GitHub.** This listener never signs transactions.

Events are written to local SQLite `pump_events.sqlite3`. Keep that database on persistent storage. To inspect recent records:

```bash
python -c "import sqlite3; c=sqlite3.connect('pump_events.sqlite3'); print(*c.execute('select received_at_utc,event_type,mint from events order by id desc limit 10'), sep='\\n')"
```

## Important limitations

- This listener **is not deployed** by adding it to GitHub. GitHub Actions is not a 24/7 WebSocket server.
- It collects creation and migration events only; it does not collect every trade, calculate a live bonding-curve entry, verify holders, or generate BUY signals.
- The existing 15-minute GitHub Actions scanner is a **separate** process and does not read this local SQLite database. Integration requires a secure data-transfer/storage architecture.
- PumpPortal stream access terms, key requirements and charges can change. Verify them before connecting.
- Provider disconnections and gaps are possible; reconnecting does not recover missed events.
- No private keys, wallet connections, or live trades.

Provider docs: https://pumpportal.fun/data-api/real-time/
