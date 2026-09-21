# War Room: integrity recovery mission

From the repository root on Linux (in either a worktree or the main checkout):

```bash
cd 12_ENGINE_ROOM/projects/02_file_integrity
/usr/bin/python3 practice.py
```

No installation is needed. Each launch creates a unique `/tmp/integrity-war-room-*`
directory containing only generated data. The runner accepts no directory or other
mission arguments (only the help option). It calls the existing `integrity.py`
by absolute path with the current Python interpreter and reads its JSON reports.
It does not duplicate hashing or comparison logic.

1. **Establish the reference.** Generate `orders.txt`, `roster.txt`, and
   `steady.txt` in `watched/`. Baseline creation must exit 0, record three files,
   and report no unreadable or skipped paths. `baseline.json` lives beside
   `watched/`, outside the scan, and is created only once.
2. **Prove the initial match.** Check must exit 0 with every difference and
   coverage category empty. This establishes a known working starting point.
3. **Introduce differences.** Move the original orders into `stored/` and write
   changed orders at the same watched path. Move the roster into storage and
   create an arrival file. Check must exit 1 with exactly `added: [arrival.txt]`,
   `modified: [orders.txt]`, and `missing: [roster.txt]`. The unchanged control
   stays verified. Missing means absent from the watched tree, not destroyed.
4. **Recover against the original reference.** Move the arrival and changed
   orders into storage, then move the original orders and roster back. Check
   must exit 0 with all categories empty. Recovery uses the original baseline;
   it does not accept the changed state as a new reference.

Each check asserts unchanged baseline bytes and the complete expected JSON report,
including empty `unreadable`, `unverified`, `skipped`, and `unverified_reasons`.
Assertions remain active with Python optimization. Unexpected output or exit codes
stop the mission with a nonzero runner exit. Checker exit 2 (error or incomplete
coverage) fails the mission. Success prints `MISSION PASS` and exits 0.

Fixture files are moved instead of deleted. No permissions are changed, no real
documents are scanned, and no baseline overwrite is requested. The location is
printed at creation and on exit, including on failure. On success, `watched/`
holds the restored originals, `stored/` retains the changed orders and arrival,
and the baseline remains available. There is no automatic cleanup. Temporary
files may disappear after system cleanup or reboot. Rerun for a fresh mission.

## Existing test suite

Run the unchanged suite from this project directory:

```bash
/usr/bin/python3 -m unittest discover -s tests -v
```

The existing `test_real_permission_denial` changes permissions only on its freshly
generated temporary fixture and restores them afterward. This test is authorized;
do not apply a custom skip wrapper. If the execution environment bypasses file
permissions, the test skips itself because actual permission denial cannot be
exercised. Report that skip explicitly when it occurs. The practice runner itself
does not change permissions.
