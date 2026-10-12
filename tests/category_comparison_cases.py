"""Category history and unfiltered home behavior with synthetic, offline records."""
from copy import deepcopy
from datetime import date
from unittest.mock import Mock, patch

from financial_cases import expense
from offline_support import OfflineCase, load_offline_module


class CategoryComparisonCases(OfflineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = load_offline_module('app.py', 'offline_category_comparison_app')
        cls.module.app.config.update(TESTING=True)

    def report(self, rows, month='2026-10', plans=None, filters=None, failed=None):
        renderer = Mock(return_value='offline')
        def fetch_rows():
            if failed:
                self.module.mark_financial_read_failure(failed)
            return deepcopy(rows)
        with (
            patch.object(self.module, 'fetch_expenses', side_effect=fetch_rows) as expense_read,
            patch.object(self.module, 'fetch_payment_plans_map', return_value=deepcopy(plans or {})) as plan_read,
            patch.object(self.module, 'fetch_budgets_for_month', return_value=[]),
            patch.object(self.module, 'render_template', renderer),
        ):
            response = self.module.app.test_client().get('/reports', query_string={
                'month': month, 'category_filter': 'מזון', **(filters or {})})
        self.assertEqual(response.status_code, 200)
        expense_read.assert_called_once()
        plan_read.assert_called_once()
        return renderer.call_args.kwargs

    def test_financial_boundaries_and_year_rollover(self):
        rows = [expense(1, '2026-01-09', 150), expense(2, '2025-12-09', 80),
                expense(3, '2025-11-09', 40), expense(4, '2026-01-10', 900)]
        comparison = self.report(rows, month='2025-12')['category_comparison']
        self.assertEqual([(p['month'], p['amount']) for p in comparison['points']],
                         [('2025-12', 150), ('2025-11', 80), ('2025-10', 40)])
        self.assertEqual(comparison['change'], 70)
        self.assertEqual(comparison['points'][0]['range'], '10/12/2025 – 09/01/2026')

    def test_monthly_installment_and_historical_recurring_amounts(self):
        fixed = expense(1, '2025-12-10', 100, 'standing')
        fixed['recurring_history'] = [{'from_month': '2026-01', 'active': True, 'amount': 120,
                                      'category': 'מזון', 'payment_method': 'מזומן', 'comment': 'מדומה'}]
        rows = [fixed, expense(2, '2025-11-10', 300, 'installments')]
        plans = {2: {'installments_count': 3, 'payment_amount': 100, 'total_amount': 300}}
        comparison = self.report(rows, month='2026-01', plans=plans)['category_comparison']
        self.assertEqual([p['amount'] for p in comparison['points']], [220, 200, 100])
        self.assertEqual(self.report(rows, month='2026-02', plans=plans)['category_comparison']['points'][0]['amount'], 120)
        self.assertEqual(fixed['amount'], 100)

    def test_all_filters_apply_to_all_three_months(self):
        rows = [dict(expense(1, '2026-10-10', 30), payment_method='מקס שלום'),
                expense(2, '2026-10-11', 50),
                dict(expense(3, '2026-09-10', 70), payment_method='מקס שלום'),
                dict(expense(4, '2026-08-10', 20), payment_method='מקס שלום'),
                dict(expense(5, '2026-10-10', 500, 'standing'), payment_method='מקס שלום'),
                dict(expense(6, 'bad-date', 500), category='בית', payment_method='מקס שלום')]
        comparison = self.report(rows, filters={'payment_filter': 'מקס שלום', 'expense_type': 'single'})['category_comparison']
        self.assertEqual([p['amount'] for p in comparison['points']], [30, 70, 20])

    def test_missing_plan_is_unknown_and_does_not_become_zero(self):
        comparison = self.report([expense(1, '2026-10-10', 300, 'installments')])['category_comparison']
        self.assertEqual([p['amount'] for p in comparison['points']], [None, 0, 0])
        self.assertIsNone(comparison['change'])

    def test_payment_only_combines_categories_and_preserves_type_filter(self):
        rows = [dict(expense(1, '2026-10-10', 30), payment_method='מקס שלום'),
                dict(expense(2, '2026-10-11', 50), category='בית', payment_method='מקס שלום'),
                expense(3, '2026-10-12', 900),
                dict(expense(4, '2026-09-10', 70), category='רכב', payment_method='מקס שלום'),
                dict(expense(5, '2026-08-10', 20), payment_method='מקס שלום'),
                dict(expense(6, '2026-08-10', 100, 'standing'), category='בית', payment_method='מקס שלום')]
        filters = {'category_filter': '', 'payment_filter': 'מקס שלום'}
        comparison = self.report(rows, filters=filters)['category_comparison']
        self.assertEqual(comparison['label'], 'מקס שלום')
        self.assertEqual([p['amount'] for p in comparison['points']], [180, 170, 120])
        singles = self.report(rows, filters={**filters, 'expense_type': 'single'})['category_comparison']
        self.assertEqual([p['amount'] for p in singles['points']], [80, 70, 20])
        combined = self.report(rows, filters={'payment_filter': 'מקס שלום'})['category_comparison']
        self.assertEqual(combined['label'], 'מזון · מקס שלום')
        self.assertEqual([p['amount'] for p in combined['points']], [30, 0, 20])

    def test_payment_only_missing_plan_and_read_failures_remain_unknown(self):
        filters = {'category_filter': '', 'payment_filter': 'מקס שלום'}
        other_card = expense(1, '2026-10-10', 300, 'installments')
        comparison = self.report([other_card], filters=filters)['category_comparison']
        self.assertEqual([p['amount'] for p in comparison['points']], [0, 0, 0])
        matching_card = dict(other_card, payment_method='מקס שלום')
        comparison = self.report([matching_card], filters=filters)['category_comparison']
        self.assertEqual([p['amount'] for p in comparison['points']], [None, 0, 0])
        self.assertIsNone(comparison['change'])
        comparison = self.report([], filters=filters, failed='expenses')['category_comparison']
        self.assertEqual([p['amount'] for p in comparison['points']], [None, None, None])

    def test_read_failure_blocks_comparison_but_budget_failure_does_not(self):
        for failure in ('expenses', 'plans'):
            comparison = self.report([], failed=failure)['category_comparison']
            self.assertEqual([p['amount'] for p in comparison['points']], [None, None, None])
        comparison = self.report([expense(1, '2026-10-10', 30)], failed='budgets')['category_comparison']
        self.assertEqual([p['amount'] for p in comparison['points']], [30, 0, 0])

    def test_special_recurring_filter_and_empty_known_category(self):
        rows = [dict(expense(1, '2026-08-10', 100, 'standing'), category='בית'),
                expense(2, '2026-10-10', 50)]
        comparison = self.report(rows, filters={'category_filter': 'fixed_only'})['category_comparison']
        self.assertEqual(comparison['label'], 'קבועות בלבד')
        self.assertEqual([p['amount'] for p in comparison['points']], [100, 100, 100])
        empty = self.report(rows, filters={'category_filter': 'רכב'})['category_comparison']
        self.assertEqual([p['amount'] for p in empty['points']], [0, 0, 0])
        self.assertEqual([p['bar_percent'] for p in empty['points']], [0, 0, 0])

    def test_type_only_comparison_includes_all_categories_for_each_month(self):
        rows = [expense(1, '2026-10-10', 20),
                dict(expense(2, '2026-10-11', 10), category='בית'),
                expense(3, '2026-09-10', 40), expense(4, '2026-08-10', 50),
                dict(expense(5, '2026-08-10', 70, 'standing'), category='רכב'),
                dict(expense(6, '2026-08-10', 300, 'installments'), category='בית')]
        plans = {6: {'installments_count': 3, 'payment_amount': 100, 'total_amount': 300}}
        for kind, label, totals in (('single', 'חד־פעמיות', [30, 40, 50]),
                                    ('standing', 'קבועות', [70, 70, 70]),
                                    ('installments', 'תשלומים', [100, 100, 100])):
            with self.subTest(kind=kind):
                comparison = self.report(rows, plans=plans, filters={
                    'category_filter': '', 'expense_type': kind})['category_comparison']
                self.assertEqual(comparison['label'], label)
                self.assertEqual([p['amount'] for p in comparison['points']], totals)
        combined = self.report(rows, plans=plans, filters={'expense_type': 'single'})['category_comparison']
        self.assertEqual(combined['label'], 'מזון · חד־פעמיות')
        self.assertEqual([p['amount'] for p in combined['points']], [20, 40, 50])

    def test_unfiltered_report_keeps_existing_summary_without_comparison(self):
        context = self.report([expense(1, '2026-10-10', 50)], filters={'category_filter': ''})
        self.assertIsNone(context['category_comparison'])
        self.assertEqual(context['summary']['total_spent'], 50)

    def test_home_after_filtered_report_shows_all_kinds_of_same_month(self):
        rows = [expense(1, '2026-08-10', 20), dict(expense(2, '2026-08-11', 30), category='בית'),
                expense(3, '2026-07-10', 100, 'standing'), expense(4, '2026-08-10', 300, 'installments'),
                expense(5, '2026-09-10', 999)]
        plans = {4: {'installments_count': 3, 'payment_amount': 100, 'total_amount': 300}}
        renderer = Mock(return_value='offline')
        with patch.object(self.module, 'fetch_expenses', return_value=deepcopy(rows)), \
             patch.object(self.module, 'fetch_payment_plans_map', return_value=plans), \
             patch.object(self.module, 'fetch_budgets_for_month', return_value=[]), \
             patch.object(self.module, 'render_template', renderer):
            client = self.module.app.test_client()
            client.get('/reports?month=2026-08&category_filter=מזון&expense_type=single')
            self.assertEqual(client.get('/', follow_redirects=True).status_code, 200)
        home = renderer.call_args.kwargs
        self.assertEqual(home['selected_month'], '2026-08')
        self.assertEqual({row['id'] for row in home['expenses']}, {1, 2, 3, 4})
        self.assertEqual(home['total_amount'], 250)
        self.assertEqual((home['category_filter'], home['payment_filter'], home['expense_type']), ('', '', ''))
