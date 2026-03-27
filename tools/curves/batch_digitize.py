#!/usr/bin/env python3
"""Batch-digitize all target mics from RecordingHacks.

Pairs each target mic against SM57 (0006) and extracts the second curve.
"""

import subprocess
import sys
from pathlib import Path

DIGITIZE = Path(__file__).resolve().parent / "digitize.py"

# RecordingHacks mic IDs: (id, name)
TARGETS = [
    ("0253", "SM58"),
    ("0255", "SM7B"),
    ("0307", "C414 XL II"),
    ("0335", "D112"),
    ("0219", "Beta 52A"),
    ("0417", "RE20"),
    ("0429", "AEA R84"),
    ("0552", "MD421"),
    ("0567", "Audix D6"),
    ("0701", "Coles 4038"),
    ("0860", "U87 Ai"),
    ("1009", "M88 TG"),
    ("1091", "KM184"),
    ("1184", "e906"),
    ("0323", "C451 B"),
]

REF_ID = "0006"  # SM57


def main():
    failed = []
    for mic_id, name in TARGETS:
        print(f"\n{'='*60}")
        print(f"  {name} ({mic_id})")
        print(f"{'='*60}")
        result = subprocess.run(
            [sys.executable, str(DIGITIZE), REF_ID, mic_id, "--second"],
            timeout=120,
        )
        if result.returncode != 0:
            failed.append((mic_id, name))

    print(f"\n{'='*60}")
    print(f"Done: {len(TARGETS) - len(failed)}/{len(TARGETS)} succeeded")
    if failed:
        print(f"Failed: {', '.join(f'{name} ({id})' for id, name in failed)}")


if __name__ == "__main__":
    main()
