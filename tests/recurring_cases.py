"""Month-based recurring changes through real Flask routes, with fake REST storage."""

from copy import deepcopy
import io
import json
from unittest.mock import Mock, patch

import requests

from financial_cases import expense
from offline_support import OfflineCase, load_offline_module


def response(rows, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(rows).encode('utf-8')
    return result


class RecurringCases(OfflineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = load_offline_module('app.py', 'offline_recurring_app')
        cls.module.app.config.update(TESTING=True)
        cls.real_get_by_id = staticmethod(cls.module.get_expense_by_id)

    def setUp(self):
        self.row = expense(1, '2026-01-09', 100, 'standing')
        self.row.update(date_for_input='2026-01-09', recurring_history=[], recurring_revision=0, installments_count=0)
        self.original = deepcopy(self.row)
        self.store = {1: self.row}
        self.client = self.module.app.test_client()
        self.output = io.StringIO()
        self.patch_calls = []
        for patcher in (
            patch.object(self.module, 'get_expense_by_id', side_effect=lambda identifier: deepcopy(self.store.get(identifier))),
            patch.object(self.module.requests, 'patch', side_effect=self.rest_patch),
            patch('sys.stdout', self.output),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def rest_patch(self, url, **kwargs):
        self.patch_calls.append(kwargs)
        identifier = int(kwargs['params']['id'].split('.')[1])
        row = self.store[identifier]
        if kwargs['params']['recurring_revision'] != f"eq.{row['recurring_revision']}":
            return response([])
        row.update(deepcopy(kwargs['json']))
        return response([deepcopy(row)])

    def edit(self, month, amount=120, **extra):
        form = {'date': self.row['date_for_input'], 'expense_type': 'standing', 'is_fixed': '1',
                'category': 'מזון', 'payment_method': 'מקס שלום', 'comment': 'מדומה',
                'amount': str(amount), 'effective_month': month,
                'recurring_revision': str(self.row['recurring_revision'])}
        form.update(extra)
        return self.client.post('/edit/1?return_to=/expenses', data=form)

    def context(self, route, month):
        renderer = Mock(return_value='offline response')
        with patch.object(self.module, 'fetch_expenses', side_effect=lambda: deepcopy(list(self.store.values()))), patch.object(self.module, 'fetch_payment_plans_map', return_value={}), patch.object(self.module, 'fetch_budgets_for_month', return_value=[]), patch.object(self.module, 'render_template', renderer):
            result = self.client.get(route, query_string={'month': month})
        self.assertEqual(result.status_code, 200)
        return renderer.call_args.kwargs

    def assert_months(self, expected):
        for route in ('/expenses', '/reports'):
            for month, amount in expected.items():
                with self.subTest(route=route, month=month):
                    context = self.context(route, month)
                    key = 'fixed_total_reports' if route == '/reports' else 'fixed_total'
                    self.assertEqual(context[key], amount)
                    self.assertEqual(len(context['fixed_expenses']), int(amount > 0))

    def test_multiple_edits_and_stop_preserve_prior_months_without_duplicate_rows(self):
        self.assertEqual(self.edit('2026-01', 120).status_code, 302)
        self.assertEqual(self.edit('2026-03', 140).status_code, 302)
        self.assertEqual(self.edit('2026-05', recurring_action='stop').status_code, 302)
        self.assert_months({'2025-11': 0, '2025-12': 100, '2026-01': 120, '2026-02': 120, '2026-03': 140, '2026-04': 140, '2026-05': 0, '2026-06': 0})
        for key in ('id', 'amount', 'raw_date', 'category', 'payment_method', 'comment'):
            self.assertEqual(self.row[key], self.original[key])
        self.assertEqual(self.row['recurring_revision'], 3)
        self.assertTrue(all(set(call['json']) == {'recurring_history', 'recurring_revision'} for call in self.patch_calls))

    def test_same_month_replaces_version_and_backdated_edit_preserves_later_versions(self):
        self.edit('2026-03', 150)
        self.edit('2026-01', 120)
        self.edit('2026-01', 125)
        self.assertEqual([entry['from_month'] for entry in self.row['recurring_history']], ['2026-01', '2026-03'])
        self.assert_months({'2025-12': 100, '2026-01': 125, '2026-02': 125, '2026-03': 150})

    def test_profile_changes_do_not_change_prior_category_payment_or_description(self):
        self.edit('2026-01', 120, category='בית', payment_method='שופרסל', comment='פרט מדומה חדש')
        for route in ('/expenses', '/reports'):
            prior = self.context(route, '2025-12')['fixed_expenses'][0]
            updated = self.context(route, '2026-01')['fixed_expenses'][0]
            self.assertEqual((prior['category'], prior['payment_method'], prior['comment']), ('מזון', 'מזומן', 'נתון מדומה'))
            self.assertEqual((updated['category'], updated['payment_method'], updated['comment']), ('בית', 'שופרסל', 'פרט מדומה חדש'))

    def test_stop_cancels_future_edits_and_can_be_explicitly_resumed(self):
        self.edit('2026-03', 150)
        self.edit('2026-05', 160)
        self.edit('2026-02', recurring_action='stop')
        self.assertEqual([entry['from_month'] for entry in self.row['recurring_history']], ['2026-02'])
        self.assert_months({'2026-01': 100, '2026-02': 0, '2026-05': 0})
        self.edit('2026-04', 170)
        self.assert_months({'2026-02': 0, '2026-03': 0, '2026-04': 170, '2026-05': 170})

    def test_backdated_update_does_not_remove_an_existing_later_stop(self):
        self.edit('2026-03', recurring_action='stop')
        self.edit('2026-01', 120)
        self.assert_months({'2025-12': 100, '2026-01': 120, '2026-02': 120, '2026-03': 0})

    def test_start_boundary_invalid_month_amount_and_conversion_never_patch(self):
        for month, amount, extra in (
            ('2025-11', 120, {}), ('', 120, {}), ('2026-13', 120, {}), ('0000-01', 120, {}),
            ('2026-01', 0, {}), ('2026-01', -5, {}), ('2026-01', 'nan', {}), ('2026-01', 'inf', {}),
            ('2026-01', 120, {'expense_type': 'installments'}), ('2026-01', 120, {'date': '2026-02-10'}),
        ):
            with self.subTest(month=month, amount=amount, extra=extra):
                self.assertEqual(self.edit(month, amount, **extra).status_code, 200)
        self.assertEqual(self.patch_calls, [])
        self.assertEqual(self.row, self.original)

    def test_stale_form_and_missing_schema_never_patch(self):
        self.edit('2026-01', 120)
        calls = len(self.patch_calls)
        self.assertEqual(self.edit('2026-02', 130, recurring_revision='0').status_code, 200)
        self.assertEqual(len(self.patch_calls), calls)
        del self.row['recurring_revision']
        form = {'effective_month': '2026-03', 'recurring_action': 'stop', 'recurring_revision': '0'}
        self.assertEqual(self.client.post('/edit/1', data=form).status_code, 200)
        self.assertEqual(len(self.patch_calls), calls)

    def test_database_race_returns_empty_rows_and_does_not_overwrite_other_change(self):
        def racing_patch(url, **kwargs):
            self.row['recurring_revision'] = 1
            self.row['recurring_history'] = [{'from_month': '2026-02', 'active': False}]
            return self.rest_patch(url, **kwargs)
        with patch.object(self.module.requests, 'patch', side_effect=racing_patch):
            page = self.edit('2026-01', 120)
            self.assertEqual(page.status_code, 200)
        self.assertEqual(self.row['recurring_history'], [{'from_month': '2026-02', 'active': False}])
        self.assertIn('ההוצאה השתנתה במקביל', page.get_data(as_text=True))

    def test_api_failures_and_partial_responses_do_not_flash_success_or_expose_data(self):
        for result in (response({'error': 'synthetic-private-key'}, 403), response([]), response([{'id': 1}]), requests.Timeout('synthetic-private-key')):
            with self.subTest(result=type(result).__name__):
                with patch.object(self.module.requests, 'patch', side_effect=result if isinstance(result, Exception) else None, return_value=result) as request_patch:
                    result_page = self.edit('2026-01', 120)
                self.assertEqual(result_page.status_code, 200)
                self.assertEqual(request_patch.call_count, 1)
                self.assertNotIn('עודכנה מהחודש', result_page.get_data(as_text=True))
                self.assertNotIn('synthetic-private-key', result_page.get_data(as_text=True))
        self.assertNotIn('synthetic-private-key', self.output.getvalue())

    def test_delete_routes_stop_recurring_and_never_physically_delete_it(self):
        for route in ('/delete/1', '/delete-selected'):
            with self.subTest(route=route):
                self.row.update(recurring_history=[], recurring_revision=0)
                with patch.object(self.module, 'delete_expense_record') as delete:
                    result = self.client.post(route, data={'selected_ids': '1', 'effective_month': '2026-02', 'recurring_revision': '0'})
                self.assertEqual(result.status_code, 302)
                delete.assert_not_called()
                self.assert_months({'2026-01': 100, '2026-02': 0})

    def test_old_delete_forms_cannot_remove_recurring_history(self):
        for route in ('/delete/1', '/delete-selected'):
            with self.subTest(route=route), patch.object(self.module, 'delete_expense_record') as delete:
                self.client.post(route, data={'selected_ids': '1'})
                delete.assert_not_called()
        self.assertEqual(self.patch_calls, [])

    def test_mixed_bulk_preflight_and_single_expense_deletion(self):
        single = expense(2, '2026-01-10', 20)
        self.store[2] = single
        with patch.object(self.module, 'delete_expense_record') as delete:
            self.client.post('/delete-selected', data={'selected_ids': ['2', '1']})
            delete.assert_not_called()
            self.client.post('/delete-selected', data={'selected_ids': ['2', '1', '1'], 'effective_month': '2026-02', 'recurring_revision_1': '0'})
            delete.assert_called_once_with(2)
        self.assertEqual(len(self.patch_calls), 1)
        with patch.object(self.module, 'delete_expense_record') as delete:
            self.client.post('/delete/2')
            delete.assert_called_once_with(2)

    def test_edit_and_list_templates_expose_month_revision_and_correct_current_profile(self):
        self.edit('2026-01', 120)
        self.edit('2026-03', 140)
        page = self.client.get('/edit/1?month=2026-01').get_data(as_text=True)
        self.assertIn('name="amount" id="amount" value="120.0"', page)
        self.assertIn('name="recurring_revision" value="2"', page)
        self.assertIn('name="effective_month" value="2026-01"', page)
        self.assertIn('readonly', page)
        with patch.object(self.module, 'fetch_expenses', side_effect=lambda: deepcopy([self.row])), patch.object(self.module, 'fetch_payment_plans_map', return_value={}), patch.object(self.module, 'fetch_budgets_for_month', return_value=[]):
            for route in ('/expenses', '/reports'):
                page = self.client.get(route, query_string={'month': '2026-01'}).get_data(as_text=True)
                self.assertIn('data-recurring="1" data-revision="2"', page)
                self.assertIn('month=2026-01', page)
                self.assertIn('id="modal-stop-month"', page)

    def test_fetch_helpers_preserve_history_and_revision(self):
        raw = {'id': 1, 'date': '2026-01-09', 'amount': 100, 'category': 'מזון', 'description': 'מדומה', 'expense_type': 'standing', 'is_fixed': True, 'recurring_revision': 3, 'recurring_history': [{'from_month': '2026-02', 'active': False}]}
        with patch.object(self.module.requests, 'get', return_value=response([raw])):
            fetched = self.module.fetch_expenses()[0]
            self.assertEqual(fetched['recurring_history'], raw['recurring_history'])
            self.assertEqual(fetched['recurring_revision'], 3)
            fetched = self.real_get_by_id(1)
            self.assertEqual(fetched['recurring_history'], raw['recurring_history'])
            self.assertEqual(fetched['recurring_revision'], 3)

    def test_nonrecurring_edit_keeps_existing_update_and_plan_contract(self):
        self.row.update(expense_type='single', is_fixed=False)
        with patch.object(self.module, 'update_expense') as update, patch.object(self.module, 'upsert_payment_plan') as plan:
            result = self.client.post('/edit/1', data={'date': '2026-01-09', 'amount': '20', 'category': 'מזון', 'payment_method': 'מקס שלום', 'comment': 'מדומה', 'expense_type': 'single'})
        self.assertEqual(result.status_code, 302)
        update.assert_called_once_with(1, '2026-01-09', 'מזון', '20', 'מקס שלום', 'מדומה', 'single', False)
        plan.assert_called_once_with(expense_id=1, total_amount=0, installments_count=1)
        self.assertEqual(self.patch_calls, [])

    def test_corrupt_history_cannot_be_replaced_silently(self):
        for history in ({}, [{'from_month': '2026-01', 'active': 'yes'}], [{'from_month': '2026-01', 'active': True, 'amount': 'nan'}], [{'from_month': '2026-02', 'active': False}, {'from_month': '2026-01', 'active': False}]):
            with self.subTest(history=history):
                self.row['recurring_history'] = history
                with self.assertRaises(self.module.RecurringEditError):
                    self.module.save_recurring_change(self.row, '2026-03', '0')
        self.assertEqual(self.patch_calls, [])
