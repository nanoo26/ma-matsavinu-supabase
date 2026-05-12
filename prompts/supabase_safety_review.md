# Supabase Safety Review Prompt Template

## Review Scope
[Describe endpoint(s), table(s), and operations to review.]

## Required Checks
1. Verify env-based credential handling (`SUPABASE_URL`, `SUPABASE_KEY`).
2. Identify all write/delete paths.
3. Verify timeout, error handling, and response validation behavior.
4. Confirm table and field names are consistent with existing code.
5. Identify bulk-operation or destructive-operation risks.

## Guardrails
- No key/token disclosure.
- No schema changes without explicit approval.
- No production data mutation during review.

## Output
1. Verified data flow map (read/write/delete)
2. Safety findings by severity
3. High-risk operations requiring explicit approval
4. Recommended minimal improvements
