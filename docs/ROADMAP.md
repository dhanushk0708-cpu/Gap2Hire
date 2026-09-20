# Gap2Hire — Development Roadmap

Build the project phase-by-phase.

Each phase is a meaningful product capability, not a single endpoint.

---

## Phase 0 — Engineering Foundation

Purpose:

Build the backend foundation required for the product.

Includes:

- repository structure
- FastAPI
- configuration
- PostgreSQL / Supabase
- SQLAlchemy
- Alembic
- authentication foundation
- JWT
- password hashing
- RBAC foundation
- testing foundation
- Docker foundation

Status: Mostly complete.

---

## Phase 1 — Identity + Multi-Tenant Company System

Purpose:

Make Gap2Hire a secure multi-company platform.

Includes:

- organizations
- users
- authentication
- roles
- authorization
- organization membership
- tenant isolation
- protected company resources
- security tests

Result:

Company A cannot access Company B's data.

---

## Phase 2 — Job + Capability Intelligence

Purpose:

Turn job requirements into a reviewed capability blueprint.

Includes:

- job management
- job lifecycle/status
- capability model
- job-capability relationships
- JD analysis
- AI capability extraction
- capability importance
- HR review/editing
- validation
- tests

Result:

Job Description
→ Required Capabilities
→ HR-reviewed Capability Blueprint

---

## Phase 3 — Candidate + Resume Evidence

Purpose:

Connect candidates to jobs and convert resume information into structured evidence.

Includes:

- candidate profiles
- applications
- resume upload
- file validation
- resume text extraction
- candidate information extraction
- capability evidence
- evidence strength
- known / weak / unknown analysis
- evidence traceability
- tests

Result:

Candidate
→ Application
→ Resume
→ Capability Evidence

---

## Phase 4 — Verification + Hiring Decision

Purpose:

Verify uncertain capabilities and support human hiring decisions.

Includes:

- verification requests
- targeted verification
- practical assessments / verification types
- verification results
- evidence updates
- evidence review
- hiring decisions
- decision reasons
- auditability
- tests

Result:

Evidence
→ Uncertainty
→ Verification
→ Updated Evidence
→ Human Hiring Decision

---

## Phase 5 — AI Adaptive Interviews

Purpose:

Make interviews adapt to candidate evidence and uncertainty.

Includes:

- interview sessions
- interview plans
- capability-focused questions
- adaptive question selection
- answers
- answer evaluation
- interview evidence
- interview history
- safety and validation
- tests/evaluation

---

## Phase 6 — Company Knowledge + RAG

Purpose:

Give Gap2Hire company-specific knowledge.

Includes:

- company documents
- document processing
- chunking
- embeddings
- pgvector
- retrieval
- grounded generation
- source traceability
- access control
- prompt-injection defenses
- RAG evaluation

Flow:

Company Documents
→ Chunks
→ Embeddings
→ pgvector
→ Retrieval
→ LLM
→ Validated Response

---

## Phase 7 — Personalized Training + Readiness

Purpose:

Help candidates/employees close capability gaps.

Includes:

- readiness profiles
- personalized learning plans
- company-specific learning context
- training content
- practice
- submissions
- evaluation
- skill proof
- readiness progression

Result:

Capability Gap
→ Learning Plan
→ Practice
→ Proof
→ Improved Readiness

---

## Phase 8 — Email Ingestion

Purpose:

Use permitted email data as another entry point into the hiring workflow.

Includes:

- email connection/integration
- ingestion
- classification
- extraction
- application-related information
- evidence-related information
- safe processing
- permissions
- privacy
- auditability

Email must never be blindly trusted as instructions.

---

## Phase 9 — Post-Hire Outcomes

Purpose:

Connect hiring evidence with later employee outcomes.

Includes:

- employee transition
- outcome records
- readiness progress
- capability development
- expected vs observed capability
- outcome analysis
- privacy/access controls

Do not make unsupported causal claims.

---

## Phase 10 — Decision Replay

Purpose:

Reconstruct what was known when a hiring decision was made.

Includes:

- decision-time evidence snapshot
- verification results
- interview results
- human feedback
- decision reasoning
- historical state
- replay/audit view

Core question:

"What did we know at the time of the decision?"

---

## Phase 11 — Hiring Autopsy

Purpose:

Learn from hiring outcomes and improve the hiring process.

Includes:

- hiring process analysis
- evidence gaps
- verification effectiveness
- capability-definition issues
- outcome patterns
- process insights
- human-reviewable recommendations

Focus on evidence and process patterns, not unsupported judgments about individuals.

---

## Phase 12 — Candidate Rediscovery

Purpose:

Find previously evaluated candidates for future opportunities using capability evidence.

Includes:

- historical candidate search
- capability-based matching
- evidence-based relevance
- verification history
- candidate/job matching
- access controls

Not merely keyword-based resume search.

---

## Phase 13 — Production Hardening

Purpose:

Make the complete system robust and deployment-ready.

Includes:

- security hardening
- tenant-isolation review
- rate limiting
- file security
- AI security
- prompt-injection defenses
- audit logging
- database optimization
- indexes
- background jobs
- retries
- idempotency
- observability
- error handling
- AI evaluation
- CI/CD
- environment separation
- health checks
- deployment preparation

---

## Phase 14 — Full Integration + Demo

Purpose:

Integrate and verify the complete Gap2Hire product.

Primary lifecycle:

Job
→ Capability Blueprint
→ Candidate
→ Application
→ Resume
→ Evidence
→ Gap / Unknown
→ Verification
→ Adaptive Interview
→ Evidence Update
→ Human Hiring Decision
→ Employee Readiness
→ Outcomes
→ Decision Replay
→ Hiring Autopsy

Additional flows:

Company Knowledge / RAG
Email Ingestion
Candidate Rediscovery

Final focus:

- end-to-end integration
- complete testing
- UI/backend integration
- realistic demo data
- documentation
- final project presentation
- deployment-ready demonstration