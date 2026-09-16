"""Read-only Linux system snapshot utility from Project Poseidon."""

import argparse
import json
import os
from pathlib import Path

from .collector import collect_system_info
from .formatting import format_system_info


def directory_path(value: str) -> Path:
    """Resolve a caller-relative directory, reporting argument errors cleanly."""
    try:
        path = Path(value).resolve(strict=True)
        if not path.is_dir():
            raise ValueError("not a directory")
    except (OSError, ValueError, RuntimeError) as error:
        raise argparse.ArgumentTypeError(f"invalid directory {value!r}: {error}") from None
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON with raw measurements")
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="save the report to a new private UTF-8 file instead of stdout",
    )
    parser.add_argument(
        "--disk-path",
        type=directory_path,
        metavar="DIRECTORY",
        help="measure the filesystem containing DIRECTORY (default: current working directory)",
    )
    args = parser.parse_args()
    system = collect_system_info(project_path=args.disk_path)

    if args.json:
        report = json.dumps(system, indent=2, allow_nan=False) + "\n"
    else:
        report = "\n".join([
            "",
            "POSEIDON SYSTEM COLLECTOR",
            "========================",
            "",
            format_system_info(system),
            "",
        ])

    if args.output is None:
        print(report, end="")
    else:
        try:
            # O_EXCL rejects existing entries, including dangling symlinks,
            # without a check-then-create race. Restrict access at creation.
            with open(
                args.output,
                "x",
                encoding="utf-8",
                opener=lambda path, flags: os.open(path, flags, 0o600),
            ) as destination:
                destination.write(report)
        except (OSError, ValueError) as error:
            parser.exit(1, f"error: cannot save report to {args.output!r}: {error}\n")


if __name__ == "__main__":
    main()
