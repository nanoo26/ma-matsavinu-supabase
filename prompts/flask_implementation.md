# Flask Implementation Prompt Template

## Task
[Describe exact behavior change.]

## Hard Constraints
- Preserve existing routes, request field names, and template contracts unless explicitly requested.
- Keep changes minimal and scoped.
- Do not modify deployment or backup scripts unless explicitly requested.
- No schema assumptions; verify existing usage first.

## Pre-Implementation
1. Run `git status --short --branch`.
2. Inspect impacted code paths in `app.py`, templates, and static files.
3. List affected files and risks before applying changes.
4. Wait for explicit approval if risk is medium/high.

## Implementation Rules
- Reuse existing helper patterns.
- Add defensive handling for failure paths where relevant.
- Avoid broad refactors.

## Validation
1. Run project validation/smoke checks.
2. Re-run `git status --short --branch`.
3. Report changed files and validation results.

## Deliverables
- Summary of change
- Exact files changed
- Validation output summary
- Residual risks
