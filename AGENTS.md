# AGENTS.md - Safety Guardrails for Ma Matsavinu

## Scope
This repository is a legacy financial Flask + Supabase app. Treat it as production-sensitive.

## Core Rules
1. Inspect first, then propose, then implement.
2. Do not assume missing behavior, schema, routes, or business logic.
3. Keep changes minimal, scoped, and reversible.
4. Prefer existing project patterns over new abstractions.
5. No destructive operations without explicit user approval.

## Mandatory Pre-Change Workflow
1. Run `git status --short --branch`.
2. Confirm the working tree state.
3. Read these files before planning changes:
   - `README.md`
   - `ChatGPT_Agent_Project_Instructions.md`
   - `BACKUP_INSTRUCTIONS.md`
   - `.github/copilot-instructions.md` (if present)
4. Inspect impacted files before proposing edits.
5. Report risks and affected files before implementation.
6. Wait for explicit approval when changes are risky or broad.

## Architecture Guardrails (Flask/Jinja)
1. `app.py` is a monolith and source of truth for routes and business logic.
2. Preserve existing route names, request fields, response shapes, and template variable contracts.
3. Do not redesign architecture unless explicitly requested.
4. Preserve Hebrew/RTL and mobile-first behavior in user-facing templates.

## Supabase REST Safety Guardrails
1. Data access is direct REST (`requests`) with environment credentials.
2. Do not change table names, column names, or query semantics without explicit instruction.
3. Do not log or expose keys, tokens, or sensitive payloads.
4. Treat write/delete operations as high risk; require explicit intent for bulk or destructive changes.
5. Validate failure paths (timeouts, non-2xx, partial responses) when touching request logic.

## Financial Data Protection
1. Financial records are sensitive; minimize data movement and output.
2. Never print full financial datasets in logs or chat responses.
3. Avoid writing ad-hoc exports unless explicitly requested.
4. Preserve current financial month logic and reporting semantics unless explicitly requested.

## Backup/Restore Safety
1. `backup_daily.py` and `restore_backup.py` are operationally sensitive.
2. Do not modify backup/restore behavior without explicit approval.
3. Any restore flow that can overwrite or clear data requires explicit user confirmation.
4. Treat backup artifacts as sensitive data and avoid unnecessary duplication.

## Deployment Safety (Fly.io / Runtime)
1. Deployment-critical files:
   - `fly.toml`
   - `Dockerfile`
   - `render.yaml`
2. Do not change deployment ports, health checks, startup command, or env variable contracts unless explicitly requested.
3. Preserve `/health` behavior for platform health checks.

## Forbidden-by-Default Actions
1. No `git reset --hard`, forced checkouts, or mass deletes.
2. No schema/migration/deployment changes without explicit request.
3. No package/dependency changes without explicit request.
4. No commit/push/tag/release actions unless explicitly requested.

## Validation Expectations
1. After code changes, run the project's existing validation commands.
2. If commands are unknown, inspect docs and propose a safe validation plan first.
3. Always report:
   - modified files
   - validations executed
   - residual risks
