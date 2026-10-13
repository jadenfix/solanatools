"""Offline RSI replay CLI; never sends transactions or requests market data."""
import argparse
import csv
import json
from pathlib import Path
from core.strategies.rsi_momentum import RSIMomentumStrategy
from core.engine.paper import PaperExecutionEngine


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", type=Path, help="local CSV with price and optional timestamp")
    source.add_argument("--demo", "--dry-run", action="store_true", help="replay bundled synthetic fixture")
    parser.add_argument("--cash", type=float, default=10000)
    parser.add_argument("--period", type=int, default=14)
    parser.add_argument("--max-exposure", type=float, default=0.25)
    parser.add_argument("--fee-bps", type=float, default=10)
    parser.add_argument("--output", type=Path, help="save full curve and fill ledger as JSON")
    args = parser.parse_args(argv)
    path = args.csv or Path(__file__).parent / "fixtures" / "synthetic_prices.csv"
    try:
        with path.open(newline="") as handle:
            data = list(csv.DictReader(handle))
        engine = PaperExecutionEngine(RSIMomentumStrategy(args.period), cash=args.cash,
                                      max_exposure=args.max_exposure, fee_bps=args.fee_bps)
        result = engine.run(data)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("ledger", "curve")}, indent=2))
    return result


if __name__ == "__main__":
    main()
