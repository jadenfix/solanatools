# Solana RSI Replay

A local, spot-only paper execution engine for the RSI strategy in this repository.
It replays price bars, sizes inventory within an exposure cap, applies trading
fees and stop-loss/take-profit exits, and exports a reconciled fill ledger and
equity curve. The bundled fixture is **synthetic**, not historical performance.

## Actual workflow demo

![Offline paper replay workbench](docs/demo/offline-paper-workbench.gif)

[Watch the 960×540 MP4](docs/demo/offline-paper-workbench.mp4) ·
[Capture receipt](docs/demo/capture.json)

This is a 23-second recording of the real local browser workbench at captured
source commit `c6cc2aba41267c0ac07869527786e9d6c4fc0247`. It runs the bundled
75-bar synthetic fixture, changes strategy parameters, uploads a separate
fixture CSV whose provenance is explicitly unverified, and inspects the actual
charts and fill ledger. The receipt pins all 18 runtime, test, and capture blobs
plus the SHA-256 and decoded metadata for the GIF, MP4, and poster.

## Run without accounts or network access

Python 3.9+; the replay itself uses only the standard library.

```sh
cd solana-bot
python main.py --demo --output artifacts/replay.json
python main.py --csv /path/to/prices.csv --period 14 --cash 10000 --fee-bps 10
python -m pip install pytest
python -m pytest -q tests/unit tests/integration
```

Input CSV: `price` is required and must be positive and finite; `timestamp` is
optional. CSV rows are consumed in file order. Signals act at each supplied price;
this model does not simulate liquidity, slippage, latency, or executable quotes.
`SHORT` means sell existing spot inventory, never borrow. Final holdings are
marked to the last price rather than automatically liquidated. JSON includes
cash, quantity, equity, RSI, drawdown, and the fee-bearing fill ledger.

`--dry-run` is an alias for the bundled offline replay. No wallet is read and no
network endpoint is called. The older RPC/Jito/wallet modules remain research
scaffolds: live transactions and a real market-price feed are not implemented.
CLI reports are written atomically, and an output path that is the input CSV—or
a resolved, symbolic-link, or hard-link alias of it—is rejected before replay.

## Checks

The tests verify exact RSI warmup, bounded price history, invalid market inputs,
fee and cash reconciliation, risk exits, input preservation, atomic report
replacement, and the complete CLI export path.

```sh
cd solana-bot
python -m pytest -q tests/unit tests/integration
cd browser-tests && npm ci && npx playwright-core install chromium && npm test
cd .. && python scripts/verify_demo_media.py
```
