# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

*Add reusable patterns discovered during development here.*

---

## 2026-04-21 - US-001

- **What was implemented:** Agent CLI smoke testing - verified claude (working), openclaw (not installed), hermes (not installed), codex (installed but requires auth)
- **Files changed:** `agent_cli_verified.md` (new), `cloud/.venv/` (pytest installed)
- **Learnings:**
  - Only `claude --print` works out of the box for agent execution
  - `openclaw` and `hermes` are not installed - not needed for MVP per PRD Non-Goals
  - `codex exec` requires OpenAI API authentication and returns 401 without it
  - `python -m pytest` returns exit code 5 (no tests) since test files don't exist yet (US-024)
  - `python -m py_compile cloud/**/*.py` passes all syntax checks

---

## 2026-04-21 - US-003

- **What was implemented:** Development environment setup - verified all modules are properly configured
- **Files changed:**
  - `frontend/package.json` (added typecheck script)
  - `cloud/.gitignore` (created - Python, venv, env, IDE patterns)
  - `bridge/.gitignore` (created - Python, venv, env, IDE patterns)
  - `bridge/venv/` (created via python3 -m venv venv, dependencies installed)
- **Learnings:**
  - Frontend already had shadcn initialized with components in `src/components/ui/`
  - Cloud/.venv already had FastAPI/uvicorn/SQLAlchemy installed
  - Bridge venv needed to be created fresh with `python3 -m venv venv && pip install -r requirements.txt`
  - Root .gitignore already existed with proper patterns
  - pytest exit code 5 = "no tests collected" - not a failure, documented in US-001
  - `pnpm typecheck` requires adding to package.json scripts (`"typecheck": "tsc --noEmit"`)

