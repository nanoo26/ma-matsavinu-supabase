"""Restore failure and orchestration checks; synthetic rows, no live requests."""

import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import requests

from offline_support import OfflineCase, load_offline_module


def response(rows, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(rows).encode("utf-8")
    return result


class RestoreCases(OfflineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.restore = load_offline_module("restore_backup.py", "offline_restore")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.rows = {
            "expenses": [{"id": 21, "amount": 123.45, "description": "נתון מדומה"}],
            "budgets": [{"id": 31, "category": "מדומה", "amount": 500, "month": "2025-12"}],
            "payment_plans": [{"id": 41, "expense_id": 21, "num_payments": 3}],
        }
        for table, rows in self.rows.items():
            self.save(table, rows)
        self.summary = {
            "status": "complete", "backup_date": "2025-12-10", "backup_time": "12:00:00",
            "tables": {table: len(rows) for table, rows in self.rows.items()},
            "total_records": 3,
        }
        self.backup = {"path": self.folder, "name": "synthetic", "summary": self.summary}
        self.output = io.StringIO()
        stdout = patch("sys.stdout", self.output)
        stdout.start()
        self.addCleanup(stdout.stop)

    def save(self, table, rows):
        (self.folder / f"{table}.json").write_text(json.dumps(rows), encoding="utf-8")

    def run_main(self, answers=("1", "yes", "no")):
        with patch.object(self.restore, "list_backups", return_value=[self.backup]), patch("builtins.input", side_effect=answers):
            return self.restore.main()

    def test_success_preserves_payload_ids_foreign_keys_and_table_order(self):
        with patch.object(self.restore.requests, "post", side_effect=[response(rows) for rows in self.rows.values()]) as post:
            self.assertEqual(self.run_main(), 0)
        self.assertEqual([call.args[0].rsplit("/", 1)[1] for call in post.call_args_list], list(self.rows))
        for call, rows in zip(post.call_args_list, self.rows.values()):
            self.assertEqual(call.kwargs["json"], rows)
            self.assertEqual(call.kwargs["headers"]["Prefer"], "return=representation")
            self.assertEqual(call.kwargs["timeout"], 30)
            self.assertFalse(call.kwargs["allow_redirects"])
        self.assertIn("שחזור הושלם!", self.output.getvalue())

    def test_http_failure_stops_following_tables_without_exposing_error_body(self):
        with patch.object(self.restore.requests, "post", side_effect=[response(self.rows["expenses"]), response({"message": "synthetic-private-key"}, 403)]) as post:
            self.assertEqual(self.run_main(), 1)
        self.assertEqual(post.call_count, 2)
        self.assertNotIn("שחזור הושלם!", self.output.getvalue())
        self.assertNotIn("synthetic-private-key", self.output.getvalue())
        self.assertIn("שחזור חלקי", self.output.getvalue())

    def test_timeout_is_a_failure_without_automatic_retry_or_secret_output(self):
        with patch.object(self.restore.requests, "post", side_effect=requests.Timeout("synthetic-private-key")) as post:
            self.assertEqual(self.run_main(), 1)
        self.assertEqual(post.call_count, 1)
        self.assertNotIn("synthetic-private-key", self.output.getvalue())
        self.assertNotIn("שחזור הושלם!", self.output.getvalue())

    def test_partial_wrong_duplicate_or_invalid_insert_response_is_not_success(self):
        invalid = ([], [{"id": 99}], [{"id": 21}, {"id": 21}], [{"id": "21"}], {}, [{"amount": 123.45}])
        for rows in invalid:
            with self.subTest(rows=rows), patch.object(self.restore.requests, "post", return_value=response(rows)) as post:
                self.assertEqual(self.run_main(), 1)
                self.assertEqual(post.call_count, 1)
        self.assertNotIn("שחזור הושלם!", self.output.getvalue())

    def test_malformed_success_json_is_not_success(self):
        invalid = response([])
        invalid._content = b"synthetic-private-key invalid JSON"
        with patch.object(self.restore.requests, "post", return_value=invalid) as post:
            self.assertEqual(self.run_main(), 1)
        self.assertEqual(post.call_count, 1)
        self.assertNotIn("synthetic-private-key", self.output.getvalue())

    def test_redirect_is_rejected_even_with_matching_response_ids(self):
        with patch.object(self.restore.requests, "post", return_value=response(self.rows["expenses"], 302)) as post:
            self.assertEqual(self.run_main(), 1)
        self.assertEqual(post.call_count, 1)
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_incomplete_summary_metadata_is_reported_without_traceback_or_writes(self):
        self.backup["summary"] = {"tables": {}}
        with patch.object(self.restore.requests, "post") as post:
            self.assertEqual(self.run_main(), 1)
        post.assert_not_called()

    def test_missing_later_table_prevents_all_writes(self):
        (self.folder / "payment_plans.json").unlink()
        with patch.object(self.restore.requests, "post") as post, patch.object(self.restore.requests, "delete") as delete:
            self.assertEqual(self.run_main(), 1)
        post.assert_not_called()
        delete.assert_not_called()

    def test_invalid_later_table_or_count_prevents_all_writes(self):
        invalid = ({}, [{"amount": 5}], [{"id": True}], [{"id": 41}, {"id": 41}], [])
        for rows in invalid:
            with self.subTest(rows=rows):
                self.save("payment_plans", rows)
                with patch.object(self.restore.requests, "post") as post, patch.object(self.restore.requests, "delete") as delete:
                    self.assertEqual(self.run_main(), 1)
                post.assert_not_called()
                delete.assert_not_called()
        (self.folder / "payment_plans.json").write_text("broken JSON", encoding="utf-8")
        with patch.object(self.restore.requests, "post") as post:
            self.assertEqual(self.run_main(), 1)
        post.assert_not_called()

    def test_incomplete_summary_and_invalid_totals_prevent_writes(self):
        for change in ({"status": "failed"}, {"total_records": 4}, {"total_records": True}, {"tables": {"expenses": 1}}, {"tables": {table: True for table in self.rows}}):
            with self.subTest(change=change):
                original = self.backup["summary"]
                self.backup["summary"] = dict(self.summary, **change)
                with patch.object(self.restore.requests, "post") as post:
                    self.assertEqual(self.run_main(), 1)
                post.assert_not_called()
                self.backup["summary"] = original

    def test_legacy_summary_without_status_is_still_accepted(self):
        del self.summary["status"]
        self.restore.validate_backup(self.folder, self.summary)

    def test_empty_tables_are_valid_and_do_not_send_requests(self):
        for table in self.rows:
            self.save(table, [])
        self.summary["tables"] = {table: 0 for table in self.rows}
        self.summary["total_records"] = 0
        with patch.object(self.restore.requests, "post") as post, patch.object(self.restore.requests, "delete") as delete:
            self.assertEqual(self.run_main(), 0)
        post.assert_not_called()
        delete.assert_not_called()
        self.assertIn("שחזור הושלם!", self.output.getvalue())

    def test_delete_failure_stops_before_post_or_later_deletes(self):
        self.save("expenses", [{"id": 21}, {"id": 22}])
        for failure in (response({"message": "synthetic-private-key"}, 500), requests.Timeout("synthetic-private-key")):
            with self.subTest(failure=type(failure).__name__), patch("builtins.input", return_value="yes"):
                with patch.object(self.restore.requests, "delete", side_effect=failure if isinstance(failure, Exception) else None, return_value=failure) as delete, patch.object(self.restore.requests, "post") as post:
                    with self.assertRaises(requests.RequestException):
                        self.restore.restore_table("expenses", self.folder, True)
                self.assertEqual(delete.call_count, 1)
                post.assert_not_called()
        self.assertNotIn("synthetic-private-key", self.output.getvalue())

    def test_unexpected_delete_response_prevents_insert(self):
        for rows in ([{"id": 99}], [{"id": 21}, {"id": 21}], {}):
            with self.subTest(rows=rows), patch("builtins.input", return_value="yes"), patch.object(self.restore.requests, "delete", return_value=response(rows)), patch.object(self.restore.requests, "post") as post:
                with self.assertRaises(ValueError):
                    self.restore.restore_table("expenses", self.folder, True)
                post.assert_not_called()

    def test_clear_deletes_only_backup_ids_and_allows_already_absent_row(self):
        self.save("expenses", [{"id": 21}, {"id": 22}])
        with patch("builtins.input", return_value="yes"), patch.object(self.restore.requests, "delete", side_effect=[response([{"id": 21}]), response([])]) as delete, patch.object(self.restore.requests, "post", return_value=response([{"id": 22}, {"id": 21}])):
            self.assertEqual(self.restore.restore_table("expenses", self.folder, True), 2)
        self.assertEqual([call.kwargs["params"] for call in delete.call_args_list], [{"id": "eq.21"}, {"id": "eq.22"}])

    def test_declined_table_deletion_does_not_continue_with_insert(self):
        with patch("builtins.input", return_value="no"), patch.object(self.restore.requests, "delete") as delete, patch.object(self.restore.requests, "post") as post:
            with self.assertRaises(RuntimeError):
                self.restore.restore_table("expenses", self.folder, True)
        delete.assert_not_called()
        post.assert_not_called()

    def test_invalid_selection_and_cancel_never_write(self):
        for answers, expected in ((["-1"], 1), (["2"], 1), (["invalid"], 1), (["0"], 0), (["1", "no"], 0)):
            with self.subTest(answers=answers), patch.object(self.restore.requests, "post") as post, patch.object(self.restore.requests, "delete") as delete:
                self.assertEqual(self.run_main(answers), expected)
                post.assert_not_called()
                delete.assert_not_called()

    def test_no_backups_or_unreadable_summary_reports_failure(self):
        with patch.object(self.restore, "list_backups", return_value=[]):
            self.assertEqual(self.restore.main(), 1)
        with patch.object(self.restore, "list_backups", side_effect=ValueError("synthetic-private-key")):
            self.assertEqual(self.restore.main(), 1)
        self.assertNotIn("synthetic-private-key", self.output.getvalue())

    def test_unknown_table_is_rejected_before_read_or_write(self):
        with patch.object(self.restore.requests, "post") as post:
            with self.assertRaises(ValueError):
                self.restore.restore_table("unexpected", self.folder)
        post.assert_not_called()
