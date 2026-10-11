"""Savings reserve and isolated persistence with synthetic REST data only."""
from contextlib import ExitStack
from copy import deepcopy
from datetime import date
from unittest.mock import Mock, patch

import requests

from offline_support import OfflineCase, load_offline_module


class SavingsGoalCases(OfflineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = load_offline_module("app.py", "offline_savings_app")
        cls.module.app.config.update(TESTING=True)

    def setUp(self):
        self.rows = [{"id": 1, "month": "2026-10", "category": "שכר שלום", "amount": 1000},
                     {"id": 2, "month": "2026-10", "category": "מזון", "amount": 200},
                     {"id": 3, "month": "2026-09", "category": "יעד חיסכון", "amount": 70}]
        self.writes = []

    def response(self, rows):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = deepcopy(rows)
        return response

    def get(self, url, **kwargs):
        self.assertEqual(url, self.module.SUPABASE_BUDGETS_URL)
        month = kwargs["params"]["month"][3:]
        return self.response([row for row in self.rows if row["month"] == month])

    def insert(self, url, **kwargs):
        self.assertEqual(url, self.module.SUPABASE_BUDGETS_URL)
        self.writes.append(("POST", deepcopy(kwargs)))
        inserted = [dict(row, id=100 + index) for index, row in enumerate(kwargs["json"])]
        self.rows.extend(inserted)
        return self.response(inserted)

    def update(self, url, **kwargs):
        self.assertEqual(url, self.module.SUPABASE_BUDGETS_URL)
        self.writes.append(("PATCH", deepcopy(kwargs)))
        params = kwargs["params"]
        matches = [row for row in self.rows if row["month"] == params["month"][3:]
                   and row["category"] == params["category"][3:]]
        for row in matches:
            row.update(kwargs["json"])
        return self.response(matches)

    def delete(self, url, **kwargs):
        self.assertEqual(url, self.module.SUPABASE_BUDGETS_URL)
        self.writes.append(("DELETE", deepcopy(kwargs)))
        params = kwargs["params"]
        self.assertEqual(params["category"], "neq.יעד חיסכון")
        self.rows = [row for row in self.rows if row["month"] != params["month"][3:]
                     or row["category"] == "יעד חיסכון"]
        return self.response([])

    def mocked_rest(self):
        stack = ExitStack()
        for name, method in (("get", self.get), ("post", self.insert), ("patch", self.update), ("delete", self.delete)):
            stack.enter_context(patch.object(self.module.requests, name, side_effect=method))
        return stack

    def save(self, amount, month="2026-10"):
        result = self.module.app.test_client().post("/budget", data={
            "month": month, "save_savings_goal": "1", "savings_goal": amount,
        })
        self.assertEqual(result.status_code, 302)
        return result

    def test_no_goal_requires_no_record_or_write(self):
        with self.mocked_rest():
            self.save("0")
        self.assertEqual(self.writes, [])

    def test_create_update_and_disable_preserve_other_financial_rows(self):
        original = deepcopy(self.rows)
        with self.mocked_rest():
            for amount, method in (("120", "POST"), ("150.5", "PATCH"), ("0", "PATCH")):
                result = self.save(amount)
                self.assertTrue(result.location.endswith("#savings-goal"))
                self.assertEqual(self.writes[-1][0], method)
                self.assertEqual([row for row in self.rows if row["category"] != "יעד חיסכון"], original[:2])
                current = [row for row in self.rows if row["month"] == "2026-10" and row["category"] == "יעד חיסכון"]
                self.assertEqual(len(current), 1)
                self.assertEqual(current[0]["amount"], float(amount))
                self.assertEqual(self.rows[2], original[2])

    def test_invalid_amount_or_month_never_writes(self):
        with self.mocked_rest():
            for value in ("", "-1", "nan", "inf", "bad"):
                self.save(value)
            for month in ("2026-13", "2026-1", "0000-01", "9999-12"):
                self.save("100", month)
        self.assertEqual(self.writes, [])

    def test_read_failure_blocks_all_budget_writes(self):
        for error in (requests.exceptions.Timeout("synthetic"), requests.exceptions.HTTPError("synthetic")):
            with self.mocked_rest(), patch.object(self.module.requests, "get", side_effect=error):
                self.save("100")
                self.module.app.test_client().post("/budget", data={"month": "2026-10", "income_shalom": "1000"})
            self.assertEqual(self.writes, [])

    def test_save_timeout_or_non_2xx_does_not_delete_or_claim_success(self):
        for existing in (False, True):
            if existing:
                self.rows.append({"id": 4, "month": "2026-10", "category": "יעד חיסכון", "amount": 120})
            method = "patch" if existing else "post"
            original = deepcopy(self.rows)
            for error in (requests.exceptions.Timeout("synthetic"), requests.exceptions.HTTPError("synthetic")):
                with self.mocked_rest(), patch.object(self.module.requests, method, side_effect=error):
                    client = self.module.app.test_client()
                    client.post("/budget", data={"month": "2026-10", "save_savings_goal": "1", "savings_goal": "200"})
                    with client.session_transaction() as session:
                        self.assertTrue(any(category == "error" for category, _ in session["_flashes"]))
                        self.assertFalse(any(category == "success" for category, _ in session["_flashes"]))
                self.assertEqual(self.rows, original)
                self.assertEqual(self.writes, [])

    def test_partial_or_malformed_acknowledgement_is_not_success(self):
        for saved in ([], {}, [{"month": "2026-09", "category": "יעד חיסכון", "amount": 100}],
                      [{"month": "2026-10", "category": "יעד חיסכון", "amount": 99}],
                      [{"month": "2026-10", "category": "יעד חיסכון", "amount": 100}] * 2):
            with self.mocked_rest(), patch.object(self.module.requests, "post", return_value=self.response(saved)):
                client = self.module.app.test_client()
                client.post("/budget", data={"month": "2026-10", "save_savings_goal": "1", "savings_goal": "100"})
                with client.session_transaction() as session:
                    self.assertFalse(any(category == "success" for category, _ in session["_flashes"]))
            self.assertEqual(self.writes, [])

    def test_budget_replacement_keeps_goal_and_failed_delete_stops_insert(self):
        self.rows.append({"id": 4, "month": "2026-10", "category": "יעד חיסכון", "amount": 120})
        with self.mocked_rest():
            self.module.app.test_client().post("/budget", data={"month": "2026-10", "income_shalom": "1000", "budget_מזון": "200"})
        self.assertEqual([row["amount"] for row in self.rows if row["month"] == "2026-10" and row["category"] == "יעד חיסכון"], [120])
        self.assertNotIn("יעד חיסכון", [row["category"] for row in self.writes[-1][1]["json"]])
        with self.mocked_rest(), patch.object(self.module.requests, "delete", side_effect=requests.exceptions.Timeout("synthetic")), patch.object(self.module.requests, "post") as insert:
            self.module.app.test_client().post("/budget", data={"month": "2026-10"})
            insert.assert_not_called()

    def test_goal_is_reserved_once_and_never_counts_as_spending_or_category_budget(self):
        rows = [{"id": 10, "raw_date": "2026-10-10", "amount": 100, "expense_type": "standing", "category": "מזון", "recurring_history": []},
                {"id": 11, "raw_date": "2026-10-10", "amount": 50, "expense_type": "single", "category": "מזון"}]
        class FixtureDate(date):
            @classmethod
            def today(cls):
                return cls(2026, 10, 10)
        for goal in (None, 0, 120, 1200):
            budgets = deepcopy(self.rows[:2])
            if goal is not None:
                budgets.append({"category": "יעד חיסכון", "amount": goal})
            for route in ("/expenses", "/reports"):
                with patch.object(self.module, "date", FixtureDate), patch.object(self.module, "fetch_expenses", return_value=deepcopy(rows)), patch.object(self.module, "fetch_payment_plans_map", return_value={}), patch.object(self.module, "fetch_budgets_for_month", return_value=budgets), patch.object(self.module, "render_template", return_value="offline") as renderer:
                    self.module.app.test_client().get(route, query_string={"month": "2026-10", "category_filter": "בית"})
                context = renderer.call_args.kwargs
                summary = context["summary"]
                self.assertEqual(summary["can_still_spend"], 850 - (goal or 0))
                self.assertAlmostEqual(summary["daily_average"], (850 - (goal or 0)) / 31)
                self.assertEqual(summary["total_commitments"], 100)
                self.assertEqual(summary["total_spent"], 150)
                self.assertEqual(summary["already_spent"], 50)
                self.assertEqual(context.get("total_budget", summary.get("total_budget")), 200)

    def test_invalid_or_duplicate_goals_make_margin_unavailable(self):
        for goals in ([{"category": "יעד חיסכון", "amount": -1}],
                      [{"category": "יעד חיסכון", "amount": float("nan")}],
                      [{"category": "יעד חיסכון", "amount": 100}] * 2):
            with self.module.app.test_request_context("/reports"):
                summary = self.module.monthly_financial_summary([], self.rows[:2] + goals, "2026-10", [])
            self.assertIsNone(summary["can_still_spend"])
            self.assertIn("savings_goal", summary["read_errors"])

    def test_budget_renders_optional_zero_goal_without_saving(self):
        with self.mocked_rest():
            html = self.module.app.test_client().get("/budget?month=2026-10").get_data(as_text=True)
        self.assertIn('id="savings-goal-form"', html)
        self.assertIn('name="savings_goal"', html)
        self.assertIn('min="0"', html)
        self.assertIn("אופציונלי, לחודש הנבחר בלבד", html)
        self.assertEqual(self.writes, [])
