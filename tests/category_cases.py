"""Category integration through real routes, with synthetic rows and no network."""
from copy import deepcopy
from unittest.mock import Mock, patch

from financial_cases import expense
from offline_support import OfflineCase, load_offline_module


class CategoryCases(OfflineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = load_offline_module('app.py', 'offline_tipuach_app')
        cls.module.app.config.update(TESTING=True)

    def context(self, route, rows, month='2026-11', plans=None, budgets=None, filters=None, render=False):
        renderer = Mock(wraps=self.module.render_template) if render else Mock(return_value='offline')
        with (
            patch.object(self.module, 'fetch_expenses', side_effect=lambda: deepcopy(rows)),
            patch.object(self.module, 'fetch_payment_plans_map', return_value=deepcopy(plans or {})),
            patch.object(self.module, 'fetch_budgets_for_month', return_value=deepcopy(budgets or [])),
            patch.object(self.module, 'render_template', renderer),
        ):
            result = self.module.app.test_client().get(route, query_string={'month': month, **(filters or {})})
        self.assertEqual(result.status_code, 200)
        return renderer.call_args.kwargs, result.get_data(as_text=True)

    def test_full_and_quick_forms_and_filters_include_category(self):
        rows = [dict(expense(1, '2026-11-10', 50), category='טיפוח')]
        for route in ('/expenses', '/reports'):
            with self.subTest(route=route):
                _, html = self.context(route, rows, render=True)
                self.assertIn('value="טיפוח"', html)
                self.assertIn('dir="rtl"', html)
        with patch.object(self.module, 'get_expense_by_id', return_value=rows[0]):
            for route in ('/add', '/edit/1'):
                result = self.module.app.test_client().get(route)
                self.assertEqual(result.status_code, 200)
                html = result.get_data(as_text=True)
                self.assertIn('טיפוח', html)
                self.assertIn('>spa</span>', html)
        self.assertEqual(self.module.CATEGORIES.count('טיפוח'), 1)

    def test_add_and_edit_preserve_submitted_category_and_other_fields(self):
        form = {'date': '2026-11-24', 'category': 'טיפוח', 'amount': '50.5',
                'payment_method': 'מקס שלום', 'comment': 'מדומה', 'expense_type': 'single'}
        with patch.object(self.module, 'insert_expense', return_value=[{'id': 123}]) as insert:
            result = self.module.app.test_client().post('/add?return_to=/expenses', data=form)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(insert.call_args.args[:5], ('2026-11-24', 'טיפוח', '50.5', 'מקס שלום', 'מדומה'))
        with (
            patch.object(self.module, 'get_expense_by_id', return_value=expense(1, '2026-11-10', 10)),
            patch.object(self.module, 'update_expense', return_value=True) as update,
            patch.object(self.module, 'upsert_payment_plan', return_value=None),
        ):
            result = self.module.app.test_client().post('/edit/1?return_to=/expenses', data=form)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(update.call_args.args[2], 'טיפוח')

    def test_category_totals_budget_payment_and_three_month_comparison(self):
        rows = [dict(expense(1, '2026-11-10', 50), category='טיפוח'),
                dict(expense(2, '2026-10-10', 30), category='טיפוח'),
                dict(expense(3, '2026-09-10', 20), category='טיפוח'),
                expense(4, '2026-11-11', 80)]
        original = deepcopy(rows)
        for route in ('/expenses', '/reports'):
            context, _ = self.context(route, rows, budgets=[{'category': 'טיפוח', 'amount': 100}],
                                      filters={'category_filter': 'טיפוח', 'payment_filter': 'מזומן', 'expense_type': 'single'})
            self.assertEqual([row['id'] for row in context['expenses']], [1])
            if route == '/reports':
                self.assertEqual(context['category_rows'], [{'category': 'טיפוח', 'spent': 50, 'budget': 100, 'diff': 50}])
                self.assertEqual(context['payment_rows'][0]['total'], 50)
                self.assertEqual([p['amount'] for p in context['category_comparison']['points']], [50, 30, 20])
        self.assertEqual(rows, original)

    def test_no_budget_and_no_expenses_keep_existing_report_behavior(self):
        rows = [dict(expense(1, '2026-11-10', 50), category='טיפוח')]
        context, _ = self.context('/reports', rows)
        self.assertEqual(context['category_rows'][0]['budget'], 0)
        self.assertEqual(context['category_rows'][0]['diff'], -50)
        old, _ = self.context('/reports', rows, month='2026-08')
        self.assertEqual(old['category_rows'], [])
        self.assertEqual(old['summary']['total_spent'], 0)

    def test_standing_and_installments_include_monthly_charge_only(self):
        rows = [dict(expense(1, '2026-10-10', 60, 'standing'), category='טיפוח'),
                dict(expense(2, '2026-10-10', 300, 'installments'), category='טיפוח')]
        plans = {2: {'installments_count': 3, 'payment_amount': 100, 'total_amount': 300}}
        for month, expected in (('2026-10', 160), ('2026-11', 160), ('2026-12', 160), ('2027-01', 60)):
            for route in ('/expenses', '/reports'):
                context, _ = self.context(route, rows, month=month, plans=plans, filters={'category_filter': 'טיפוח'})
                self.assertEqual(sum(row['amount'] for row in context['expenses']), expected)
                self.assertEqual(context['summary']['total_commitments'], expected)
