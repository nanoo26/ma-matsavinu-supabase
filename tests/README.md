# Offline backup, restore and financial checks

From the repository root:

```powershell
python -m unittest discover -s tests -p '*_cases.py' -v
python -m py_compile app.py backup_daily.py restore_backup.py
git diff --check
```

These tests use synthetic financial rows, dummy environment variables and temporary
folders. Dotenv loading is mocked before importing production modules, and real HTTP
requests are blocked. Old-backup cleanup is mocked; the real backup and restore
scripts are not executed. The Windows scheduler test runs a temporary copy against
a fake backup script that only returns an exit code.

`*_cases.py` avoids the repository's existing `test_*.py` ignore rule.

The financial cases protect the 10th-to-9th month boundary, recurring start months,
installment first/last months, totals and rendered RTL pages. Recurring edits now
have a regression case that requires earlier months to retain their original amount.
The remaining `known_gap` case records an installment without a plan appearing
without contributing to commitments. That installment gap is not fixed here.

## Recurring expense history

`recurring_cases.py` exercises real Flask edit/delete routes against a synthetic
REST store. It checks repeated/same-month/backdated edits, stopping and resuming,
prior amounts and profile fields, both month views, optimistic concurrency,
failed/partial API responses, mixed deletion and the rendered form contracts.

Approved additive schema change, migration name `add_recurring_expense_history`:

Applied to the approved Supabase project on 2026-10-10 and verified through column
metadata (types, NOT NULL and defaults). Existing financial rows were not read or
updated by this implementation. The application changes have not been deployed.

```sql
ALTER TABLE public.expenses
  ADD COLUMN recurring_history jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN recurring_revision bigint NOT NULL DEFAULT 0;
```

- The original amount/date/profile stay in the existing row. A sorted timeline
  resolves exactly one profile for each financial month, starting on the 10th.
- An update replaces a version in the same month and preserves later versions.
  A stop preserves versions before its month and cancels all versions from that
  month onward. Saving a new active profile after a stop resumes the expense.
- Each recurring PATCH includes the current revision in its filter, increments
  that revision and validates the returned row. Stale forms or competing writes
  fail without automatically retrying. This protects this app's new edit flow;
  it does not replace database authorization.
- Recurring deletion endpoints stop the series; they never DELETE its base row.
  A submitted month and matching revision are required even for old clients.
  Mixed bulk actions preflight input, then stop on a write failure and report
  partial completion; they are not one database transaction.
- Original recurring dates and types are fixed in this edit flow. To convert
  to an ordinary/installment expense, stop the recurring one and add a separate
  expense. Ordinary edits/deletes and installment calculations retain their flow.
- Empty history preserves the original behavior; no past financial values are
  reconstructed or corrected. Failed/unavailable schema setup blocks recurring
  writes. The two new fields are carried by the existing `select=*` backup.
- Deployment is separate. After history is in use, reverting to older app code
  that ignores it will show incorrect future months and can overwrite base values.
  Retain this history-aware reader for any rollback; do not drop the new fields.

Validation: 57 offline tests passed, plus syntax compilation and `git diff --check`.
A local fixture at a 390px viewport verified editing through the calculator and
saving an effective-month update. The report stop modal displayed the month and
revision; its native confirmation dialog blocked browser automation, so browser
submission of the stop was not verified. Both stop endpoints passed offline route
tests. No real financial data, production writes or production keys were used in
the browser fixture.

## Backup contract and limits

- The existing `expenses`, `budgets` and `payment_plans` tables and JSON row format
  are preserved. This is an application-table export, not a complete database dump
  of schemas, roles, Auth or Storage.
- Every page requests an exact count and orders by `id`. The next offset uses the
  actual number received, even if the server caps pages below the requested size.
  Missing counts, changing counts, repeated IDs and incomplete responses fail.
- Each run uses a new folder. Table files and the code ZIP are published from
  temporary files. `backup_summary.json` is published last and marks completion;
  failed folders have no summary and are omitted by the existing restore picker.
- The code ZIP requires Git and an existing checkout. It uses only tracked files,
  excluding known secret filenames/directories, private keys, CSV/database files, logs,
  archives, environment files and symlinks. Untracked files and Git history are
  omitted. Filename filtering cannot detect secrets embedded in ordinary source.
- Table reads are sequential, not a transactional point-in-time snapshot. Exact
  counts cannot detect every concurrent edit. A future live backup must be taken
  while financial writes are paused; running it requires separate approval.
- No live backup or restore, production key change, RLS change, commit, push or
  deployment is part of these checks. Restorability against an isolated database
  has not yet been verified.

