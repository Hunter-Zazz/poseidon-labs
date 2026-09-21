"""Run the War Room mission against fresh, generated fixtures only."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def require_equal(actual, expected, label):
    # Assertions must remain active even under Python's -O option.
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    checker = Path(__file__).resolve().with_name("integrity.py")
    practice = Path(tempfile.mkdtemp(prefix="integrity-war-room-", dir="/tmp"))
    watched = practice / "watched"
    stored = practice / "stored"
    baseline = practice / "baseline.json"
    print(f"Practice directory: {practice}", flush=True)
    print("Fixtures are retained. Temporary files may disappear after cleanup or reboot.")
    original_baseline = None

    def run(command, code, expected):
        result = subprocess.run(
            [sys.executable, str(checker), command, str(watched),
             "--baseline", str(baseline), "--format", "json"],
            capture_output=True, text=True, timeout=30,
        )
        print(f"{command}: exit {result.returncode}\n{result.stdout}", flush=True)
        if original_baseline is not None:
            require_equal(baseline.read_bytes(), original_baseline, "baseline preserved")
        require_equal(result.returncode, code, f"{command} exit (stderr={result.stderr!r})")
        require_equal(result.stderr, "", f"{command} stderr")
        require_equal(json.loads(result.stdout), expected, f"{command} result")

    match = {"added": [], "modified": [], "missing": [], "unreadable": {},
             "unverified": [], "skipped": {}, "unverified_reasons": {}}
    try:
        watched.mkdir()
        stored.mkdir()
        (watched / "orders.txt").write_text("Hold position.\n", encoding="utf-8")
        (watched / "roster.txt").write_text("Crew accounted for.\n", encoding="utf-8")
        (watched / "steady.txt").write_text("Unchanged control.\n", encoding="utf-8")

        print("Stage 1 — Create the reference: record three generated files.")
        run("baseline", 0, {"baseline": str(baseline), "file_count": 3,
                            "unreadable": {}, "skipped": {}})
        original_baseline = baseline.read_bytes()

        print("Stage 2 — Match: unchanged files produce no differences or coverage gaps.")
        run("check", 0, match)

        print("Stage 3 — Changes: detect a new path, changed contents, and an absent path.")
        (watched / "orders.txt").rename(stored / "original-orders.txt")
        (watched / "orders.txt").write_text("Advance to station.\n", encoding="utf-8")
        (watched / "roster.txt").rename(stored / "roster.txt")
        (watched / "arrival.txt").write_text("New arrival.\n", encoding="utf-8")
        run("check", 1, dict(match, added=["arrival.txt"],
                             modified=["orders.txt"], missing=["roster.txt"]))

        print("Stage 4 — Restore: move fixtures back; the original baseline matches again.")
        (watched / "arrival.txt").rename(stored / "arrival.txt")
        (watched / "orders.txt").rename(stored / "changed-orders.txt")
        (stored / "original-orders.txt").rename(watched / "orders.txt")
        (stored / "roster.txt").rename(watched / "roster.txt")
        run("check", 0, match)
        print("MISSION PASS — all exit codes, categories, and baseline preservation verified.")
    finally:
        print(f"Fixtures left at: {practice}", flush=True)


if __name__ == "__main__":
    main()
