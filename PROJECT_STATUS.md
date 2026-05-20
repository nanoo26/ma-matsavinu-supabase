# PROJECT_STATUS

Last verified: 2026-05-19

See `docs/AI_HANDOFF.md` for current project state, recent AI-assisted changes, and safe AI workflow.

## Verified Architecture
- Legacy Flask monolith in `app.py`
- Jinja templates under `templates/`
- CSS-driven UI in `static/`
- Supabase accessed via REST (`requests`), no ORM
- Session-based month selection/state handling

## Current Deployment Setup
- GitHub Actions deploy is active.
- Fly.io production was updated through GitHub Actions.
- Preferred production workflow: commit reviewed changes, push to `main`, and let GitHub Actions deploy to Fly.io.
- Local `fly deploy` from this Windows machine had remote builder / Docker host issues and is not the preferred workflow.
- Fly.io config in `fly.toml`
  - `internal_port = 8080`
  - health check path: `/health`
  - region: `fra`
- Container startup in `Dockerfile` using `gunicorn`
- Additional deployment config exists in `render.yaml`

## Recent Completed Changes
- Add Expense UI improved.
- Edit Expense UI aligned with Add Expense.
- Category `צ'אבי` added and connected to budget/categories.
- Payment method `שופרסל` added.
- Reports ordering fixed: first section newest-to-oldest.
- Chart label escaping fixed for Hebrew/apostrophes/quotes.
- Bottom navigation overlap fixed.
- Reports page: six summary cards relabeled and daily average logic updated. Phase 2 complete.

## Supabase Usage
- Environment-based credentials (`SUPABASE_URL`, `SUPABASE_KEY`)
- Tables used by app and backup flow:
  - `expenses`
  - `budgets`
  - `payment_plans`
- CRUD behavior implemented directly through HTTP calls in backend and scripts

## Backup System
- `backup_daily.py`:
  - Exports Supabase tables to JSON under `backups/`
  - Creates summary/readme artifacts
  - Performs cleanup of old backups
  - Creates ZIP snapshot of project tree (excluding `backups/`)
- `restore_backup.py`:
  - Interactive restore from backup folders
  - Optional data clearing behavior (high-risk operation)
- Operational guidance in `BACKUP_INSTRUCTIONS.md`

## Existing Routes / Features (verified)
- `/` redirect to expenses
- `/health` health endpoint
- `/expenses`
- `/add`
- `/edit/<int:expense_id>`
- `/delete/<int:expense_id>`
- `/delete-selected`
- `/budget`
- `/reports`

## Current Risks
1. Monolithic `app.py` increases regression risk for broad edits.
2. Direct REST data writes/deletes require strict review discipline.
3. Deployment config exists for more than one platform; drift risk.
4. Backup artifacts contain sensitive financial data and require careful handling.
5. Development fallback secret key behavior must never be relied on in production.

## Known Technical Debt
- Single-file backend concentration of routing, domain logic, and data-access concerns
- Tight coupling between templates and CSS classes
- Limited separation between operational scripts and app domain model contracts
- High manual discipline required for safe schema/route evolution

## Recommended Future Direction (Safe, Incremental)
1. Preserve current behavior and add guardrails before refactors.
2. Introduce targeted tests around financial-month calculations and critical routes.
3. Document Supabase table/field contracts explicitly to reduce accidental drift.
4. Add non-destructive validation scripts/checklists for deployment and backup workflows.
5. Split backend responsibilities gradually only when protected by tests and clear parity checks.
