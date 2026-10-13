"""Offline RSI replay CLI; never sends transactions or requests market data."""
import argparse
import csv
import json
import os
import tempfile
from pathlib import Path
from core.strategies.rsi_momentum import RSIMomentumStrategy
from core.engine.paper import PaperExecutionEngine


def _require_distinct_input_output(source, output):
    """Reject aliases before a successful replay can destroy its source CSV."""
    if source is None or output is None:
        return
    if source.resolve() == output.resolve():
        raise ValueError("output must not overwrite the input CSV")
    if source.exists() and output.exists() and source.samefile(output):
        raise ValueError("output must not alias the input CSV")


def _write_json_atomic(path, payload):
    """Replace a completed JSON file; never stream partial JSON to the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(payload, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


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
        _require_distinct_input_output(path, args.output)
        with path.open(newline="") as handle:
            data = list(csv.DictReader(handle))
        engine = PaperExecutionEngine(RSIMomentumStrategy(args.period), cash=args.cash,
                                      max_exposure=args.max_exposure, fee_bps=args.fee_bps)
        result = engine.run(data)
        if args.output:
            _write_json_atomic(args.output, result)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps({k: v for k, v in result.items() if k not in ("ledger", "curve")}, indent=2))
    return result


if __name__ == "__main__":
    main()
