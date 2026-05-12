# UI Review Prompt Template (Hebrew RTL, Mobile-First)

## Scope
[Screens/templates/components to review.]

## Required Context
- `templates/`
- `static/style.css`
- `static/design-system.md` (if used)

## Review Checklist
1. RTL correctness and Hebrew readability.
2. Mobile-first behavior (360-480px).
3. Visual hierarchy and touch-target usability.
4. Regression risk to existing template variable bindings.
5. CSS consistency with existing design tokens/classes.

## Guardrails
- Do not alter backend logic unless explicitly requested.
- Do not rename form fields, route references, or Jinja variables.

## Output
1. Findings by severity
2. Affected templates/styles
3. Minimal safe UI patch plan
