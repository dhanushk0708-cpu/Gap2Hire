# Gap2Hire — Development Rules

## 1. Understand Before Changing

Always inspect the existing repository, code, tests, database models, and relevant documentation before making changes.

Never assume a file or feature does not already exist.

## 2. Phase-Based Development

Implement one complete ROADMAP phase at a time.

A phase may contain multiple related modules, APIs, database changes, AI components, and tests.

Do NOT split a phase into unnecessary tiny tasks.

Do NOT start the next phase automatically.

Workflow:

Implement
→ Test
→ Verify
→ Explain
→ STOP

## 3. Preserve Working Code

Do not rewrite working code unnecessarily.

Do not replace existing architecture without a clear reason.

Fix unrelated issues only when they block the current phase. Otherwise report them.

## 4. Architecture

Use a modular monolith.

Prefer:

API / Router
→ Service / Business Logic
→ Database / Repository
→ Model

Keep AI logic separate from core business rules.

Avoid unnecessary abstractions, microservices, agents, dependencies, or infrastructure.

## 5. Security

- Never expose secrets.
- Never modify `.env` unless explicitly instructed.
- Never commit credentials.
- Never store plaintext passwords.
- Enforce authentication on protected resources.
- Enforce authorization server-side.
- Enforce tenant isolation server-side.
- Do not trust client-supplied ownership fields.
- Treat uploads, emails, external content, and AI output as untrusted.
- Validate structured AI output before using it.

## 6. AI

AI assists the system; it does not independently make important hiring decisions.

AI output must be treated as untrusted data.

Prefer structured outputs, validation, traceability, and human review where appropriate.

Do not create fake multi-agent systems just to make the project appear advanced.

## 7. Database

Use SQLAlchemy models and Alembic migrations.

Before creating migrations:

- inspect existing migrations
- verify model metadata
- run `alembic check`

Never create duplicate migrations or tables.

## 8. API

Use:

`/api/v1/`

Use Pydantic schemas.

Use consistent HTTP status codes and error responses.

Do not expose internal implementation details.

## 9. Testing

Every completed phase must have appropriate automated tests.

At minimum consider:

- unit tests
- API tests
- integration tests
- security tests
- tenant-isolation tests
- AI evaluation tests where AI is involved
- end-to-end tests for important workflows

Existing tests must continue to pass.

## 10. Verification

Never claim a feature works without running the relevant tests/checks.

For each phase report:

- implementation
- files created
- files modified
- database changes
- APIs
- architecture decisions
- security
- tests
- actual test results
- limitations
- remaining work

## 11. Stop Rule

After completing the requested phase:

STOP.

Do not implement or begin the next phase without explicit instruction.