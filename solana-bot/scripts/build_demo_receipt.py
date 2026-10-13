"""Build the source/blob and media receipt for the offline replay demo."""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "solana-bot" / "docs" / "demo"
SOURCE_PATHS = [
    "solana-bot/main.py",
    "solana-bot/replay_web.py",
    "solana-bot/core/engine/paper.py",
    "solana-bot/core/strategies/base.py",
    "solana-bot/core/strategies/rsi_momentum.py",
    "solana-bot/fixtures/synthetic_prices.csv",
    "solana-bot/web/index.html",
    "solana-bot/web/workbench.css",
    "solana-bot/web/workbench.js",
    "solana-bot/tests/unit/test_paper.py",
    "solana-bot/tests/integration/test_web_replay.py",
    "solana-bot/browser-tests/e2e.mjs",
    "solana-bot/browser-tests/capture.mjs",
    "solana-bot/browser-tests/package.json",
    "solana-bot/browser-tests/package-lock.json",
    "solana-bot/scripts/generate_demo.sh",
    "solana-bot/scripts/build_demo_receipt.py",
    "solana-bot/scripts/verify_demo_media.py",
]
ARTIFACTS = [
    "solana-bot/docs/demo/offline-paper-workbench.gif",
    "solana-bot/docs/demo/offline-paper-workbench.mp4",
    "solana-bot/docs/demo/poster.png",
]


def command(*args):
    return subprocess.check_output(args, cwd=REPO, text=True).strip()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path):
    raw = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_name,width,height,nb_frames,duration",
         "-of", "json", str(path)], text=True
    )
    data = json.loads(raw)
    stream = data["streams"][0]
    duration = stream.get("duration") or data.get("format", {}).get("duration")
    return {
        "codec": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "duration_seconds": round(float(duration), 3) if duration else None,
        "frames": int(stream["nb_frames"]) if str(stream.get("nb_frames", "")).isdigit() else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    source = command("git", "rev-parse", f"{args.source_commit}^{{commit}}")
    source_tree = command("git", "rev-parse", f"{source}^{{tree}}")
    blobs = {path: command("git", "rev-parse", f"{source}:{path}") for path in SOURCE_PATHS}
    artifacts = {}
    for relative in ARTIFACTS:
        path = REPO / relative
        artifacts[relative] = {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            **probe(path),
        }
    receipt = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": source,
        "source_tree": source_tree,
        "source_blobs": blobs,
        "artifacts": artifacts,
        "observed_workflow": {
            "mode": "offline-paper",
            "data": "bundled synthetic fixture plus explicitly unverified uploaded fixture CSV",
            "synthetic_bars": 75,
            "synthetic_fills": 9,
            "interactions": [
                "run and persist replay",
                "inspect equity, RSI, fees, drawdown, and fill ledger",
                "change RSI period and fee parameters",
                "upload local CSV with unverified provenance",
            ],
        },
        "limitations": [
            "No live Solana RPC, wallet, Jito, order, or market-data call.",
            "No profitability, strategy quality, latency, liquidity, or deployment claim.",
            "Uploaded CSV provenance is unverified; bundled prices are synthetic.",
        ],
    }
    target = DEMO / "capture.json"
    descriptor, temporary = tempfile.mkstemp(dir=DEMO, prefix=".capture.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(receipt, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print(f"DEMO_RECEIPT_OK source={source} blobs={len(blobs)} artifacts={len(artifacts)}")


if __name__ == "__main__":
    main()
