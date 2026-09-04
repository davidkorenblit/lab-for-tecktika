# Engineering & Operating Rules (Guardrails)

These rules are strictly enforced across all development and agent workflows within this repository.

---

## 1. Git & Version Control Hygiene
* **Explicit Staging Only**: NEVER run `git add .` or `git add -A`. Always stage files explicitly by name (e.g., `git add frontend/src/App.tsx backend/app/main.py`).
* **Clean Commits**: Commit messages must follow Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
* **Zero Secrets in Git**: Never commit `.env`, `local.settings.json`, certificates, private keys, or API tokens. Always use `.env.example` templates with placeholder values.

---

## 2. Cloud & Azure Best Practices
* **Managed Identity Over API Keys**: In production and cloud deployments, always use Microsoft Entra Managed Identities (DefaultAzureCredential) instead of hardcoding connection strings or secrets.
* **Idempotency by Design**: All event-driven handlers (workers/functions) must be idempotent using ETags or deterministic partition keys to prevent double-processing.
* **Cost Consciousness**: Never provision paid cloud tiers (e.g., Search Standard S2/S3, GPU compute) without explicit requirement justification. Use Consumption / Serverless / Basic tiers where possible.
* **Dead Letter Queues (DLQ)**: Every queue processing loop must route unprocessable/poison messages to a DLQ rather than silently failing or crashing.

---

## 3. Code Quality & Architecture Standards
* **Production-Grade Code**: No placeholder "magic fixes" or pseudo-code in production files. Write complete, well-typed, maintainable implementations with proper error handling.
* **Strict Typing**:
  * **Python (Backend & Worker)**: Pydantic v2 schemas for all inputs/outputs, explicit type hints (`typing`), and structured logging.
  * **TypeScript (Frontend)**: Strict type checking (`noImplicitAny: true`), zero `any` types where avoidable.
* **Security & Injection Guardrails**:
  * All agent tool inputs must be validated through strict Pydantic schemas.
  * Prompt injection protection: System prompt delimiters must strictly separate user instructions from retrieved untrusted document content.
* **Decoupled Contracts**: Changes to shared data schemas (Queue payloads, Table entities, API models) must maintain backward compatibility or be versioned cleanly (`/api/v1`).

---

## 4. Execution & Step-by-Step Discipline
* **Never Blindly Overwrite**: Always check file state before modifying.
* **Verification First**: Verify changes through automated unit tests or local emulation (Azurite) before considering a task complete.
