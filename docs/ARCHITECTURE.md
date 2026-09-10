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

The backend will contain modules for:

* Authentication and authorization
* Organizations and users
* Job management
* Capability blueprints
* Candidate applications
* Resume processing
* Evidence and gap analysis
* Verification
* Interviews
* Hiring decisions
* Company knowledge and RAG
* Employee readiness and training
* Post-hire outcomes
* Decision replay
* Hiring autopsy
* Candidate rediscovery

## 4. Data Layer

Gap2Hire will use PostgreSQL as its primary database.

Supabase will provide the managed cloud PostgreSQL environment.

pgvector will support vector storage and similarity search for use cases such as:

* Company knowledge retrieval
* Candidate capability matching
* Candidate rediscovery
* Other semantic search requirements

## 5. Background Processing

Redis and background workers will handle operations that should not block normal API requests, such as:

* Resume processing
* Document processing
* AI analysis
* Embedding generation
* Email ingestion
* Other long-running tasks

## 6. AI Layer

AI functionality will be separated from core business logic.

AI services may handle:

* Job description analysis
* Capability extraction
* Resume analysis
* Evidence classification
* Gap identification
* Verification recommendations
* Adaptive interviews
* Company knowledge retrieval
* Personalized training
* Hiring-process analysis

AI outputs will be validated and important decisions will remain human-controlled.

## 7. RAG / Company Knowledge

Company knowledge will be stored and indexed for retrieval.

The basic flow will be:

```text
Company Documents
       ↓
Processing
       ↓
Chunking
       ↓
Embeddings
       ↓
pgvector
       ↓
Relevant Context
       ↓
LLM
       ↓
Structured Response
```

Access to company knowledge will respect organization and user permissions.

## 8. Multi-Tenancy

Gap2Hire will support multiple organizations.

Every organization-owned resource must be associated with the correct organization, and authorization rules must prevent users from accessing another organization's data.

## 9. Future Extensibility

The architecture shall allow future capabilities to be added without redesigning the entire system.

Future capabilities include:

* AI adaptive interviews
* Email ingestion
* RAG/company knowledge
* Personalized training
* Post-hire outcomes
* Decision replay
* Hiring autopsy
* Candidate rediscovery

The architecture should remain simple until actual scale or operational requirements justify additional services.

## 10. Architectural Principle

> **Start simple, keep boundaries clear, and introduce complexity only when the product actually requires it.**
