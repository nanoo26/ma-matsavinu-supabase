"""Financial regression checks with synthetic data; no writes, dotenv access or live datasets.

The two screens must agree on monthly charges and spending margin.
Run: python -m unittest discover -s tests -p '*_cases.py' -v
"""

from copy import deepcopy
from datetime import date
from unittest.mock import Mock, patch

from offline_support import OfflineCase, load_offline_module


def expense(identifier, raw_date, amount, kind="single"):
    return {
        "id": identifier, "raw_date": raw_date, "date": raw_date,
        "amount": amount, "category": "מזון", "payment_method": "מזומן",
        "comment": "נתון מדומה", "expense_type": kind,
        "is_fixed": kind != "single", "created_at": "2025-12-10T00:00:00Z",
    }


class FinancialCases(OfflineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = load_offline_module("app.py", "offline_financial_app")
        cls.module.app.config.update(TESTING=True)

    def context(self, route, month, rows, plans=None, budgets=None, filters=None):
        renderer = Mock(return_value="offline response")
        with (
            patch.object(self.module, "fetch_expenses", side_effect=lambda: deepcopy(rows)),
            patch.object(self.module, "fetch_payment_plans_map", return_value=deepcopy(plans or {})),
            patch.object(self.module, "fetch_budgets_for_month", return_value=deepcopy(budgets or [])),
            patch.object(self.module, "render_template", renderer),
        ):
            with self.module.app.test_client() as client:
                result = client.get(route, query_string={"month": month, **(filters or {})})
        self.assertEqual(result.status_code, 200)
        renderer.assert_called_once()
        context = renderer.call_args.kwargs
        if route == "/reports":
            # Preserve and explicitly check the existing reports template contract.
            for name in ("single_total", "fixed_total", "installment_total"):
                context[name] = context[f"{name}_reports"]
        return context

    def test_financial_month_boundary_and_year_rollover(self):
        for day, expected in (
            (date(2025, 12, 9), (2025, 11)),
            (date(2025, 12, 10), (2025, 12)),
            (date(2026, 1, 9), (2025, 12)),
            (date(2026, 1, 10), (2026, 1)),
        ):
            with self.subTest(day=day):
                self.assertEqual(self.module.financial_label_for_date(day), expected)
        self.assertEqual(self.module.financial_range_for_month("2025-12"), (date(2025, 12, 10), date(2026, 1, 9)))
        self.assertEqual(self.module.financial_range_for_month("2024-02"), (date(2024, 2, 10), date(2024, 3, 9)))

    def test_recurring_expense_starts_in_its_financial_month(self):
        rows = [expense(1, "2026-01-09", 100, "standing")]
        for route in ("/expenses", "/reports"):
            for month, total in (("2025-11", 0), ("2025-12", 100), ("2026-01", 100)):
                with self.subTest(route=route, month=month):
                    context = self.context(route, month, rows)
                    self.assertEqual(context["fixed_total"], total)

    def test_installments_first_last_and_outside_months(self):
        rows = [expense(1, "2025-12-09", 300, "installments")]
        plans = {1: {"installments_count": 3, "payment_amount": 100, "total_amount": 300}}
        for route in ("/expenses", "/reports"):
            for month, installment in (("2025-10", None), ("2025-11", 1), ("2025-12", 2), ("2026-01", 3), ("2026-02", None)):
                with self.subTest(route=route, month=month):
                    context = self.context(route, month, rows, plans)
                    rendered = context["installment_expenses"]
                    self.assertEqual(context["installment_total"], 0 if installment is None else 100)
                    if installment is not None:
                        self.assertEqual(len(rendered), 1)
                        self.assertEqual(rendered[0]["current_installment"], installment)
                        self.assertEqual(rendered[0]["total_installments"], 3)
                    else:
                        self.assertEqual(rendered, [])

    def test_installment_amount_fallback_uses_total_and_count(self):
        rows = [expense(1, "2025-12-10", 123.45, "installments")]
        plans = {1: {"installments_count": 3, "payment_amount": 0, "total_amount": 123.45}}
        for route in ("/expenses", "/reports"):
            context = self.context(route, "2025-12", rows, plans)
            self.assertAlmostEqual(context["installment_total"], 41.15, places=2)

    def test_both_routes_preserve_month_totals_and_budget_income(self):
        rows = [
            expense(1, "2025-12-09", 10), expense(2, "2025-12-10", 100, "standing"),
            expense(3, "2025-12-09", 300, "installments"), expense(4, "2025-12-10", 20),
            expense(5, "2026-01-09", 30), expense(6, "2026-01-10", 40),
        ]
        plans = {3: {"installments_count": 3, "payment_amount": 100, "total_amount": 300}}
        budgets = [{"category": "שכר שלום", "amount": 1000}, {"category": "מזון", "amount": 500}]
        for route in ("/expenses", "/reports"):
            with self.subTest(route=route):
                context = self.context(route, "2025-12", rows, plans, budgets)
                self.assertEqual({row["id"] for row in context["expenses"]}, {2, 3, 4, 5})
                self.assertEqual((context["single_total"], context["fixed_total"], context["installment_total"]), (50, 100, 100))
                income = context["summary"]["total_income"] if route == "/reports" else context["total_income"]
                self.assertEqual(income, 1000)
                if route == "/reports":
                    self.assertEqual(context["summary"]["total_commitments"], 200)
                    self.assertEqual(context["summary"]["can_still_spend"], 750)

    def test_recurring_history_preserves_amount_in_earlier_months(self):
        row = expense(1, "2025-12-10", 100, "standing")
        row["recurring_history"] = [{"from_month": "2026-01", "active": True, "amount": "120", "category": "מזון", "payment_method": "מזומן", "comment": "מדומה"}]
        for route in ("/expenses", "/reports"):
            old = self.context(route, "2025-12", [row])
            edited = self.context(route, "2026-01", [row])
            self.assertEqual(old["fixed_total"], 100)
            self.assertEqual(edited["fixed_total"], 120)
        self.assertEqual(row["amount"], 100)

    def test_missing_plan_blocks_margin_without_treating_purchase_total_as_monthly(self):
        for route in ("/expenses", "/reports"):
            for month in ("2025-12", "2026-01"):
                context = self.context(route, month, [expense(1, "2025-12-10", 300, "installments")])
                self.assertEqual(context["installment_total"], 0)
                self.assertEqual(len(context["unresolved_expenses"]), 1)
                self.assertFalse(context["summary"]["complete"])
                self.assertIsNone(context["summary"]["can_still_spend"])
            before = self.context(route, "2025-11", [expense(1, "2025-12-10", 300, "installments")])
            self.assertTrue(before["summary"]["complete"])

    def test_filtered_lists_do_not_change_the_monthly_margin(self):
        rows = [expense(1, "2025-12-10", 100, "standing"),
                expense(2, "2025-12-11", 20), expense(3, "2025-12-12", 30)]
        rows[2]["category"] = "בית"
        budgets = [{"category": "שכר שלום", "amount": 1000}]
        for route in ("/expenses", "/reports"):
            for filters in ({"category_filter": "בית"}, {"expense_type": "single"}, {"payment_filter": "לא קיים"}):
                context = self.context(route, "2025-12", rows, budgets=budgets, filters=filters)
                self.assertEqual(context["summary"]["can_still_spend"], 850)
                self.assertEqual(context["summary"]["already_spent"], 50)
                self.assertEqual(context["summary"]["total_spent"], 150)
            filtered = self.context(route, "2025-12", rows, budgets=budgets, filters={"category_filter": "בית"})
            self.assertEqual(filtered["single_total"], 30)

    def test_one_payment_is_not_a_recurring_commitment(self):
        rows = [expense(1, "2025-12-10", 300, "installments")]
        plans = {1: {"installments_count": 1, "payment_amount": 300, "total_amount": 300}}
        for route in ("/expenses", "/reports"):
            active = self.context(route, "2025-12", rows, plans)
            ended = self.context(route, "2026-01", rows, plans)
            self.assertEqual(active["summary"]["total_commitments"], 300)
            self.assertEqual(ended["installment_total"], 0)
            self.assertTrue(ended["summary"]["complete"])

    def test_invalid_plan_amount_or_count_cannot_produce_available_money(self):
        row = expense(1, "2025-12-10", 300, "installments")
        for plan in ({"installments_count": 0, "payment_amount": 100},
                     {"installments_count": 3.5, "payment_amount": 100},
                     {"installments_count": 3, "payment_amount": float("nan")},
                     {"installments_count": 3, "payment_amount": -1, "total_amount": 0}):
            for route in ("/expenses", "/reports"):
                context = self.context(route, "2025-12", [row], {1: plan})
                self.assertIsNone(context["summary"]["can_still_spend"])
                self.assertIsNone(context["summary"]["daily_average"])
                self.assertEqual(context["summary"]["known_total_spent"], 0)

    def test_invalid_dates_amounts_and_recurring_history_are_visible_as_incomplete(self):
        for row in (expense(1, "unknown", 100), expense(1, "2025-12-10", float("inf")),
                    dict(expense(1, "2025-12-10", 100, "standing"), recurring_history="invalid")):
            for route in ("/expenses", "/reports"):
                context = self.context(route, "2025-12", [row])
                self.assertFalse(context["summary"]["complete"])
                self.assertEqual(len(context["unresolved_expenses"]), 1)

    def test_daily_margin_includes_today_and_preserves_deficit(self):
        for today, month, expected_days in ((date(2026, 10, 10), "2026-10", 31),
                                            (date(2026, 11, 9), "2026-10", 1),
                                            (date(2024, 2, 29), "2024-02", 10),
                                            (date(2026, 1, 1), "2025-12", 9)):
            class FixtureDate(date):
                @classmethod
                def today(cls):
                    return today
            with patch.object(self.module, "date", FixtureDate):
                for route in ("/expenses", "/reports"):
                    summary = self.context(route, month, [], budgets=[{"category": "שכר שלום", "amount": 310}])["summary"]
                    self.assertEqual(summary["days_remaining"], expected_days)
                    self.assertAlmostEqual(summary["daily_average"], 310 / expected_days)
                summary = self.context("/reports", "2020-01", [expense(1, "2020-01-10", 50)])["summary"]
                self.assertEqual(summary["can_still_spend"], -50)
                self.assertIsNone(summary["usage_percent"])
                self.assertIsNone(summary["daily_average"])

    def test_failed_reads_do_not_appear_as_an_empty_month(self):
        import requests
        for route in ("/expenses", "/reports"):
            for method in ("fetch_expenses", "fetch_payment_plans_map", "fetch_budgets_for_month"):
                real_fetch = getattr(self.module, method)
                response = Mock()
                response.raise_for_status.side_effect = requests.exceptions.HTTPError("synthetic failure")
                kwargs = {"fetch_expenses": Mock(return_value=[]), "fetch_payment_plans_map": Mock(return_value={}), "fetch_budgets_for_month": Mock(return_value=[])}
                kwargs[method] = real_fetch
                with patch.multiple(self.module, **kwargs), patch.object(self.module.requests, "get", return_value=response), patch.object(self.module, "render_template", return_value="offline") as renderer:
                    self.module.app.test_client().get(route, query_string={"month": "2025-12"})
                summary = renderer.call_args.kwargs["summary"]
                self.assertFalse(summary["complete"])
                self.assertIsNone(summary["can_still_spend"])
                self.assertTrue(summary["read_errors"])

    def test_timeout_malformed_and_invalid_numeric_reads_block_margin(self):
        import requests
        for method in ("fetch_expenses", "fetch_payment_plans_map", "fetch_budgets_for_month"):
            real_fetch = getattr(self.module, method)
            for case in ("timeout", "malformed"):
                response = Mock()
                response.raise_for_status.return_value = None
                response.json.return_value = {"unexpected": "response"}
                kwargs = {"fetch_expenses": Mock(return_value=[]), "fetch_payment_plans_map": Mock(return_value={}), "fetch_budgets_for_month": Mock(return_value=[])}
                kwargs[method] = real_fetch
                with patch.multiple(self.module, **kwargs), patch.object(self.module.requests, "get", side_effect=requests.exceptions.Timeout("synthetic") if case == "timeout" else None, return_value=response), patch.object(self.module, "render_template", return_value="offline") as renderer:
                    self.module.app.test_client().get("/reports", query_string={"month": "2025-12"})
                self.assertIsNone(renderer.call_args.kwargs["summary"]["can_still_spend"])

    def test_fetch_rejects_fractional_installment_count(self):
        response = Mock()
        response.json.return_value = [{"expense_id": 1, "installments_count": 3.5, "payment_amount": 100}]
        with patch.object(self.module.requests, "get", return_value=response):
            self.assertEqual(self.module.fetch_payment_plans_map()[1]["installments_count"], 0)

    def test_normalized_installments_and_legacy_fixed_flags_agree(self):
        rows = [dict(expense(1, "2025-12-10", 300), expense_type="תשלומים"),
                dict(expense(2, "2025-12-10", 100), is_fixed=True)]
        plans = {1: {"installments_count": 3, "payment_amount": 100}}
        for route in ("/expenses", "/reports"):
            context = self.context(route, "2026-01", rows, plans, filters={"category_filter": "fixed_and_installments"})
            self.assertEqual(context["summary"]["total_commitments"], 200)
            self.assertEqual((context["fixed_total"], context["installment_total"]), (100, 100))

    def test_incomplete_templates_show_warning_and_edit_link(self):
        with patch.object(self.module, "fetch_expenses", return_value=[expense(1, "2025-12-10", 300, "installments")]), patch.object(self.module, "fetch_payment_plans_map", return_value={}), patch.object(self.module, "fetch_budgets_for_month", return_value=[]):
            for route in ("/expenses", "/reports"):
                result = self.module.app.test_client().get(route, query_string={"month": "2025-12"})
                html = result.get_data(as_text=True)
                self.assertEqual(result.status_code, 200)
                self.assertIn("חסר מידע לחישוב המרווח", html)
                self.assertIn('/edit/1?', html)

    def test_templates_render_with_synthetic_financial_data(self):
        with (
            patch.object(self.module, "fetch_expenses", side_effect=lambda: [expense(1, "2025-12-10", 12.34)]),
            patch.object(self.module, "fetch_payment_plans_map", return_value={}),
            patch.object(self.module, "fetch_budgets_for_month", return_value=[]),
        ):
            with self.module.app.test_client() as client:
                for route in ("/expenses", "/reports"):
                    with self.subTest(route=route):
                        result = client.get(route, query_string={"month": "2025-12"})
                        self.assertEqual(result.status_code, 200)
                        self.assertIn('dir="rtl"', result.get_data(as_text=True))
