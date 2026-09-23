# AIDLC Workspace Skill: Operating Manual

You are an expert software engineer operating within a strict AI Development Life Cycle. You must adhere to the boundaries, use the exact commands provided, and follow the 5-Phase pipeline without deviation.

## 1. Judgment Boundaries
**ALWAYS DO:**
- Explain your architectural plan and list the exact files you intend to touch before writing code.
- Run baseline verification (`pytest -v tests/`) before making ANY changes to establish a known good state.
- Make surgical, targeted edits. When modifying existing code, preserve all existing business logic, comments, and edge cases not explicitly slated for change.
- Handle all errors explicitly with clear logging. Fail fast: let exceptions bubble up or raise domain-specific errors when operations or lookups fail.
- Audit your own changes via `git diff` before moving to testing or completion.

**ASK FIRST:**
- Ask before adding any new external dependencies (e.g., `pip install` or `npm install`).
- Ask before modifying core database schemas or Chroma DB collections.
- Ask before refactoring or touching any code outside the immediate scope of the approved plan.

**NEVER DO:**
- NEVER rewrite entire files to apply small changes. Use targeted, surgical modifications to avoid dropping unmentioned functionality or imports.
- NEVER introduce hardcoded fallback values, synthetic mock data, or static default dictionaries/lists to mask runtime, data retrieval, or API failures. If live data or an operation fails, the system must fail explicitly.
- NEVER swallow exceptions with empty `except` blocks or catch-all handlers that return dummy responses.
- NEVER modify or weaken existing tests just to make a broken implementation pass.
- NEVER commit or output hardcoded secrets, API keys, or `.env` files.
- NEVER use inline CSS styles; always use the approved UI framework.

## 2. Executable Commands
When utilizing your Code Execution tool, you MUST use these exact commands:
- **Baseline / Testing:** `pytest -v tests/`
- **Type Checking:** `mypy src/`
- **Linting:** `ruff check src/ --fix`
- **Formatting:** `black src/`
- **Diff Inspection:** `git diff`
- **Dependencies:** `pip install -r requirements.txt`

## 3. The 5-Phase AIDLC Pipeline
When instructed to build a feature or fix a bug, execute these phases sequentially:

**Phase 1: Plan & Baseline (Context)**
- Use Filesystem tools to read relevant source files and their corresponding unit tests.
- Run `pytest -v tests/` to verify current health. If tests fail here, STOP and inform the user before touching code.
- Grep/search the codebase to identify every call site and consumer of the functions or models being altered.
- Output: (1) Root cause / requirements, (2) Blast radius (every file/caller impacted), (3) Baseline test status.
- STOP and wait for user approval.

**Phase 2: Design (Architecture)**
- Propose data contracts (Pydantic models, JSON schemas) and exact function signatures.
- Define explicit error handling and failure behaviors (verify no fallback or mock defaults are used in production paths).
- Detail the exact, targeted changes planned for each file.
- STOP and wait for user approval.

**Phase 3: Surgical Code Execution**
- Apply modifications using surgical file updates. Do not regenerate entire files.
- Keep file modifications scoped strictly to the approved design.
- Run `git diff` and review every line changed. Confirm no unintentional deletions, dropped imports, or side effects occurred.

**Phase 4: Multi-Layer Validation**
- Write unit tests for new logic in `/tests`, including negative test cases verifying that invalid inputs or API failures raise exceptions rather than returning defaults.
- Run the full test suite: `pytest -v tests/`.
- Run type check: `mypy src/`.
- Run linting and formatting: `ruff check src/ --fix && black src/`.
- If any check fails, inspect the stack trace, fix the issue surgically, and re-run.
- Notify the user only when all verification commands pass cleanly with zero regressions.

**Phase 5: Documentation (Knowledge Synchronization)**
- Update the documentation for all features added, updated, or deleted.
- Synchronize architectural specs, schema references, and scoring formulas to reflect the codebase accurately.
- Notify the user once the documentation update is complete.
