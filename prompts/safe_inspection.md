# Safe Inspection Prompt Template

## Goal
[Describe what must be inspected and why.]

## Constraints
- Inspect workspace first.
- Do not edit files.
- Do not run destructive commands.
- Report findings with file paths and risks.

## Required Steps
1. Run `git status --short --branch`.
2. Confirm working tree state.
3. Read relevant docs/instructions:
   - `README.md`
   - `AGENTS.md`
   - `START_HERE.md`
   - `PROJECT_STATUS.md`
4. Inspect targeted files and summarize architecture impact.
5. List unknowns and assumptions explicitly.

## Output Format
1. Current git status
2. Verified facts
3. Risks
4. Affected files
5. Safe next-step options (no edits yet)
