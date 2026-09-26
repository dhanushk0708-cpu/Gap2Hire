# Gap2Hire Architecture

## 1. Architecture Approach

Gap2Hire will initially use a **modular monolith architecture**.

The backend will be built with FastAPI and organized into independent business modules. This keeps development and deployment simple while allowing the system to grow as new capabilities are added.

The architecture will support the complete Gap2Hire lifecycle without requiring unnecessary microservices during the early stages.

## 2. High-Level Architecture

```text
                    ┌──────────────┐
                    │   Frontend   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   FastAPI    │
                    │    Backend   │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   Core Modules        AI Services       RAG / Knowledge
        │                  │                  │
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                    ┌──────▼───────┐
                    │ PostgreSQL   │
                    │  Supabase    │
                    │  + pgvector  │
                    └──────────────┘

                    ┌──────────────┐
                    │    Redis     │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   Workers    │
                    └──────────────┘
```

## 3. Core Backend Modules

The backend contains modules for:

* Authentication and authorization (RBAC & multi-tenant isolation)
* Organizations and users
* Job management & Capability blueprints
* Candidate applications & Resume processing
* Evidence and gap analysis
* AI Screening & Dynamic Top-N Shortlisting
* Pre-Interview Analysis & Interview Planning
* Concurrent Live AI Interviews & Integrity Monitoring
* Post-Interview Evidence Reports
* Human Hiring Decisions
* Decision Replay (Historical audit & evidence reconstruction)
* Post-Hire Outcomes (Structured capability-to-work outcome tracking)
* Hiring Autopsy & AI Process Improvement Suggestions

*Post-MVP Expansion Modules (Future):*
* Candidate Rediscovery
* Advanced Organization-Wide Intelligence Assistant
* Personalized Training Expansion

## 6. AI Layer

AI functionality is separated from core business logic:

* Job description analysis & Capability extraction
* Resume analysis & Evidence extraction
* Evidence classification & Gap identification
* AI Screening & Candidate Shortlisting
* Adaptive Interview Question Generation & Dynamic Probing
* Post-Interview Report Generation
* Hiring Autopsy AI Advisory Process Improvement Suggestions

*Strict AI Principles:*
* All AI outputs are validated against Pydantic schemas.
* AI suggestions for hiring autopsy are strictly advisory (`is_advisory_only: true`).
* AI never automatically modifies hiring decisions, job blueprints, interview plans, or employee status.
* Insufficient evidence is explicitly recognized rather than assumed to be a skill lack.

## 9. Future Extensibility (Post-MVP)

The architecture allows future capabilities to be added without redesigning the system:

* Candidate Rediscovery & Re-engagement
* Organization-wide multi-cycle hiring trend analytics
* Personalized onboarding training tracks based on pre-hire unresolved gaps
* Cross-organization portable capability mesh (future research)

## 10. Architectural Principle

> **Start simple, keep boundaries clear, and introduce complexity only when the product actually requires it.**
