# Release Checklist Prompt Template

## Release Scope
[Describe planned release and included changes.]

## Pre-Release Checks
1. `git status --short --branch` is clean except intended files.
2. No forbidden files changed unintentionally:
   - deployment configs
   - backup/restore scripts
   - env/secret files
3. Validation/smoke checks passed.
4. High-risk routes and data flows reviewed.

## Safety Checks
1. `/health` remains correct.
2. Port/runtime assumptions unchanged unless intentional.
3. Supabase credentials not exposed in logs/output.
4. Backup/restore operational safety unaffected (unless explicitly changed).

## Release Notes Template
- Summary:
- Files changed:
- Validation performed:
- Known risks:
- Rollback considerations:

## Final Gate
- Confirm explicit approval before commit/push/release actions.
