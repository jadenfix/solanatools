"""Verify current capture inputs, artifact hashes, metadata, and full decoding."""
import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECEIPT_PATH = REPO / "solana-bot" / "docs" / "demo" / "capture.json"


def command(*args):
    return subprocess.check_output(args, cwd=REPO, text=True).strip()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    receipt = json.loads(RECEIPT_PATH.read_text())
    source = command("git", "rev-parse", f"{receipt['source_commit']}^{{commit}}")
    assert source == receipt["source_commit"]
    assert command("git", "rev-parse", f"{source}^{{tree}}") == receipt["source_tree"]
    for relative, expected_blob in receipt["source_blobs"].items():
        captured_blob = command("git", "rev-parse", f"{source}:{relative}")
        current_blob = command("git", "hash-object", relative)
        assert captured_blob == expected_blob, f"receipt blob mismatch: {relative}"
        assert current_blob == expected_blob, f"capture input drift: {relative}"
    for relative, metadata in receipt["artifacts"].items():
        path = REPO / relative
        assert path.stat().st_size == metadata["bytes"], f"size mismatch: {relative}"
        assert sha256(path) == metadata["sha256"], f"SHA-256 mismatch: {relative}"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
            check=True,
        )
    readme = (REPO / "solana-bot" / "README.md").read_text()
    assert "docs/demo/offline-paper-workbench.gif" in readme
    assert "docs/demo/offline-paper-workbench.mp4" in readme
    print(
        f"MEDIA_VERIFY_OK source_blobs={len(receipt['source_blobs'])} "
        f"artifacts={len(receipt['artifacts'])} full_decode=gif,mp4,png"
    )


if __name__ == "__main__":
    main()
