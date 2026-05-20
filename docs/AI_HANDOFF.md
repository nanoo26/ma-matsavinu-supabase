# AI Handoff

## Purpose
This file summarizes the current Ma Matsavinu project state and AI handoff context. It is intended for future AI assistants, Codex runs, and the custom GPT so they can understand recent work and operate safely.

## Source of truth
- The Git repository and current local workspace are the source of truth.
- ChatGPT Project Sources may be outdated.
- Do not rely on uploaded copies of `app.py`, `reports.html`, `style.css`, or other code files unless they were refreshed from the current repository.
- Codex and future assistants must inspect the actual workspace before making code recommendations.

## Current stack
- Flask
- Jinja2
- Supabase PostgreSQL via `requests`
- HTML/CSS/JS
- Hebrew RTL
- Mobile-first up to 480px

## Current deployment workflow
- Production deploy is handled through GitHub Actions after push to `main`.
- Fly.io production was successfully updated through GitHub Actions.
- Local `fly deploy` on this Windows machine had remote builder / Docker host issues and is not the preferred workflow.
- Do not deploy automatically.

## Recent completed changes
- Add Expense UI improved.
- Edit Expense UI aligned with Add Expense.
- Category `צ'אבי` added and connected to categories/budget.
- Payment method `שופרסל` added.
- Safe handling for Hebrew labels with apostrophes/quotes using JSON-safe serialization where needed.
- Expenses and Reports row action buttons fixed.
- Reports chart label escaping fixed.
- Reports first section sorting fixed newest-to-oldest.
- Expense lists now sort by actual expense date, newest-to-oldest.
- Bottom navigation overlap fixed.
- Reports six summary cards relabeled:
  - `התחייבויות קבועות` -> `התחייבויות חודשיות`
  - `נשאר למותרות` -> `תקציב למותרות`
  - `כבר הוצאת החודש` -> `כבר הוצאת מהמותרות`
  - `עוד יכול להוציא` -> `נשאר להוציא`
- Daily average now only shows numeric value for the current selected financial month.
- Project docs updated for local run and GitHub Actions deployment.

## Known follow-up risks
- Installment rows without valid `payment_plans` may appear in installment tables but not in commitments card calculation.
- Full reports calculation audit should be done read-only before any future formula change.
- Project Sources in ChatGPT should be refreshed from current repo docs, not old code files.

## Safe AI workflow
- Start risky work with read-only audit.
- Always run `git status --short --branch` first.
- Stop if the working tree is dirty unless the user explicitly approves continuing.
- Do not edit files outside the approved allowlist.
- Do not touch `.env`, secrets, tokens, or credentials.
- Do not change routes, schema, Supabase, auth, sessions, financial calculations, or deployment config unless explicitly approved.
- Before commit:
  ```powershell
  git status --short --branch
  python -m py_compile app.py
  git diff --check
  ```

## How future ChatGPT/Codex work should happen
- User describes the issue.
- Assistant creates a safe Codex prompt.
- Codex audits first.
- User reviews the report.
- Only then approve implementation.
- Manual QA before commit, push, or deploy.
