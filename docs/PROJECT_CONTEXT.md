# Gap2Hire — Project Context

## Product

Gap2Hire is an evidence-based hiring and employee-readiness platform.

Tagline:

> Find the Gap. Build the Skill. Get Hired.

Core question:

> What evidence do we have that a candidate can perform the capabilities required for a job?

Gap2Hire does not simply score resumes. It connects job requirements, capabilities, candidate evidence, verification, hiring decisions, employee readiness, and later outcomes.

## Core Principles

- Evidence over unsupported claims.
- Insufficient evidence does not mean lack of skill.
- Verification should target uncertainty.
- Practical work can create capability evidence.
- AI assists; humans own important hiring decisions.
- Company data must remain tenant-isolated.
- User input, uploaded documents, emails, external content, and AI output are untrusted until validated.
- Use technology only when it solves a real product problem.
- Prefer a modular monolith over unnecessary microservices.
- Build locally first but keep the architecture deployment-ready.

## Product Pillars

### Hire Right

Job requirements
→ Capability blueprint
→ Candidate
→ Evidence
→ Gaps / unknowns
→ Verification
→ Evidence report
→ Human hiring decision

### Build Readiness

Capability gaps
→ Company knowledge
→ Personalized training
→ Practice
→ Skill proof
→ Readiness

### Learn & Improve

Expected capability
→ Real-world outcomes
→ Decision replay
→ Root-cause analysis
→ Hiring process improvement

## Final Major Capabilities

1. AI Adaptive Interviews
2. Email Ingestion
3. Company Knowledge + RAG
4. Personalized Training
5. Post-Hire Outcomes
6. Decision Replay
7. Hiring Autopsy
8. Candidate Rediscovery

These are implemented progressively according to ROADMAP.md.

## Architecture

Modular monolith.

Typical flow:

Frontend
→ FastAPI API
→ Services / Business Logic
→ SQLAlchemy
→ PostgreSQL / Supabase

Redis and background workers are used when genuinely required.

AI functionality remains separated from core business logic.

## Technology Stack

- Python 3.11
- FastAPI
- SQLAlchemy async
- PostgreSQL
- Supabase
- Alembic
- Pydantic
- JWT
- pwdlib / Argon2
- Redis
- Background workers
- LLM APIs
- pgvector
- LangChain / LangGraph only where useful
- Pytest
- Docker
- Git / GitHub

## Roles

- COMPANY_ADMIN
- RECRUITER
- HIRING_MANAGER
- CANDIDATE
- PLATFORM_ADMIN

## Multi-Tenancy

Organizations are isolated tenants.

A user must only access data belonging to their organization unless an explicitly authorized platform-level operation exists.

Never trust a client-supplied organization_id for ownership.

## Current Core Domain

Organizations
→ Users
→ Jobs
→ Capabilities
→ Candidates
→ Applications
→ Evidence
→ Verification
→ Hiring Decisions

Later phases extend this domain with interviews, RAG, training, email ingestion, outcomes, decision replay, hiring autopsy, and candidate rediscovery.