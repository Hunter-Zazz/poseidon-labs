import contextlib
import hashlib
import io
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import integrity


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "watched"
        self.root.mkdir()
        self.baseline = self.base / "baseline.json"
        (self.root / "a").write_bytes(b"abc")

    def command(self, action, *extra):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = integrity.main([action, str(self.root), "--baseline",
                                   str(self.baseline), *extra])
        return code, json.loads(output.getvalue())

    def test_round_trip_and_categories(self):
        (self.root / "gone").write_text("gone")
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "é").write_bytes(b"\x00\xff")
        (self.root / "empty").touch()
        before = (self.root / "a").stat().st_mtime_ns
        self.assertEqual(self.command("baseline")[0], 0)
        self.assertEqual(integrity.load_baseline(self.baseline)["a"],
                         hashlib.sha256(b"abc").hexdigest())
        self.assertEqual(self.command("check")[0], 0)
        self.assertEqual((self.root / "a").read_bytes(), b"abc")
        self.assertEqual((self.root / "a").stat().st_mtime_ns, before)
        (self.root / "a").write_text("edited")
        (self.root / "gone").unlink()
        (self.root / "new").touch()
        code, report = self.command("check")
        self.assertEqual(code, 1)
        self.assertEqual(report["added"], ["new"])
        self.assertEqual(report["modified"], ["a"])
        self.assertEqual(report["missing"], ["gone"])

    def cli(self, action, *extra):
        return subprocess.run(
            ["/usr/bin/python3", integrity.__file__, action, str(self.root),
             "--baseline", str(self.baseline), *extra],
            capture_output=True, text=True, timeout=5)

    def test_text_cli_success_changes_and_incomplete(self):
        (self.root / "gone").touch()
        (self.root / "link").symlink_to("absent")
        result = self.cli("baseline", "--format", "text")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("Baseline created:", result.stdout)
        self.assertIn("Files recorded: 2", result.stdout)
        self.assertIn('Skipped: 1\n  "link" — "symbolic_link"', result.stdout)
        result = self.cli("check", "--format", "text")
        self.assertEqual(result.returncode, 0)
        self.assertIn("no differences among verified files", result.stdout)
        for category in ("Added", "Modified", "Missing", "Unreadable", "Unverified"):
            self.assertIn(category + ": 0", result.stdout)
        (self.root / "a").write_text("changed")
        (self.root / "gone").unlink()
        hostile = "new\n\x1b[31m\x7f\x85"
        (self.root / hostile).touch()
        result = self.cli("check", "--format", "text")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        for category in ("Added", "Modified", "Missing"):
            self.assertIn(category + ": 1", result.stdout)
        self.assertIn(json.dumps(hostile), result.stdout)
        self.assertNotIn(hostile, result.stdout)
        (self.root / "a").unlink()
        (self.root / "a").symlink_to("absent")
        result = self.cli("check", "--format", "text")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        self.assertIn("Check: incomplete", result.stdout)
        self.assertNotIn("match", result.stdout)
        self.assertIn('Unverified: 1\n  "a" — skipped "a": "symbolic_link"', result.stdout)

    def test_text_baseline_failures_and_operational_errors(self):
        (self.root / "bad\\name\n\x1b").touch()
        (self.root / "link").symlink_to("absent")
        result = self.cli("baseline", "--format", "text")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        self.assertIn("Baseline creation failed", result.stdout)
        self.assertIn("Unreadable: 1", result.stdout)
        self.assertIn("Skipped: 1", result.stdout)
        self.assertNotIn("\x1b", result.stdout)
        self.assertFalse(self.baseline.exists())
        self.baseline.write_text("invalid")
        for action in ("baseline", "check"):
            result = self.cli(action, "--format", "text")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("failed:", result.stderr)

    def test_default_json_compatibility(self):
        result = self.cli("baseline")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {
            "baseline": str(self.baseline), "file_count": 1,
            "unreadable": {}, "skipped": {}})
        default = self.cli("check")
        explicit = self.cli("check", "--format", "json")
        self.assertEqual(default.returncode, 0)
        self.assertEqual(default.stdout, explicit.stdout)
        self.assertEqual(default.stdout, json.dumps({
            "added": [], "modified": [], "missing": [], "unreadable": {},
            "unverified": [], "skipped": {}, "unverified_reasons": {}},
            indent=2, sort_keys=True) + "\n")

    def test_text_reasons_and_errors_are_escaped(self):
        self.command("baseline")
        reason = "denied\n\x1b[31m\r\t\x85"
        for action, target, failure in (
                ("check", "integrity.hash_file", PermissionError(reason)),
                ("check", "integrity.load_baseline", ValueError(reason)),
                ("baseline", "integrity.scan", RecursionError())):
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch(target, side_effect=failure), contextlib.redirect_stdout(stdout), \
                    contextlib.redirect_stderr(stderr):
                code = integrity.main([action, str(self.root), "--baseline",
                                       str(self.baseline), "--format", "text",
                                       *(["--overwrite"] if action == "baseline" else [])])
            self.assertEqual(code, 2)
            output = stdout.getvalue() + stderr.getvalue()
            self.assertNotIn("\x1b", output)
            if target == "integrity.hash_file":
                self.assertEqual(stderr.getvalue(), "")
                self.assertIn("Unreadable: 1", output)
                self.assertIn("Unverified: 1", output)
                self.assertEqual(output.count(json.dumps(reason)), 2)
            else:
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("failed:", stderr.getvalue())
                self.assertIn("excessive nesting" if action == "baseline" else
                              json.dumps(reason), stderr.getvalue())

    def test_creation_and_replacement_safety(self):
        self.command("baseline")
        original = self.baseline.read_bytes()
        (self.root / "a").write_text("edited")
        self.assertEqual(self.command("baseline")[0], 2)
        with patch("integrity.os.fsync", side_effect=OSError("disk failure")):
            self.assertEqual(self.command("baseline", "--overwrite")[0], 2)
        self.assertEqual(self.baseline.read_bytes(), original)
        with patch("integrity.hash_file", side_effect=PermissionError("denied")):
            self.assertEqual(self.command("baseline", "--overwrite")[0], 2)
        self.assertEqual(self.baseline.read_bytes(), original)
        with patch("integrity.os.replace", side_effect=OSError("replace failure")):
            self.assertEqual(self.command("baseline", "--overwrite")[0], 2)
        self.assertEqual(self.baseline.read_bytes(), original)
        self.assertEqual(self.command("baseline", "--overwrite")[0], 0)
        self.assertEqual(self.command("check")[0], 0)
        self.assertEqual(sorted(p.name for p in self.base.iterdir()),
                         ["baseline.json", "watched"])

    def test_exclusive_publication_race(self):
        real_link = os.link
        def racing_link(source, destination):
            Path(destination).write_text("other writer")
            return real_link(source, destination)
        with patch("integrity.os.link", side_effect=racing_link):
            self.assertEqual(self.command("baseline")[0], 2)
        self.assertEqual(self.baseline.read_text(), "other writer")

    def test_locations(self):
        with self.assertRaises(ValueError):
            integrity.locations(self.root, self.root / "baseline.json")
        link = self.base / "link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            integrity.locations(link, self.baseline)
        self.baseline.symlink_to(self.base / "absent")
        self.assertEqual(self.command("baseline", "--overwrite")[0], 2)

    def test_fifo_baseline_does_not_block(self):
        os.mkfifo(self.baseline)
        result = subprocess.run(
            ["/usr/bin/python3", integrity.__file__, "check", str(self.root),
             "--baseline", str(self.baseline)],
            capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("regular file", json.loads(result.stderr)["error"])
        self.assertNotIn("Traceback", result.stderr)

    def test_baseline_symlink_swap_before_open(self):
        self.command("baseline")
        fifo = self.base / "fifo"
        os.mkfifo(fifo)
        # Run the injected race in a subprocess: following the substituted
        # link to a FIFO must not be able to hang the test runner.
        script = '''
import os
from pathlib import Path
import sys
from unittest.mock import patch
import integrity
baseline = Path(sys.argv[2])
real_open = os.open
def swapped(path, flags, *args, **kwargs):
    if Path(path) == baseline:
        baseline.unlink()
        baseline.symlink_to(sys.argv[3])
    return real_open(path, flags, *args, **kwargs)
with patch("integrity.os.open", side_effect=swapped):
    sys.exit(integrity.main(["check", sys.argv[1], "--baseline", str(baseline)]))
'''
        result = subprocess.run(
            ["/usr/bin/python3", "-c", script, str(self.root), str(self.baseline), str(fifo)],
            cwd=Path(integrity.__file__).parent,
            capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("symbolic link", json.loads(result.stderr)["error"])
        self.assertNotIn("Traceback", result.stderr)

    def test_directory_baseline_rejected(self):
        self.baseline.mkdir()
        code, report = self.command("check")
        self.assertEqual(code, 2)
        self.assertIn("regular file", report["error"])

    def test_baseline_descriptor_closed_on_failures(self):
        self.command("baseline")
        real_open = os.open
        for target in ("integrity.os.fstat", "integrity.os.fdopen", "integrity.json.load"):
            opened = []
            def tracked_open(*args, **kwargs):
                fd = real_open(*args, **kwargs)
                opened.append(fd)
                return fd
            with self.subTest(target=target), \
                    patch("integrity.os.open", side_effect=tracked_open), \
                    patch(target, side_effect=RecursionError("injected")):
                code, report = self.command("check")
            self.assertEqual(code, 2)
            self.assertIn("excessive nesting", report["error"])
            self.assertEqual(len(opened), 1)
            with self.assertRaises(OSError):
                os.fstat(opened[0])

    def test_deep_json_returns_error_without_traceback(self):
        self.command("baseline")
        original = self.baseline.read_bytes()
        # Decoder nesting limits vary between Python versions; inject the
        # exception at the decoder boundary without altering recursion limits.
        with patch("integrity.json.load", side_effect=RecursionError("decoder nesting")):
            code, report = self.command("check")
        self.assertEqual(code, 2)
        self.assertIn("excessive nesting", report["error"])
        self.assertEqual(self.baseline.read_bytes(), original)

    def test_recursion_failure_preserves_publication(self):
        folder = self.root / "nested"
        folder.mkdir()
        real_listdir = os.listdir
        def traversal_failure(fd):
            if os.fstat(fd).st_ino == folder.stat().st_ino:
                raise RecursionError("injected traversal exhaustion")
            return real_listdir(fd)
        def serialization_failure(data, stream, **kwargs):
            stream.write('{"partial":')
            raise RecursionError("injected serialization exhaustion")
        for target, failure in (("integrity.os.listdir", traversal_failure),
                                ("integrity.json.dump", serialization_failure)):
            for overwrite in (False, True):
                with self.subTest(target=target, overwrite=overwrite):
                    if self.baseline.exists():
                        self.baseline.unlink()
                    if overwrite:
                        self.assertEqual(self.command("baseline")[0], 0)
                        original = self.baseline.read_bytes()
                    before = set(self.base.iterdir())
                    with patch(target, side_effect=failure):
                        code, report = self.command(
                            "baseline", *(["--overwrite"] if overwrite else []))
                    self.assertEqual(code, 2)
                    self.assertIn("excessive nesting", report["error"])
                    self.assertEqual(set(self.base.iterdir()), before)
                    if overwrite:
                        self.assertEqual(self.baseline.read_bytes(), original)
                    else:
                        self.assertFalse(self.baseline.exists())

    def test_validation(self):
        self.command("baseline")
        valid = json.loads(self.baseline.read_text())
        for name in ("/absolute", "../escape", "a/../b", "a//b", "./a", "C:/a"):
            with self.subTest(name=name):
                data = dict(valid, files={name: {"sha256": "0" * 64}})
                self.baseline.write_text(json.dumps(data))
                self.assertEqual(self.command("check")[0], 2)
        for raw in ('{"version":1,"version":1}',
                    '{"files":{"a":{},"a":{}}}',
                    '{"files":{"a":{"sha256":"x","sha256":"y"}}}',
                    '[]', '{broken'):
            self.baseline.write_text(raw)
            self.assertEqual(self.command("check")[0], 2)
        valid["files"]["a"]["sha256"] = "invalid"
        self.baseline.write_text(json.dumps(valid))
        self.assertEqual(self.command("check")[0], 2)

    def test_unrepresentable_filename_refuses_baseline(self):
        (self.root / "back\\slash").touch()
        self.assertEqual(self.command("baseline")[0], 2)
        self.assertFalse(self.baseline.exists())

    def test_skipped_and_tracked_replacements(self):
        self.command("baseline")
        (self.root / "dangling").symlink_to(self.base / "absent")
        (self.root / "directory_link").symlink_to(self.base, target_is_directory=True)
        self.assertEqual(self.command("check")[0], 0)
        (self.root / "a").unlink()
        for kind in ("link", "fifo"):
            if kind == "link":
                (self.root / "a").symlink_to(self.baseline)
            else:
                os.mkfifo(self.root / "a")
            code, report = self.command("check")
            self.assertEqual(code, 2)
            self.assertEqual(report["unverified"], ["a"])
            self.assertEqual(report["missing"], [])
            (self.root / "a").unlink()

    def assert_directory_replacement(self, with_child):
        self.assertEqual(self.command("baseline")[0], 0)
        target = self.root / "a"
        target.unlink()
        target.mkdir()
        if with_child:
            (target / "new.txt").write_text("new contents")
        code, report = self.command("check")
        self.assertEqual(code, 2)
        self.assertEqual(report["unverified"], ["a"])
        self.assertEqual(report["unverified_reasons"]["a"],
                         "type_changed: regular_file -> directory")
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["modified"], [])
        self.assertEqual(report["unreadable"], {})
        self.assertEqual(report["skipped"], {})
        self.assertEqual(report["added"], ["a/new.txt"] if with_child else [])

    def test_tracked_file_replaced_by_empty_directory(self):
        self.assert_directory_replacement(with_child=False)

    def test_tracked_file_replaced_by_directory_with_new_file(self):
        self.assert_directory_replacement(with_child=True)

    def test_unreadable_file(self):
        self.command("baseline")
        with patch("integrity.hash_file", side_effect=PermissionError("denied")):
            code, report = self.command("check")
        self.assertEqual(code, 2)
        self.assertIn("a", report["unreadable"])
        self.assertEqual(report["missing"], [])

    def test_real_permission_denial(self):
        self.command("baseline")
        target = self.root / "a"
        target.chmod(0)
        try:
            if os.access(target, os.R_OK):
                self.skipTest("current privileges bypass file permissions")
            code, report = self.command("check")
            self.assertEqual(code, 2)
            self.assertIn("a", report["unreadable"])
        finally:
            target.chmod(0o600)

    def test_inaccessible_subtree(self):
        folder = self.root / "private"
        folder.mkdir()
        (folder / "file").touch()
        self.command("baseline")
        real_listdir = os.listdir
        inode = folder.stat().st_ino
        def denied(fd):
            if os.fstat(fd).st_ino == inode:
                raise PermissionError("denied")
            return real_listdir(fd)
        with patch("integrity.os.listdir", side_effect=denied):
            code, report = self.command("check")
        self.assertEqual(code, 2)
        self.assertEqual(report["missing"], [])
        self.assertIn("private/file", report["unverified"])

    def test_edit_during_read_and_bounded_reads(self):
        self.command("baseline")
        real_read = os.read
        changed = False
        def editing_read(fd, count):
            nonlocal changed
            self.assertLessEqual(count, integrity.CHUNK_SIZE)
            result = real_read(fd, count)
            if not changed:
                changed = True
                (self.root / "a").write_bytes(b"replacement content")
            return result
        with patch("integrity.os.read", side_effect=editing_read):
            code, report = self.command("check")
        self.assertEqual(code, 2)
        self.assertIn("changed_during_scan", report["unreadable"]["a"])

    def test_symlink_swap_before_open(self):
        self.command("baseline")
        real_hash = integrity.hash_file
        def swapped(fd, name, initial):
            (self.root / name).unlink()
            (self.root / name).symlink_to(self.baseline)
            return real_hash(fd, name, initial)
        with patch("integrity.hash_file", side_effect=swapped), \
                patch("integrity.os.read", side_effect=AssertionError("must not read link")):
            code, report = self.command("check")
        self.assertEqual(code, 2)
        self.assertIn("a", report["unreadable"])


if __name__ == "__main__":
    unittest.main()
