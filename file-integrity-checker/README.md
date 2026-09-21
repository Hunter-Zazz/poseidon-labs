# Local file-integrity checker

A small Linux Python 3 standard-library utility. It recursively records SHA-256
hashes of regular files and compares subsequent scans. No installation is needed.

For a repeatable exercise using only generated temporary fixtures, follow the
[War Room practice mission](PRACTICE_MISSION.md).

From this project directory, with your chosen directory and an existing baseline
parent directory:

```bash
/usr/bin/python3 integrity.py baseline /path/to/watch --baseline /path/to/baselines/watch.json
/usr/bin/python3 integrity.py check /path/to/watch --baseline /path/to/baselines/watch.json
/usr/bin/python3 integrity.py baseline /path/to/watch --baseline /path/to/baselines/watch.json --overwrite
/usr/bin/python3 -m unittest discover -s tests -v
```

The baseline must be outside the resolved scan root. Existing baselines require
explicit `--overwrite`. Check never updates the baseline. Both commands accept
`--format json|text`; JSON is the default and its schema is unchanged. For example:

```bash
/usr/bin/python3 integrity.py baseline /path/to/watch --baseline /path/to/baselines/watch.json --format text
/usr/bin/python3 integrity.py check /path/to/watch --baseline /path/to/baselines/watch.json --format text
```

Text reports show category counts, filenames, and available reasons. Unverified
entries include explicit type-change reasons or the unreadable/skipped coverage
gap that prevented verification. Counts are per category and may overlap: a
tracked symlink is both skipped and unverified. Filenames, paths, and reasons
are quoted with JSON ASCII escaping, including newlines, terminal escapes, and
non-ASCII characters. Text output is intended for people; use JSON for automation.
Normal reports (including incomplete scans and baseline scan failures) go to
stdout. Operational errors go to stderr in the selected format; argument syntax
errors retain argparse's usage diagnostics. Baseline text explicitly reports
creation or failure and lists skipped entries when a scan report is available.

JSON output separates
`added`, `modified`, `missing`, `unreadable`, `unverified`, and `skipped`.
Exit status is 0 for success/a complete match, 1 for differences, and 2 for errors
or incomplete coverage (even if other differences were found). Untracked links
and special files are explicitly skipped and do not alone make a scan incomplete.
A tracked path replaced by one is unverified and returns 2. Files beneath an
inaccessible or unstable directory are unverified, never confirmed missing.
If a tracked regular file becomes a directory, its path is also unverified,
with `type_changed: regular_file -> directory` in `unverified_reasons`, and the
check returns 2. It is not missing. Observed directories are tracked separately
from skipped entries and coverage failures, so readable contents are still
scanned normally and new files inside the replacement directory appear as added.

## Components and format

`scan` walks pinned directory descriptors and records coverage gaps. `hash_file`
reads at most 1 MiB per read, keeping file-content memory bounded. `compare` keeps
uncertainty separate from confirmed differences. `load_baseline` validates the
schema and paths and rejects duplicate JSON keys at every nesting level.
Baseline loading opens with Linux `O_NOFOLLOW | O_NONBLOCK` and requires a regular
file using `fstat` before reading. Symlinks (including substitutions just before
opening), FIFOs, directories, and other special files are rejected with exit 2;
the descriptor is closed on success and on failure.
`publish` prepares and fsyncs a temporary file in the baseline's parent directory,
then uses an exclusive hard link for creation or atomic replacement when authorized.
Scan and preparation failures preserve the previous baseline. `main` provides the
two commands and consistent exit codes. Tests use isolated generated fixtures.

Example baseline (the hash shown is SHA-256 of an empty file):

```json
{
  "version": 1,
  "algorithm": "sha256",
  "created_at": "2026-09-11T18:00:00+00:00",
  "files": {
    "nested/empty.txt": {
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
  }
}
```

