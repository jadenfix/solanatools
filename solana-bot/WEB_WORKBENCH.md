# Offline paper replay workbench

```sh
cd solana-bot
python replay_web.py
# Open http://127.0.0.1:8082
python -m unittest discover -s tests/integration -p test_web_replay.py -v
```

Python standard library only. The workbench calls the **same `RSIMomentumStrategy` and `PaperExecutionEngine` as `main.py`**, rather than simulating a different strategy in JavaScript.

Choose the explicitly synthetic 75-bar fixture or upload a CSV with a `price` column and optional `timestamp`. Configure starting cash, RSI period, exposure cap, fees, stop loss and take profit. Run and save the replay to inspect equity, rolling RSI and the full fee-bearing ledger. Saved runs reload from SQLite after page or server restart; export the full result as JSON.

User CSV provenance is labeled unverified. Rows are replayed in file order; the tool does not assert that timestamps are ordered or quotes executable. RSI uses the existing rolling gain/loss calculation; no strategy math was changed for this interface. A zero-fill result and RSI warmup are shown explicitly. Final holdings remain marked at the last bar price; fees, cash and equity follow the engine.

The default database is `replays.sqlite3`; use `--db /path/to/file.sqlite3` or `--port 9000` if needed. Requests are limited to 1 MiB and replays to 10,000 bars. Server binds only to `127.0.0.1`, uses validated JSON, parameterized SQLite, fixed static routes, cross-origin write checks, CSP and text-only user rendering. This is an unauthenticated local workspace; use a production server and authentication before any public deployment.

## HTTP API

- `GET /api/health`: offline-paper status.
- `POST /api/runs`: `{ "name": "Example", "source": "demo", "parameters": { "period": 14, "cash": 10000, "max_exposure": 0.25, "fee_bps": 10, "stop_loss_pct": 0.05, "take_profit_pct": 0.10 } }`.
- For CSV input, set `source` to `csv` and supply CSV text in `csv`.
- `GET /api/runs`: newest 100 saved-run summaries.
- `GET /api/runs/1`: full parameters, source, curve, ledger, fees and run metadata.
- `GET /api/runs/1/download`: full JSON as an attachment.

Source CSV text is not stored separately; saved results contain bar prices/timestamps and output curves. Upload the original file again to rerun a custom CSV with new parameters.

## Recording gate

Record the actual UI after HTTP tests and the browser workflow pass at the exact published PR head: run synthetic replay, inspect equity/RSI/fills, change parameters, upload CSV, reload history and export JSON. Keep **OFFLINE PAPER · NO WALLET** and data provenance visible. The broader portfolio/platform modules, live data, wallet/RPC/Jito execution and deployment remain incomplete and must not appear as working capabilities.
