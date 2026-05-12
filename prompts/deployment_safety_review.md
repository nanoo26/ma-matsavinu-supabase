# Deployment Safety Review Prompt Template

## Review Scope
[Fly.io / Docker / Render files and runtime assumptions.]

## Required Files
- `fly.toml`
- `Dockerfile`
- `render.yaml` (if present)
- `app.py` (`/health` behavior only as needed)

## Required Checks
1. Port alignment (`8080` expected).
2. Health check path and expected response.
3. Startup command consistency.
4. Required environment variables contract.
5. Multi-platform config drift risks.

## Guardrails
- Do not change deployment files unless explicitly requested.
- Do not alter health endpoint behavior unless explicitly requested.

## Output
1. Verified deployment configuration state
2. Drift/misalignment risks
3. Minimal safe corrective actions (proposal only unless approved)
