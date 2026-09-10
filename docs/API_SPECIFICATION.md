# Gap2Hire API Specification

## 1. API Overview

Gap2Hire will expose a REST API using FastAPI.

The API will use JSON for normal request and response data and appropriate file handling for resume/document uploads.

API routes will be versioned, starting with:

```text
/api/v1/
```

## 2. Authentication

```text
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
GET    /api/v1/auth/me
```

Authentication will be required for protected resources.

## 3. Organizations & Users

```text
POST   /api/v1/organizations
GET    /api/v1/organizations/{organization_id}
GET    /api/v1/organizations/{organization_id}/users
```

Access will depend on the user's role and organization.

## 4. Jobs

```text
POST   /api/v1/jobs
GET    /api/v1/jobs
GET    /api/v1/jobs/{job_id}
PATCH  /api/v1/jobs/{job_id}
DELETE /api/v1/jobs/{job_id}
POST   /api/v1/jobs/{job_id}/analyze
```

The analysis endpoint will generate a capability blueprint from the job description.

## 5. Capabilities

```text
GET    /api/v1/jobs/{job_id}/capabilities
POST   /api/v1/jobs/{job_id}/capabilities
PATCH  /api/v1/capabilities/{capability_id}
DELETE /api/v1/capabilities/{capability_id}
```

HR users will be able to review and modify AI-generated capabilities.

## 6. Candidates & Applications

```text
POST   /api/v1/applications
GET    /api/v1/applications
GET    /api/v1/applications/{application_id}
PATCH  /api/v1/applications/{application_id}
POST   /api/v1/applications/{application_id}/resume
```

Applications connect candidates with specific jobs.

## 7. Evidence

```text
GET    /api/v1/applications/{application_id}/evidence
GET    /api/v1/applications/{application_id}/evidence/{evidence_id}
POST   /api/v1/applications/{application_id}/evidence
```

Evidence will be associated with relevant capabilities and its source will be recorded.

## 8. Verification

```text
POST   /api/v1/applications/{application_id}/verifications
GET    /api/v1/applications/{application_id}/verifications
GET    /api/v1/verifications/{verification_id}
PATCH  /api/v1/verifications/{verification_id}
```

Verification activities will provide additional evidence for capabilities where required.

## 9. Hiring Decisions

```text
POST   /api/v1/applications/{application_id}/decision
GET    /api/v1/applications/{application_id}/decision
```

Only authorized users can create or modify hiring decisions.

## 10. Future API Areas

Additional API modules will be introduced as the product evolves:

```text
Adaptive Interviews
Email Ingestion
Company Knowledge / RAG
Personalized Training
Post-Hire Outcomes
Decision Replay
Hiring Autopsy
Candidate Rediscovery
```

These APIs will be designed when their corresponding features are implemented.

## 11. API Standards

The API shall follow these principles:

* RESTful resource naming.
* Versioned API routes.
* Consistent HTTP status codes.
* Pydantic request/response validation.
* Consistent error responses.
* Authentication and authorization for protected endpoints.
* Pagination for collections where required.
* OpenAPI documentation through FastAPI.
