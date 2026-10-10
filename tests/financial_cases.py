"""Baseline financial behavior only; no writes, dotenv access or live datasets.

The explicitly named known-gap tests document current limitations, not desired behavior.
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

    def context(self, route, month, rows, plans=None, budgets=None):
        renderer = Mock(return_value="offline response")
        with (
            patch.object(self.module, "fetch_expenses", side_effect=lambda: deepcopy(rows)),
            patch.object(self.module, "fetch_payment_plans_map", return_value=deepcopy(plans or {})),
            patch.object(self.module, "fetch_budgets_for_month", return_value=deepcopy(budgets or [])),
            patch.object(self.module, "render_template", renderer),
        ):
            with self.module.app.test_client() as client:
                result = client.get(route, query_string={"month": month})
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

    def test_known_gap_missing_plan_displays_installment_but_not_commitment(self):
        """Known handoff gap; this test records it without changing formulas."""
        context = self.context("/reports", "2025-12", [expense(1, "2025-12-10", 300, "installments")])
        self.assertEqual(context["installment_total"], 300)
        self.assertEqual(context["summary"]["total_commitments"], 0)

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
