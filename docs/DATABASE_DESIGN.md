# Gap2Hire Database Design

## 1. Database

Gap2Hire will use **PostgreSQL** as the primary database.

Supabase will provide the managed PostgreSQL database for cloud environments.

pgvector will be used where semantic/vector search is required.

## 2. Core Entities

### Organization

Represents a company using Gap2Hire.

Main responsibilities:

* Company information
* Organization ownership
* Tenant isolation

### User

Represents a person using the platform.

A user belongs to an organization where applicable and has a defined role.

Roles include:

* Company Admin
* Recruiter / HR
* Hiring Manager
* Candidate
* Platform Admin

### Job

Represents a job opening created by an organization.

Contains:

* Job information
* Job description
* Status
* Organization relationship
* Created/updated information

### Capability

Represents a skill or capability required by a job.

Examples:

* Python
* FastAPI
* PostgreSQL
* REST API design
* Problem solving

A job can require multiple capabilities.

### Candidate

Represents a person being considered for employment.

Contains structured candidate information independent of a specific job.

### Application

Connects a candidate with a specific job.

This allows the same candidate to apply to multiple jobs without duplicating the candidate record.

### Evidence

Represents evidence supporting a candidate's capability.

Examples:

* Resume evidence
* Project evidence
* Assessment result
* Interview evidence
* Practical verification

Evidence should be associated with the relevant candidate and capability where applicable.

### Verification

Represents an activity performed to verify a capability where existing evidence is insufficient.

Contains:

* Capability being verified
* Verification type
* Candidate response/result
* Evaluation
* Status

### Hiring Decision

Represents the final decision made by an authorized human.

Possible states may include:

* Hire
* Reject
* Further Review

The decision is associated with the relevant application.

## 3. Core Relationships

```text
Organization
    │
    ├──< User
    │
    └──< Job
          │
          └──< Capability
          
Candidate
    │
    └──< Application >── Job
              │
              ├──< Evidence
              │
              ├──< Verification
              │
              └── Hiring Decision
```

## 4. Important Database Principles

### Organization Isolation

Organization-owned records must be associated with the correct organization.

The application must prevent cross-organization data access.

### Evidence Traceability

Evidence should retain enough information to understand:

* What capability it supports
* Where the evidence came from
* How it was produced
* Whether it was verified
* When it was created

### Human Decision Ownership

AI analysis may create recommendations or evidence classifications, but the hiring decision belongs to an authorized human user.

### Data Integrity

The database shall use:

* Primary keys
* Foreign keys
* Appropriate constraints
* Required fields
* Unique constraints where needed
* Indexes for important queries
* Database migrations

## 5. Future Database Extensions

The database can later be extended with entities for:

* Adaptive interviews
* Email ingestion
* Company knowledge
* Documents and embeddings
* Training plans
* Learning activities
* Skill proofs
* Post-hire outcomes
* Decision replay
* Hiring autopsy
* Candidate rediscovery

These will be introduced when their corresponding features are implemented.

## 6. Core Database Principle

> **Design the data model around the real Gap2Hire lifecycle, not around individual technologies or AI features.**

## 7. Evidence

`evidence` represents information that supports a candidate's capability.

Examples include:

* Resume evidence
* Project evidence
* Assessment results
* Interview evidence
* Practical verification results

Main fields:

| Field            | Purpose                                                  |
| ---------------- | -------------------------------------------------------- |
| `id`             | Unique evidence ID                                       |
| `application_id` | Related application                                      |
| `capability_id`  | Capability being supported                               |
| `source_type`    | Resume / Project / Assessment / Interview / Verification |
| `content`        | Evidence details                                         |
| `strength`       | Evidence strength                                        |
| `created_at`     | Creation time                                            |

Relationship:

```text
Application
     │
     └──< Evidence >── Capability
```

## 8. Verification

`verifications` represents an activity used to verify a capability when existing evidence is insufficient.

Main fields:

| Field            | Purpose                                 |
| ---------------- | --------------------------------------- |
| `id`             | Unique verification ID                  |
| `application_id` | Related application                     |
| `capability_id`  | Capability being verified               |
| `type`           | Assessment / Practical Task / Interview |
| `status`         | Pending / In Progress / Completed       |
| `result`         | Verification result                     |
| `created_at`     | Creation time                           |
| `completed_at`   | Completion time                         |

Relationship:

```text
Application
     │
     └──< Verification >── Capability
```

A completed verification can produce new evidence.

## 9. Hiring Decision

`hiring_decisions` stores the final decision made by an authorized human.

Main fields:

| Field            | Purpose                        |
| ---------------- | ------------------------------ |
| `id`             | Unique decision ID             |
| `application_id` | Related application            |
| `decided_by`     | User who made the decision     |
| `decision`       | Hire / Reject / Further Review |
| `reason`         | Optional decision notes        |
| `created_at`     | Decision time                  |

Relationship:

```text
Application
     │
     └── Hiring Decision
```

AI analysis may support the decision, but the final hiring decision belongs to an authorized human.

## 10. Core Evidence Flow

```text
Job
 ↓
Capabilities
 ↓
Candidate Application
 ↓
Evidence Analysis
 ↓
Evidence by Capability
 ↓
Weak / Insufficient Evidence
 ↓
Verification
 ↓
New Evidence
 ↓
Human Hiring Decision
```

This forms the core data flow of the Gap2Hire evidence-based hiring system.

## 11. Constraints and Indexes

The database shall use appropriate constraints to maintain data integrity.

Important constraints include:

* Primary keys for all entities.
* Foreign keys for entity relationships.
* Unique email addresses where required.
* Unique organization slugs.
* Valid application status values.
* Valid hiring decision values.
* Required fields enforced at database level where appropriate.

Indexes shall be added for frequently queried fields such as:

* `organization_id`
* `job_id`
* `candidate_id`
* `application_id`
* `capability_id`
* `email`

Indexes will be added based on actual query requirements rather than prematurely indexing every column.

## 12. Future Extensions

The database can later support:

* Adaptive interviews
* Email ingestion
* Company knowledge and RAG
* Embeddings and semantic search
* Personalized training
* Skill proofs
* Post-hire outcomes
* Decision replay
* Hiring autopsy
* Candidate rediscovery

These entities will be introduced when their corresponding features are implemented.

## 13. Database Principle

> Keep the database simple, maintain strong relationships and data integrity, and extend it as Gap2Hire capabilities are implemented.
