# Agent CLI Verification Report

**Date:** 2026-04-21
**Author:** US-001

## Summary

This document records the smoke test results for various Agent CLI interfaces that may be used for task execution.

## 1. Claude Code (`claude`)

### Availability
- **Installed:** Yes
- **Version:** 2.1.91
- **Path:** `/Users/mac/.nvm/versions/node/v20.16.0/bin/claude`

### Command Format
```bash
claude --print "<instruction>"
```

### Smoke Test Results

**Command:**
```bash
claude --print "echo hello"
```

**Output:**
```
hello
```

**Exit Code:** 0

### Return Structure
- stdout: Direct command output
- stderr: Error messages (if any)
- exit_code: 0 for success, non-zero for failure

### Notes
- `--print` flag runs non-interactively
- Returns output directly without interactive prompt
- Works for simple shell commands and complex instructions

---

## 2. OpenClaw (`openclaw`)

### Availability
- **Installed:** No
- **Status:** `command not found`

### Notes
Not installed in the current environment. According to PRD Non-Goals, only `claude_code` executor is required for MVP.

---

## 3. Hermes (`hermes`)

### Availability
- **Installed:** No
- **Status:** `command not found`

### Notes
Not installed in the current environment. According to PRD Non-Goals, only `claude_code` executor is required for MVP.

---

## 4. Codex (`codex`)

### Availability
- **Installed:** Yes
- **Version:** codex-cli 0.101.0
- **Path:** `/Users/mac/.nvm/versions/node/v20.16.0/bin/codex`

### Command Format
```bash
codex exec "<instruction>"
```

### Smoke Test Results

**Command:**
```bash
codex exec "echo hello"
```

**Output:**
```
OpenAI Codex v0.101.0 (research preview)
--------
workdir: /Users/mac/Desktop/DUS
model: gpt-5.2-codex
provider: openai
...
ERROR: unexpected status 401 Unauthorized
```

**Exit Code:** 1

### Return Structure
- Exit code 1 indicates authentication error (requires OpenAI API key)
- No valid return structure without authentication

### Notes
- Codex requires OpenAI API authentication
- Currently returns 401 Unauthorized errors
- Not suitable for MVP without additional authentication setup

---

## Conclusion

Only **Claude Code** (`claude --print`) is verified working in the current environment. The other agents (OpenClaw, Hermes) are not installed, and Codex requires authentication.

**Recommended for MVP:** Use `claude --print "{instruction}"` as the primary agent executor.