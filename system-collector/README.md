# Poseidon System Collector

A small, read-only Linux/Python utility that collects a local system snapshot without changing system state.

This is the public standalone extraction of the system-collection work developed inside Project Poseidon. The collection and formatting logic is derived directly from the working private engineering project; public packaging separates it from private operational material and makes it independently testable.

## What it collects

- UTC collection timestamp
- operating-system name
- kernel release
- Python version
- CPU architecture and logical CPU count
- total and available memory from `/proc/meminfo`
- disk totals for a selected local filesystem
- uptime from `/proc/uptime`

It does **not** collect credentials, browser data, user documents, network traffic or remote-system information.

## Install for development

```bash
cd system-collector
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

## Run

Human-readable output:

```bash
poseidon-system-collector
```

JSON output:

```bash
poseidon-system-collector --json
```

Measure the filesystem containing a particular directory:

```bash
poseidon-system-collector --disk-path /tmp
```

Write a new private report file with mode `0600`:

```bash
poseidon-system-collector --json --output snapshot.json
```

The output file is created exclusively; the command will not overwrite an existing file.

## Tests

```bash
pytest -q
```

The tests use temporary/synthetic `/proc`-style data and monkeypatched platform values where appropriate. They check collection units, missing-source behaviour, malformed input, formatting, CLI behaviour, directory validation and private report-file creation.

## Example output

See [`examples/sample-output.json`](examples/sample-output.json). The committed example is synthetic and does not describe the Project Poseidon workstation.

## Privacy note

A real collector run can reveal local facts such as OS/kernel version, memory size, uptime and a filesystem path. Review and redact output before posting it publicly.

No real Project Poseidon host output is committed here.

## Limitations

- Linux-oriented because memory and uptime use `/proc`.
- Availability of individual measurements depends on the local platform and permissions.
- This is an inventory/snapshot tool, not a security scanner and not proof that a host is secure.
- Disk usage describes the filesystem containing the selected path, not the size of that directory alone.

## Licence

MIT. See the repository-level [`LICENSE`](../LICENSE).
