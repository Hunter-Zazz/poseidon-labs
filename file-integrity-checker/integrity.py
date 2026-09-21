#!/usr/bin/env python3
"""Small Linux file-content integrity checker; standard library only."""

import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone


CHUNK_SIZE = 1024 * 1024
NOFOLLOW = os.O_NOFOLLOW


def safe_path(name):
    return (bool(name) and not name.startswith("/") and "\\" not in name
            and "\x00" not in name
            and all(part not in ("", ".", "..") for part in name.split("/"))
            and not re.match(r"^[A-Za-z]:", name))


def signature(info):
    """Metadata used to detect common concurrent edits and replacements."""
    return (info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def hash_file(parent_fd, name, initial):
    """Open relative to a pinned directory, refusing links and blocking FIFOs."""
    fd = os.open(name, os.O_RDONLY | NOFOLLOW | os.O_NONBLOCK,
                 dir_fd=parent_fd)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or signature(before) != signature(initial):
            raise OSError("changed_during_scan")
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(fd)
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if signature(before) != signature(after) or signature(before) != signature(current):
            raise OSError("changed_during_scan")
        return digest.hexdigest()
    finally:
        os.close(fd)


def scan(root):
    """Return hashes plus coverage gaps; never infer absence inside a gap."""
    hashes, unreadable, skipped = {}, {}, {}
    directories = set()

    def walk(fd, prefix):
        try:
            before = os.fstat(fd)
            names = sorted(os.listdir(fd))
        except OSError as exc:
            unreadable[prefix or "."] = str(exc)
            return
        for name in names:
            relative = prefix + "/" + name if prefix else name
            try:
                if not safe_path(relative):
                    raise OSError("filename cannot be represented in baseline format")
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    skipped[relative] = "symbolic_link"
                elif stat.S_ISDIR(info.st_mode):
                    directories.add(relative)
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW,
                                    dir_fd=fd)
                    try:
                        if signature(info) != signature(os.fstat(child)):
                            raise OSError("changed_during_scan")
                        walk(child, relative)
                        if signature(info) != signature(os.stat(
                                name, dir_fd=fd, follow_symlinks=False)):
                            raise OSError("changed_during_scan")
                    finally:
                        os.close(child)
                elif stat.S_ISREG(info.st_mode):
                    hashes[relative] = hash_file(fd, name, info)
                else:
                    skipped[relative] = "special_file"
            except OSError as exc:
                unreadable[relative] = str(exc)
        if signature(before) != signature(os.fstat(fd)):
            unreadable[prefix or "."] = "directory_changed_during_scan"

    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    try:
        walk(fd, "")
    finally:
        os.close(fd)
    return hashes, unreadable, skipped, directories


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def load_baseline(path):
    """Validate data before using its paths for comparison (never for opening)."""
    try:
        fd = os.open(path, os.O_RDONLY | NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError("baseline must not be a symbolic link") from exc
        raise
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("baseline must be a regular file (not a directory or special file)")
        # Keep ownership here so even fstat/fdopen/JSON failures close the fd.
        with os.fdopen(fd, encoding="utf-8", closefd=False) as stream:
            data = json.load(stream, object_pairs_hook=unique_object)
    finally:
        os.close(fd)
    if (not isinstance(data, dict) or type(data.get("version")) is not int
            or data["version"] != 1 or data.get("algorithm") != "sha256"
            or not isinstance(data.get("created_at"), str)
            or not isinstance(data.get("files"), dict)):
        raise ValueError("unsupported or malformed baseline")
    hashes = {}
    for name, entry in data["files"].items():
        if not safe_path(name):
            raise ValueError("unsafe baseline path: " + repr(name))
        if (not isinstance(entry, dict) or set(entry) != {"sha256"}
                or not isinstance(entry["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])):
            raise ValueError("invalid SHA-256 entry: " + name)
        hashes[name] = entry["sha256"]
    return hashes


def covered(path, gaps):
    return any(gap == "." or path == gap or path.startswith(gap + "/")
               for gap in gaps)


def compare(expected, actual, unreadable, skipped, directories):
    report = {"added": [], "modified": [], "missing": [],
              "unreadable": unreadable, "unverified": [], "skipped": skipped,
              "unverified_reasons": {}}
    for name in sorted(expected):
        # An observed directory is a type change, not a coverage gap: its
        # readable descendants must still participate in normal comparison.
        if name in directories:
            report["unverified"].append(name)
            report["unverified_reasons"][name] = "type_changed: regular_file -> directory"
        elif covered(name, unreadable) or covered(name, skipped):
            report["unverified"].append(name)
        elif name not in actual:
            report["missing"].append(name)
        elif actual[name] != expected[name]:
            report["modified"].append(name)
    report["added"] = sorted(name for name in actual if name not in expected
                             and not covered(name, unreadable))
    code = 2 if unreadable or report["unverified"] else (
        1 if any(report[key] for key in ("added", "modified", "missing")) else 0)
    return report, code


def publish(path, hashes, overwrite):
    """Prepare fully before publication; hard-link gives exclusive creation."""
    data = {"version": 1, "algorithm": "sha256",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": {name: {"sha256": digest} for name, digest in sorted(hashes.items())}}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=path.parent, delete=False) as stream:
            temporary = stream.name
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise ValueError("baseline must not be a symbolic link")
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def locations(root, baseline):
    raw_root = Path(os.path.abspath(root))
    if raw_root.is_symlink():
        raise ValueError("scan root must not be a symbolic link")
    root = raw_root.resolve(strict=True)
    raw_baseline = Path(os.path.abspath(baseline))
    if raw_baseline.is_symlink():
        raise ValueError("baseline must not be a symbolic link")
    baseline = raw_baseline.parent.resolve(strict=True) / raw_baseline.name
    if baseline == root or root in baseline.parents:
        raise ValueError("baseline must be outside the scan root")
    return root, baseline


def display(value):
    """Quote untrusted text, escaping controls, Unicode and surrogate filenames."""
    return json.dumps(value, ensure_ascii=True)


def text_report(command, report, code):
    """Render existing results without rescanning or changing their meaning."""
    if command == "check":
        heading = {0: "Check: no differences among verified files.",
                   1: "Check: differences found.",
                   2: "Check: incomplete; some paths could not be verified."}[code]
        categories = ("added", "modified", "missing", "unreadable", "unverified", "skipped")
        lines = [heading]
    else:
        lines = (["Baseline created: " + display(report["baseline"]),
                  "Files recorded: " + str(report["file_count"])] if code == 0 else
                 ["Baseline creation failed: incomplete scan; baseline not written."])
        categories = ("unreadable", "skipped")
    for category in categories:
        entries = report[category]
        lines.append(f"{category.capitalize()}: {len(entries)}")
        for name in sorted(entries):
            reasons = []
            if isinstance(entries, dict):
                reasons.append(display(entries[name]))
            elif category == "unverified":
                if name in report["unverified_reasons"]:
                    reasons.append(display(report["unverified_reasons"][name]))
                for source in ("unreadable", "skipped"):
                    for gap, reason in sorted(report[source].items()):
                        if covered(name, [gap]):
                            reasons.append(f"{source} {display(gap)}: {display(reason)}")
            lines.append("  " + display(name) + (" — " + "; ".join(reasons) if reasons else ""))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("baseline", "check"):
        child = sub.add_parser(command)
        child.add_argument("directory")
        child.add_argument("--baseline", required=True)
        child.add_argument("--format", choices=("json", "text"), default="json",
                           help="report format (default: json)")
        if command == "baseline":
            child.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        root, destination = locations(args.directory, args.baseline)
        if args.command == "check":
            expected = load_baseline(destination)
        elif os.path.lexists(destination) and not args.overwrite:
            raise ValueError("baseline exists; replacement requires --overwrite")
        hashes, unreadable, skipped, directories = scan(root)
        if args.command == "check":
            report, code = compare(expected, hashes, unreadable, skipped, directories)
        else:
            report = {"unreadable": unreadable, "skipped": skipped}
            code = 2 if unreadable else 0
            if not unreadable:
                publish(destination, hashes, args.overwrite)
                report["baseline"] = str(destination)
                report["file_count"] = len(hashes)
        print(text_report(args.command, report, code) if args.format == "text"
              else json.dumps(report, indent=2, sort_keys=True))
        return code
    except RecursionError:
        # A literal avoids invoking JSON serialization again after it fails.
        print(('Baseline creation failed: ' if args.command == "baseline" else 'Check failed: ')
              + 'excessive nesting during directory traversal or JSON processing'
              if args.format == "text" else
              '{"error": "excessive nesting during directory traversal or JSON processing"}',
              file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print((("Baseline creation failed: " if args.command == "baseline" else "Check failed: ")
               + display(str(exc))) if args.format == "text" else
              json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
