# Gap2Hire Testing Strategy

## 1. Purpose

Testing will ensure that Gap2Hire functionality works correctly, remains reliable during changes, and protects important business rules.

## 2. Testing Levels

### Unit Tests

Test individual functions and business logic in isolation.

Examples:

* Validation
* Capability processing
* Evidence classification
* Permission checks

### API Tests

Test FastAPI endpoints including:

* Authentication
* Jobs
* Applications
* Evidence
* Verification
* Hiring decisions

### Integration Tests

Test interactions between important components such as:

* API + PostgreSQL
* API + Redis
* Resume processing + evidence analysis
* AI services + application workflow

## 3. Security Testing

Tests shall verify:

* Unauthorized users cannot access protected resources.
* Users cannot access another organization's data.
* Invalid input is rejected.
* Invalid files are rejected.
* Role permissions are enforced.

## 4. AI Testing

Important AI workflows shall be tested using representative inputs and expected outputs.

AI tests will focus on:

* Structured output validity
* Extraction accuracy
* Evidence classification
* Gap identification
* RAG retrieval quality
* AI response safety

## 5. End-to-End Testing

The main hiring workflow shall eventually be tested from:

```text
Create Job
    ↓
Capability Blueprint
    ↓
Candidate Application
    ↓
Resume Processing
    ↓
Evidence Analysis
    ↓
Gap Identification
    ↓
Verification
    ↓
HR Review
    ↓
Hiring Decision
```

## 6. Testing Principle

> **Every important feature should have automated tests before it is considered complete.**
