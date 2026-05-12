# Backup/Restore Safety Review Prompt Template

## Scope
[Backup script, restore script, operational workflow.]

## Required Checks
1. Backup destination and retention behavior.
2. Sensitive data exposure risks in backup artifacts.
3. Restore confirmation flow and destructive-path safeguards.
4. Error handling and partial-failure behavior.
5. Operational runbook clarity.

## Guardrails
- Do not run restore against production data.
- Do not change destructive behavior without explicit approval.
- Treat backups as sensitive financial artifacts.

## Output
1. Current safety posture
2. High-risk operations
3. Gaps in operational controls
4. Minimal safe hardening recommendations
