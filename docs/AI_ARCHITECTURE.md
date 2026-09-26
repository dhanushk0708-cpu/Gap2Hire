# Gap2Hire AI Architecture

## 1. AI Role

AI will assist Gap2Hire with analysis, extraction, recommendations, and personalized workflows.

AI will not independently make important hiring decisions.

## 2. Initial AI Capabilities

AI will support:

* Job description analysis
* Capability extraction
* Resume information extraction
* Candidate evidence analysis
* Evidence strength classification
* Gap and uncertainty identification
* Verification recommendations

## 3. Implemented AI Capabilities (MVP Complete)

* Job description analysis & Capability extraction
* Candidate resume extraction & Evidence research
* Evidence strength classification & Gap identification
* AI Screening & Candidate Top-N Shortlisting
* LangGraph-powered Adaptive Live AI Interviews & Integrity Signal Detection
* Post-Interview Evidence Report Synthesis
* Hiring Autopsy & AI Process Improvement Advisory Layer

## 3.1 Post-MVP AI Capabilities (Future Scope)

* Candidate Rediscovery matching
* Cross-cycle aggregate organizational hiring intelligence
* Dynamic personalized employee curriculum generation

## 4. AI Processing Flow

```text
Input
  ↓
Validation
  ↓
AI Processing
  ↓
Structured Output
  ↓
Validation
  ↓
Business Logic
  ↓
Human Review where required
```

AI output shall not directly modify critical business state without appropriate validation and authorization.

## 5. Structured AI Output

AI responses shall use structured schemas where possible.

Examples:

```text
Job → Capability Blueprint
Resume → Candidate Information
Candidate + Capability → Evidence Analysis
Evidence → Gap Identification
Gap → Verification Recommendation
```

Structured outputs will be validated before being stored or used by the application.

## 6. RAG Architecture

Company knowledge will use a retrieval-based architecture:

```text
Company Documents
       ↓
Document Processing
       ↓
Chunks
       ↓
Embeddings
       ↓
PostgreSQL + pgvector
       ↓
Relevant Context
       ↓
LLM
       ↓
Validated Response
```

Company data shall remain isolated by organization and accessed only according to permissions.

## 7. AI Agents

Agents will only be introduced where a multi-step stateful workflow provides a real benefit.

Potential future agent workflows include:

* Adaptive Interview Agent
* Training/Readiness Agent
* Hiring Process Analysis Agent

Gap2Hire will avoid unnecessary multi-agent systems.

## 8. Human Oversight

Human review will remain important for:

* Capability blueprint approval
* Candidate evidence review
* Verification decisions
* Hiring decisions
* Important process recommendations

## 9. AI Principle

> **AI should reduce uncertainty and improve decision quality, not replace human responsibility.**