## Restore failure checks

`restore_cases.py` imports the restore module with dotenv disabled and dummy
credentials. All data is synthetic and real HTTP is blocked. The real backup
folders are not read, and the interactive script is not run against a database.

- All three JSON files, unique integer IDs and summary counts are checked before
  the first write. Legacy summaries without `status` remain accepted.
- Missing/corrupt files, failed DELETE/POST requests, timeouts, redirects and
  incomplete or mismatching response IDs stop the run with exit code 1.
- The existing `return=representation` header is retained and its response IDs
  are checked. API response bodies and exception details are not printed.
- Empty tables count as zero. The existing order remains expenses, budgets,
  payment_plans, and POST payloads retain the backup IDs and foreign keys.
- Clearing still targets only IDs present in the backup, rather than the whole
  table. Declining the per-table deletion stops instead of falling through to POST.
- These separate REST requests are not one transaction. A failure may leave
  committed writes or cascading deletions; automatic retry is unsafe. A timeout
  does not establish whether a request committed.

## Planned isolated database verification (not executed)

1. Select an explicitly approved disposable PostgreSQL 17 / PostgREST target.
   Verify its address and project identity differ from production before any
   write. Do not reuse production environment files or credentials.
2. Reproduce the verified column types, identity definitions, constraints,
   foreign keys, grants and policies in that target. Begin with synthetic rows.
   A mock REST response cannot establish compatibility with the actual schema.
3. Resolve identity handling before claiming the current REST restore is usable.
   The earlier catalog inspection found `budgets.id` is `GENERATED ALWAYS`,
   while this script sends explicit IDs. PostgreSQL normally rejects such inserts
   without an override. Do not change production identity definitions to make
   this test pass; any alternative import method requires a reviewed next step.
4. Restore parent expenses before payment plans. Compare stored row counts,
   IDs, foreign keys and exact numeric values privately; do not print datasets.
   Verify that the next generated ID cannot collide with an imported ID.
5. Exercise duplicate IDs, budget identity rejection, restricted policies,
   FK violations, DELETE cascades and failure after the first committed table.
   Verify error reporting and inspect partial state before any retry.
6. Only after synthetic schema checks pass, separately approve using the real
   snapshot in this disposable target. Check its manifest hashes before import.
   Full database/schema/Auth/Storage recovery remains outside this JSON export.

Reference for explicit identity inserts:
https://www.postgresql.org/docs/17/sql-insert.html

### Proposed identity-preserving SQL path

Metadata rechecked on 2026-10-10: all three IDs are bigint identities starting
at 1 and incrementing by 1. `budgets.id` is `ALWAYS`; the other two are
`BY DEFAULT`. The verified FK is `payment_plans.expense_id -> expenses.id`,
with update/delete cascades. These are source facts, not proof of a test target.

The proposed experiment uses an authorized SQL connection in an explicitly
selected, isolated test project. It is separate from the existing REST script
and is not implemented or executed yet. No production identity alteration,
public RPC or new dependency is proposed.

- Fail before import unless the approved target differs from production and
  all three destination tables are empty. Stop if the target schema differs.
  This first experiment does not clear, merge or overwrite existing rows.
- Import explicit column lists and preserved JSON values in one row transaction,
  using `OVERRIDING SYSTEM VALUE` for the `ALWAYS` identity. Preserve all IDs;
  do not regenerate budget IDs or remap expense/payment-plan links. Insert
  expenses before plans and validate counts, IDs, FKs and exact numeric values
  before committing. A failure in the budget/plan phase must roll back all rows.
- With the disposable target still closed to other writes, locate each actual
  identity sequence through PostgreSQL metadata. For a nonempty table, set it
  to at least the maximum imported ID with `is_called=true`. For an empty table
  in this fresh target, retain its verified initial state. Abort on an ID that
  leaves no representable next bigint value.
- Treat sequence adjustment as a separate completion condition: `setval` is
  not rolled back with the row transaction. Report any failed adjustment as an
  incomplete restore and inspect state before retrying. Do not advertise a
  transaction for row data as atomic recovery of the entire database state.
- Test default-ID insertion in each table using synthetic data and verify its
  ID exceeds the imported maximum. Also force a later-table insert failure and
  verify the row transaction left all three original empty tables unchanged.

This environment has no Docker/PostgreSQL executables available on PATH in the
current check. An isolated target must be selected before running the experiment;
no installation or Supabase test-project creation has been performed.

Reference for sequence state and rollback:
https://www.postgresql.org/docs/17/functions-sequence.html
