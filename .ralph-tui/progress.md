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