Paths are relative with `/` separators, so baselines can be used with another
copy of a directory. Absolute paths, traversal components, empty components,
backslashes, drive prefixes, malformed hashes, and duplicate keys are rejected.
Only file contents are baselined; empty directories and permission-only changes
are not baselined. Directory observations detect tracked files changing type.
Metadata is used solely to detect changes during reads.

## Safety and limitations

Linux `O_NOFOLLOW` is used for the root, child directory, and file opens. File
opens are relative to already opened directories; swapping an enumerated file
for a symlink cannot redirect its read. `O_NONBLOCK` avoids blocking on a FIFO
swapped into place, and opened objects must be regular files. Symlink roots and
baseline destinations are rejected. Selected paths' parent components are
resolved initially, so parent symlinks can be resolved at that stage.

This is not a filesystem snapshot or a security boundary against an active
local attacker. Identity, size, modification time, and change time checks catch
common concurrent edits, but changes after a final check, namespace races during
initial root resolution, mount changes, and carefully timed mutations can escape
detection. Use a quiet directory for repeatable results. The baseline parent
must be trusted and stable: publication does not pin its ancestor directories.
Atomic publication prevents partially prepared replacement, but directory entries
are not fsynced, so power-loss durability is not guaranteed. Hard-link creation
requires filesystem support. Baseline JSON and path inventories occupy memory
proportional to file count; recursive depth is limited by Python and file descriptors.
Excessive nesting during traversal or JSON loading/serialization returns a clear
error and exit 2 without a traceback; the Python recursion limit is not changed.
Traversal and baseline-serialization recursion failures publish no new baseline,
preserve an existing baseline, and remove temporary publication files. Regression
tests inject these failures deterministically and guard FIFO and symlink-race
checks with subprocess timeouts.

The utility never writes scanned files or changes their permissions. Ordinary
reads may update access times. Keep baselines outside the tree and avoid hard-link
aliases between a baseline and scanned files. There are no exclusion patterns,
watch service, signatures, automatic retries, or automatic baseline refreshes.

SHA-256 produces a fixed-length fingerprint of bytes. A changed hash indicates
changed contents, not malicious activity: legitimate edits, software updates,
synchronization, and corruption can all cause changes. A baseline is a reference,
not proof that the original files were safe. Someone able to replace the baseline
can conceal changes; keep it in a trusted location.

## Temporary-fixture demonstration

Run this exact command from the project directory. It generates and removes its
own temporary directory, exercises the actual CLI, and prints each exit code.
It does not use or alter an existing baseline or exercise directory.

```bash
/usr/bin/python3 - <<'PY'
from pathlib import Path
import subprocess
import tempfile

cli = Path("integrity.py").resolve()
with tempfile.TemporaryDirectory(prefix="integrity-text-demo-") as temporary:
    base = Path(temporary)
    root = base / "watched"
    root.mkdir()
    baseline = base / "baseline.json"
    (root / "a").write_text("original")
    (root / "gone").touch()
    (root / "link").symlink_to("absent")

    def run(label, action, expected, *extra):
        result = subprocess.run(
            ["/usr/bin/python3", str(cli), action, str(root),
             "--baseline", str(baseline), "--format", "text", *extra],
            capture_output=True, text=True, check=False)
        print(f"{label}: exit {result.returncode}")
        print(result.stdout, end="")
        if result.stderr:
            print("stderr:", result.stderr, end="")
        assert result.returncode == expected

    run("creation", "baseline", 0)
    run("unchanged", "check", 0)
    (root / "a").write_text("edited")
    (root / "gone").unlink()
    (root / "new\n\x1b[31m").touch()
    run("changed and escaped filename", "check", 1)
    (root / "a").unlink()
    (root / "a").symlink_to("absent")
    run("incomplete", "check", 2)
    run("overwrite refused", "baseline", 2)
    (root / "bad\\name").touch()
    run("baseline scan failure", "baseline", 2, "--overwrite")
PY
```
