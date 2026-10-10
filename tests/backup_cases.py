"""Backup integration tests using synthetic rows and temporary folders only."""

import io
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import Mock, patch
import zipfile

import requests

from offline_support import OfflineCase, load_offline_module


def response(rows, content_range):
    result = Mock()
    result.headers = {"Content-Range": content_range}
    result.json.return_value = rows
    return result


class BackupCases(OfflineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backup = load_offline_module("backup_daily.py", "offline_backup")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.output = io.StringIO()
        self.stdout = patch("sys.stdout", self.output)
        self.stdout.start()
        self.addCleanup(self.stdout.stop)

    def test_server_cap_does_not_truncate_backup(self):
        rows = [{"id": i, "amount": i / 100, "description": "נתון מדומה"} for i in range(1, 2502)]
        calls = []

        def paged_get(url, **kwargs):
            calls.append(kwargs)
            start = kwargs["params"]["offset"]
            page = rows[start:start + 700]  # Server cap lower than our requested 1000.
            return response(page, f"{start}-{start + len(page) - 1}/{len(rows)}")

        with patch.object(self.backup.requests, "get", side_effect=paged_get):
            self.assertEqual(self.backup.backup_table("expenses", self.folder), 2501)
        saved = json.loads((self.folder / "expenses.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, rows)
        self.assertEqual([call["params"]["offset"] for call in calls], [0, 700, 1400, 2100])
        self.assertTrue(all(call["params"]["order"] == "id.asc" for call in calls))
        self.assertTrue(all(call["headers"]["Prefer"] == "count=exact" for call in calls))
        self.assertFalse((self.folder / "expenses.json.part").exists())

    def test_empty_table_is_a_valid_zero_row_backup(self):
        with patch.object(self.backup.requests, "get", return_value=response([], "*/0")):
            self.assertEqual(self.backup.backup_table("budgets", self.folder), 0)
        self.assertEqual(json.loads((self.folder / "budgets.json").read_text()), [])

    def test_invalid_or_incomplete_pages_are_not_saved(self):
        bad_pages = (
            response([], ""),
            response([], "*/*"),
            response([], "*/2"),
            response([{"id": 1}], "1-1/1"),
            response([{"id": 1}, {"id": 1}], "0-1/2"),
            response([{"id": 2}, {"id": 1}], "0-1/2"),
            response([{"amount": 10}], "0-0/1"),
            response({"error": "synthetic error"}, "0-0/1"),
        )
        for bad_page in bad_pages:
            with self.subTest(page=bad_page.headers["Content-Range"]):
                with patch.object(self.backup.requests, "get", return_value=bad_page):
                    with self.assertRaises(ValueError):
                        self.backup.backup_table("expenses", self.folder)
                self.assertFalse((self.folder / "expenses.json").exists())

    def test_changed_count_and_repeated_page_are_failures(self):
        for second_page in (
            response([{"id": 2}], "1-1/3"),
            response([{"id": 1}], "1-1/2"),
            response([], "*/2"),
        ):
            with self.subTest(page=second_page.headers["Content-Range"]):
                with patch.object(self.backup.requests, "get", side_effect=[response([{"id": 1}], "0-0/2"), second_page]):
                    with self.assertRaises(ValueError):
                        self.backup.backup_table("expenses", self.folder)
                self.assertFalse((self.folder / "expenses.json").exists())

    def test_second_page_http_failure_preserves_existing_file(self):
        existing = self.folder / "expenses.json"
        existing.write_text("[]", encoding="utf-8")
        failed = response([], "*/2")
        failed.raise_for_status.side_effect = requests.HTTPError("synthetic private response")
        with patch.object(self.backup.requests, "get", side_effect=[response([{"id": 1}], "0-0/2"), failed]):
            with self.assertRaises(requests.HTTPError):
                self.backup.backup_table("expenses", self.folder)
        self.assertEqual(existing.read_text(), "[]")

    def test_disk_failure_does_not_publish_partial_table(self):
        with (
            patch.object(self.backup.requests, "get", return_value=response([{"id": 1}], "0-0/1")),
            patch.object(self.backup.json, "dump", side_effect=OSError("synthetic disk full")),
        ):
            with self.assertRaises(OSError):
                self.backup.backup_table("expenses", self.folder)
        self.assertFalse((self.folder / "expenses.json").exists())

    def test_archive_excludes_secrets_even_when_tracked_and_ignores_untracked_files(self):
        project = self.folder / "project"
        project.mkdir()
        inventory = [
            "app.py", "templates/example.html", ".github/workflows/example.yml",
            ".env", ".env.production", "credentials.json", "token.txt", "private.pem",
            "backups/expenses.json", ".aws/config", ".git/config", ".venv/file.py",
            "secrets/password.txt", "setup_and_deploy.bat", ".netrc", "old/file.py", "id_rsa",
        ]
        for name in inventory + ["untracked.py", "financial-data.json"]:
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic content", encoding="utf-8")
        fake_git = subprocess.CompletedProcess([], 0, stdout=("\0".join(inventory) + "\0").encode())
        with (
            patch.object(self.backup, "__file__", str(project / "backup_daily.py")),
            patch.object(self.backup.subprocess, "run", return_value=fake_git) as git,
        ):
            archive = self.backup.create_code_archive(self.folder)
        with zipfile.ZipFile(archive) as saved:
            self.assertEqual(set(saved.namelist()), {"app.py", "templates/example.html", ".github/workflows/example.yml"})
        self.assertEqual(git.call_args.args[0], ["git", "-C", str(project.resolve()), "ls-files", "-z"])

    def test_missing_git_or_invalid_inventory_cannot_publish_archive(self):
        project = self.folder / "project"
        project.mkdir()
        for inventory in (None, "", "../outside.py\0", "missing.py\0"):
            with self.subTest(inventory=inventory):
                fake_git = subprocess.CompletedProcess([], 0, stdout=(inventory or "").encode())
                with (
                    patch.object(self.backup, "__file__", str(project / "backup_daily.py")),
                    patch.object(self.backup.subprocess, "run", return_value=fake_git, side_effect=FileNotFoundError() if inventory is None else None),
                ):
                    with self.assertRaises((FileNotFoundError, ValueError)):
                        self.backup.create_code_archive(self.folder)
                self.assertEqual(list(self.folder.glob("*.zip")), [])

    def test_archive_failure_is_not_success_and_does_not_run_cleanup(self):
        with (
            patch.object(self.backup, "create_backup_folder", return_value=self.folder),
            patch.object(self.backup, "backup_table", return_value=0),
            patch.object(self.backup, "create_code_archive", side_effect=OSError("synthetic secret value")),
            patch.object(self.backup, "create_backup_summary") as summary,
            patch.object(self.backup, "cleanup_old_backups") as cleanup,
        ):
            self.assertEqual(self.backup.main(), 1)
        summary.assert_not_called()
        cleanup.assert_not_called()
        self.assertNotIn("הושלם בהצלחה", self.output.getvalue())
        self.assertNotIn("synthetic secret value", self.output.getvalue())

    def test_table_failure_stops_before_summary_archive_and_cleanup(self):
        failed = response([], "*/0")
        failed.raise_for_status.side_effect = requests.Timeout("synthetic secret value")
        with (
            patch.object(self.backup, "create_backup_folder", return_value=self.folder),
            patch.object(self.backup.requests, "get", side_effect=[response([], "*/0"), failed]) as get,
            patch.object(self.backup, "create_code_archive") as archive,
            patch.object(self.backup, "cleanup_old_backups") as cleanup,
        ):
            self.assertEqual(self.backup.main(), 1)
        self.assertEqual(get.call_count, 2)
        archive.assert_not_called()
        cleanup.assert_not_called()
        self.assertFalse((self.folder / "backup_summary.json").exists())
        self.assertNotIn("הושלם בהצלחה", self.output.getvalue())
        self.assertNotIn("synthetic secret value", self.output.getvalue())

    def test_success_summary_is_written_after_archive_with_counts(self):
        with (
            patch.object(self.backup, "create_backup_folder", return_value=self.folder),
            patch.object(self.backup.requests, "get", side_effect=[
                response([{"id": 1, "amount": 12.34}], "0-0/1"),
                response([], "*/0"), response([{"id": 2, "expense_id": 1}], "0-0/1"),
            ]),
            patch.object(self.backup, "create_code_archive", return_value=self.folder / "code.zip") as archive,
            patch.object(self.backup, "cleanup_old_backups") as cleanup,
        ):
            archive.side_effect = lambda folder: self.assertFalse((folder / "backup_summary.json").exists()) or folder / "code.zip"
            self.assertEqual(self.backup.main(), 0)
        summary = json.loads((self.folder / "backup_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["tables"], {"expenses": 1, "budgets": 0, "payment_plans": 1})
        self.assertEqual(summary["total_records"], 2)
        cleanup.assert_called_once_with(keep_days=30)

    def test_summary_write_failure_leaves_no_success_summary(self):
        with (
            patch.object(self.backup, "create_backup_folder", return_value=self.folder),
            patch.object(self.backup, "backup_table", return_value=0),
            patch.object(self.backup, "create_code_archive", return_value=self.folder / "code.zip"),
            patch.object(self.backup.json, "dump", side_effect=OSError("synthetic disk full")),
            patch.object(self.backup, "cleanup_old_backups") as cleanup,
        ):
            self.assertEqual(self.backup.main(), 1)
        self.assertFalse((self.folder / "backup_summary.json").exists())
        cleanup.assert_not_called()

    def test_backup_folder_collision_never_reuses_existing_backup(self):
        frozen = Mock()
        frozen.now.return_value.strftime.return_value = "2025-12-10_12-00-00-000000"
        with patch.object(self.backup, "datetime", frozen), patch.object(self.backup, "Path", wraps=Path) as paths:
            paths.return_value = self.folder / "backups"
            created = self.backup.create_backup_folder()
            with self.assertRaises(FileExistsError):
                self.backup.create_backup_folder()
        self.assertTrue(created.is_dir())
