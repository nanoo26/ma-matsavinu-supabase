# START_HERE

## Purpose
Quick onboarding for safe work on this legacy Flask + Supabase + Fly.io financial app.

## Read First (in order)
1. `README.md`
2. `AGENTS.md`
3. `ChatGPT_Agent_Project_Instructions.md`
4. `BACKUP_INSTRUCTIONS.md`
5. `.github/copilot-instructions.md` (if present)

## Project Snapshot
- Backend: `app.py` (Flask monolith with routes + business logic)
- Frontend: `templates/` (Jinja), `static/style.css`
- Data: Supabase REST via `requests` (no ORM)
- Runtime: `gunicorn` on port `8080`

## Deployment Overview
- Primary deployment config: `fly.toml` + `Dockerfile`
- Health endpoint: `/health` (must remain stable for platform checks)
- Also present: `render.yaml` (secondary/legacy deployment config, keep aligned intentionally)

## Fly.io + Supabase Safety Notes
- Env contract must remain stable: `SUPABASE_URL`, `SUPABASE_KEY`, `SECRET_KEY`
- Supabase writes/deletes are high risk; avoid broad data mutations without explicit approval
- Do not change deployment ports, health checks, or startup command without explicit request

## Dangerous Files / Areas
- `app.py` (financial logic, routes, data writes/deletes)
- `backup_daily.py`, `restore_backup.py` (operational data safety)
- `fly.toml`, `Dockerfile`, `render.yaml` (deployment-critical)
- `templates/` + `static/` (user-facing RTL/mobile behavior coupling)

## Validation Flow
1. Run `git status --short --branch`
2. Inspect impacted files before edits
3. Apply minimal scoped change
4. Run relevant validation/smoke checks
5. Re-run `git status --short --branch`
6. Report changed files, validation, and risks

## Model Guidance
- **Claude Sonnet**: preferred for focused UI polish in `templates/` and `static/` while preserving RTL/mobile conventions.
- **GPT-5.3-Codex**: preferred for backend debugging, safety-critical logic review, deployment checks, and cross-file risk analysis.

## Default Working Style
- Inspect-first
- No assumptions
- Minimal blast radius
- No destructive actions without explicit approval
