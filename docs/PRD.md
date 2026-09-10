# Gap2Hire

## Product Requirements Document (PRD)

**Product:** Gap2Hire
**Tagline:** Find the Gap. Build the Skill. Get Hired.
**Document Type:** Product Requirements Document
**Version:** 1.0
**Status:** Draft
**Date:** September 2026

---

## 1. Product Overview

Gap2Hire is an evidence-based hiring and employee-readiness platform designed to help companies make better-informed hiring decisions and continuously improve their hiring process.

The platform connects the hiring lifecycle from initial job requirements to candidate evidence, skill verification, employee readiness, and post-hire outcomes.

Instead of treating a resume or an AI-generated score as sufficient evidence of capability, Gap2Hire identifies what evidence exists for each required capability, highlights areas where evidence is weak or insufficient, and provides mechanisms to verify those uncertainties through practical assessments and targeted interviews.

After a candidate is hired, the platform can reuse the information gathered during hiring to identify readiness gaps, provide personalized training and practical tasks, and collect additional evidence of skill development.

Over time, Gap2Hire can compare the expectations and evidence available at the time of hiring with actual post-hire outcomes. These insights can help organizations identify weaknesses in their hiring process and improve future hiring decisions.

### Core lifecycle

**Job Requirements → Candidate Evidence → Gap Identification → Verification → Human Hiring Decision → Employee Readiness → Skill Proof → Real-World Outcomes → Hiring Process Improvement**

---

## 1.1 Core Value Proposition

Gap2Hire aims to move hiring from primarily evaluating candidate claims toward continuously building and evaluating capability evidence.

The platform's core value is:

> **Help companies understand what a candidate can demonstrate, identify what remains uncertain, verify important gaps, support employee readiness after hiring, and learn from real outcomes to improve future hiring.**

---

## 1.2 Product Philosophy

Gap2Hire follows several core principles:

1. **Evidence over unsupported claims**
2. **Insufficient evidence is not the same as lack of skill**
3. **Verification should target uncertainty**
4. **Practical work should contribute to skill evidence**
5. **Hiring decisions remain human-controlled**
6. **AI assists reasoning but should not replace responsible human decision-making**
7. **Post-hire development should build on information gathered during hiring**
8. **Real outcomes should provide feedback for improving the hiring process**
9. **Sensitive personal attributes should not be used as inappropriate hiring signals**
10. **Technology should be introduced because it solves a real engineering or product problem**

---

## 1.3 High-Level Product Flow

```text
                         GAP2HIRE

Job Requirements
       ↓
Capability Blueprint
       ↓
Candidate Application
       ↓
Candidate Evidence
       ↓
Evidence & Gap Analysis
       ↓
Targeted Verification
       ↓
Evidence Report
       ↓
Human Hiring Decision
       ↓
Employee Readiness
       ↓
Practice & Skill Proof
       ↓
Real-World Outcomes
       ↓
Decision Replay
       ↓
Hiring Process Insights
       ↓
Improved Hiring Process
```

---

## 1.4 Initial Product Scope

The initial product will focus on building a strong end-to-end evidence-based hiring workflow.

The first major product loop will cover:

* Company/job creation
* Job requirement analysis
* Capability extraction
* Candidate application
* Resume processing
* Candidate profile creation
* Evidence analysis
* Gap/unknown identification
* Targeted verification
* Evidence reporting
* Human hiring decision

Post-hire training, skill proof, and process-learning capabilities will be developed incrementally after the core hiring workflow is functional.


# 2. Problem Statement

## 2.1 Claims vs Evidence

Candidates communicate skills through resumes, projects, interviews, and previous experience. However, these sources may not provide sufficient evidence that a candidate can perform a capability required by a specific role.

**Gap:** Hiring teams need a structured way to evaluate capability-specific evidence.

## 2.2 Missing Evidence vs Missing Skill

A skill that is not mentioned or sufficiently demonstrated does not necessarily mean the candidate lacks that skill.

**Gap:** Hiring systems should distinguish between **lack of evidence** and **lack of capability**.

## 2.3 Uncertainty and Verification

When evidence for an important capability is weak or insufficient, recruiters need a way to verify that capability through targeted assessments or practical tasks.

**Gap:** Screening should identify what needs verification instead of relying only on an overall candidate score.

## 2.4 Hiring-to-Development Disconnect

Information gathered during hiring can reveal a candidate's strengths and development gaps, but this information is often disconnected from post-hire training and onboarding.

**Gap:** Hiring evidence should be reusable for employee readiness and development.

## 2.5 Lack of a Continuous Feedback Loop

Organizations may collect hiring information and later observe employee performance, but these stages are not always connected systematically.

**Gap:** Organizations need a way to compare hiring expectations and evidence with post-hire outcomes and use those insights to improve future hiring processes.

## 2.6 Core Problem

> **Gap2Hire addresses the disconnect between candidate evidence, hiring decisions, employee readiness, and post-hire outcomes by connecting these stages into a continuous lifecycle.**

# 3. Goals & Success Criteria

## 3.1 Product Goals

The initial Gap2Hire MVP aims to:

1. Convert job descriptions into structured capability requirements.
2. Extract relevant candidate information from resumes.
3. Map candidate evidence against job capabilities.
4. Identify weak or insufficient evidence.
5. Generate targeted verification requirements for important gaps.
6. Provide HR with a transparent evidence-based candidate view.
7. Keep final hiring decisions under human control.
8. Establish the foundation for post-hire employee readiness and continuous hiring-process improvement.

## 3.2 Success Criteria

The MVP will be considered successful when it can:

| Area              | Success Criterion                                                             |
| ----------------- | ----------------------------------------------------------------------------- |
| Job analysis      | Extract required capabilities into a structured representation                |
| Resume processing | Reliably process supported resume formats                                     |
| Evidence analysis | Map candidate evidence to job capabilities                                    |
| Gap detection     | Identify weak or insufficient evidence                                        |
| Verification      | Generate targeted verification requirements for important gaps                |
| Transparency      | Allow HR to understand the evidence behind candidate analysis                 |
| Reliability       | Handle invalid inputs and expected failures safely                            |
| Security          | Apply defined authentication, authorization, and data-protection requirements |
| Testing           | Provide automated tests for core backend functionality                        |
| Deployment        | Package the application for consistent deployment                             |

## 3.3 Guiding Success Principle

> **Gap2Hire should produce structured, traceable, and testable evidence that helps humans make better-informed hiring decisions rather than replacing human decision-making with an unexplained AI score.**

# 4. Target Users

## 4.1 Company Admin

Manages the organization's Gap2Hire account and company-level configuration.

**Primary capabilities:**

* Manage company information
* Manage company users
* Manage jobs
* View company hiring activity

## 4.2 Recruiter / HR

Primary user of the hiring workflow.

**Primary capabilities:**

* Create and manage jobs
* Review applications
* Review candidate evidence
* Initiate verification
* Review assessment and interview results
* Record hiring decisions

## 4.3 Hiring Manager

Evaluates candidates for roles within their team.

**Primary capabilities:**

* View assigned jobs
* Review candidate evidence
* Review verification results
* Provide hiring feedback
* Participate in hiring decisions

## 4.4 Candidate

Interacts with the candidate-facing platform.

**Primary capabilities:**

* Apply for jobs
* Submit application information and resumes
* Complete assessments and verification tasks
* Participate in interviews
* View permitted application and readiness information

## 4.5 Platform Administrator

Internal Gap2Hire administrator responsible for platform-level operations.

**Primary capabilities:**

* Manage platform configuration
* Investigate operational issues
* Perform restricted administrative actions
* Support platform operations

Platform administrator access must be restricted and audited.

## 4.6 Multi-Tenant Access Principle

Gap2Hire will support organization-level data isolation.

A user's access to jobs, candidates, applications, evidence, and other company data must be restricted according to their organization and assigned permissions.

## 4.7 Initial Roles

The MVP will support:

* Company Admin
* Recruiter / HR
* Hiring Manager
* Candidate
* Platform Administrator

Additional specialized roles may be introduced in future versions when required by the product.


# 5. User Journeys

## 5.1 HR Creates a Job

```text
HR Login
  ↓
Create Job
  ↓
Enter Job Description
  ↓
Submit
  ↓
JD Analysis
  ↓
Capability Blueprint
  ↓
HR Review / Edit
  ↓
Activate Job
```

The system may use AI to extract capabilities from the job description, but the responsible HR user can review and modify the resulting capability blueprint.

---

## 5.2 Candidate Applies

```text
Candidate
  ↓
Select Job
  ↓
Submit Application
  ↓
Upload Resume
  ↓
Application Created
  ↓
Resume Processing
```

The application workflow should be designed so that future entry points, such as email-based applications, can use the same underlying application-processing flow.

---

## 5.3 Resume and Evidence Processing

```text
Resume
  ↓
File Validation
  ↓
Text Extraction
  ↓
Candidate Information Extraction
  ↓
Evidence Analysis
  ↓
Store Structured Results
```

The system produces capability-specific evidence rather than relying only on a single overall candidate score.

---

## 5.4 HR Evaluates a Candidate

```text
Job
  ↓
Candidate
  ↓
Evidence by Capability
  ↓
Weak / Insufficient Evidence
  ↓
Verification Recommendations
  ↓
HR Review
```

The HR user should be able to understand the evidence supporting the system's analysis.

---

## 5.5 Candidate Verification

```text
Gap Identified
  ↓
Verification Requirement
  ↓
HR Approval
  ↓
Candidate Completes Task
  ↓
Automated / AI Evaluation
  ↓
Evidence Updated
  ↓
HR Review
```

Verification results support the hiring decision but do not automatically determine the outcome.

---

## 5.6 Hiring Decision

```text
Evidence
+
Verification
+
Interview Results
      ↓
HR Review
      ↓
Hire / Reject / Further Review
```

The final hiring decision remains under human control.

---

## 5.7 Future: Employee Readiness

```text
Hiring Evidence
+
Known Gaps
+
Job Requirements
+
Company Knowledge
      ↓
Readiness Plan
      ↓
Learn
      ↓
Practice
      ↓
Prove
      ↓
Adapt
```

This capability will be developed after the core hiring workflow.

---

## 5.8 Future: Hiring Process Learning

```text
Hiring Decision
      ↓
Post-Hire Outcomes
      ↓
Expected vs Actual
      ↓
Decision Replay
      ↓
Pattern Analysis
      ↓
Process Recommendation
      ↓
Human Approval
      ↓
Improved Hiring Process
```

This represents the long-term continuous-learning lifecycle of Gap2Hire.

# 6. Product Features

## 6.1 MVP Features

### 6.1.1 Authentication and Organization Management

* Company registration
* User authentication
* Role-based access control
* Organization-level data isolation
* Company and user management

Initial roles:

* Company Admin
* Recruiter / HR
* Hiring Manager
* Candidate
* Platform Administrator

### 6.1.2 Job Management

HR users can:

* Create jobs
* Edit jobs
* Activate/deactivate jobs
* View job details

A job contains information such as title, description, responsibilities, requirements, company, and status.

### 6.1.3 Job Intelligence

The system analyzes job descriptions and produces a structured capability blueprint containing:

* Required capabilities
* Importance
* Expected proficiency
* Evidence requirements

HR users can review and modify the generated blueprint.

### 6.1.4 Candidate Applications

Candidates can:

* View available jobs
* Submit applications
* Provide application information
* Upload resumes

Applications maintain a defined lifecycle status.

### 6.1.5 Resume Processing

The system will:

* Validate uploaded resume files
* Extract resume content
* Extract structured candidate information
* Store the resulting candidate profile

Initial supported formats will be limited to formats that can be reliably processed.

### 6.1.6 Evidence and Gap Engine

The system compares job capabilities with candidate evidence.

Evidence states may include:

* Strong
* Moderate
* Weak
* Insufficient Evidence

The system distinguishes between known capabilities, weak evidence, and unknown/insufficiently evidenced capabilities.

### 6.1.7 Candidate Evidence View

HR users can view candidate evidence by capability and understand the supporting information behind the system's analysis.

### 6.1.8 Verification

For important evidence gaps, the system can recommend targeted verification activities.

Verification may include:

* Practical tasks
* Structured assessments
* Other role-specific verification methods

Verification results can update the candidate's evidence profile.

### 6.1.9 Hiring Decision

Authorized HR users can record:

* Hire
* Reject
* Further Review

The final hiring decision remains human-controlled.

---

## 6.2 Post-MVP Features

* Adaptive AI interviews
* Email-based application integration
* Expanded candidate portal
* Company knowledge management
* RAG-based company knowledge access
* Personalized employee-readiness plans
* Practical learning and skill-proof workflows

---

## 6.3 Future Features

* Post-hire outcome tracking
* Hiring decision replay
* Hiring process analysis / autopsy
* Hiring process versioning
* Candidate rediscovery
* Skill evidence freshness and re-verification
* Portable capability evidence
* ProofMesh / capability-infrastructure concepts

Future features are intentionally excluded from the initial implementation scope unless explicitly brought into scope later.

# 7. MVP Scope

## 7.1 MVP Objective

The MVP will demonstrate one complete evidence-based hiring workflow:

**Company → Job → Capability Blueprint → Candidate Application → Resume → Candidate Profile → Evidence Analysis → Gap Identification → Verification → HR Review → Hiring Decision**

The MVP will initially run locally while following production-oriented engineering practices that support future deployment.

## 7.2 In Scope

### Platform Foundation

* Authentication
* Authorization and RBAC
* Organization-level data isolation
* Configuration management
* Database migrations
* API documentation
* Error handling
* Logging
* Automated testing
* Dockerized development environment

### Hiring Workflow

* Company creation
* User management
* Job creation and management
* Job description submission
* Capability extraction
* HR review of capability blueprint
* Candidate applications
* Resume upload and processing
* Candidate profile
* Candidate-job relationships

### Evidence Workflow

* Capability and evidence representation
* Evidence classification
* Gap and unknown identification
* Evidence traceability
* Candidate evidence view
* Verification recommendations
* Practical verification
* Verification result storage
* Human hiring decision

### Engineering Quality

* Secure configuration
* Input validation
* File validation
* Database constraints
* Automated API tests
* Unit/integration tests where appropriate
* CI foundation
* Docker support
* Health checks
* Deployment documentation

## 7.3 Initial Application Entry Point

The initial MVP will support applications through the Gap2Hire application flow.

Email-based application ingestion will be introduced later. The application-processing architecture should remain extensible so additional application sources can be added without redesigning the core workflow.

## 7.4 Local-First Development

During initial development, core services may run locally, including:

* FastAPI
* PostgreSQL
* Redis
* Background workers
* Frontend
* AI services

Public job posting, production email integration, cloud deployment, and external candidate access will be introduced incrementally.

The codebase will follow production-oriented engineering practices from the beginning.

## 7.5 Out of MVP Scope

The initial MVP will not require:

* Full ATS replacement
* Large-scale public job marketplace
* Advanced video proctoring
* Face-recognition-based hiring decisions
* Voice interview system
* Full HRIS integration
* Full employee performance management
* University network
* Candidate social network
* Blockchain-based credentials
* ProofMesh infrastructure
* Large multi-agent architecture

## 7.6 MVP Demonstration

The MVP should demonstrate:

1. HR authentication
2. Job creation
3. JD submission
4. Capability extraction
5. HR capability review
6. Candidate application
7. Resume upload
8. Resume processing
9. Candidate evidence generation
10. Gap/unknown identification
11. Verification request
12. Candidate verification
13. Evidence update
14. HR evidence review
15. Human hiring decision

This workflow represents the initial product-level definition of done for the MVP.

# 8. Non-Goals

Gap2Hire is intentionally not designed to:

1. **Make fully autonomous hiring decisions**
   AI may analyze evidence and provide recommendations, but final hiring decisions remain human-controlled.

2. **Replace HR professionals**
   The platform is intended to augment recruiters and hiring managers with better evidence, verification, and workflow intelligence.

3. **Operate primarily as a resume-scoring system**
   A single opaque candidate score is not the core representation of candidate capability.

4. **Treat missing evidence as proof of missing capability**
   Insufficient evidence should remain distinguishable from demonstrated lack of skill.

5. **Automatically reject candidates solely through AI predictions**
   Important candidate decisions should remain reviewable and human-controlled.

6. **Use sensitive personal attributes as inappropriate hiring signals**
   Candidate evaluation should focus on job-relevant capabilities and evidence.

7. **Guarantee prediction of employee performance**
   Post-hire analysis is intended to identify patterns and potential process improvements, not provide deterministic predictions or unsupported causal conclusions.

8. **Become a complete HR management suite**
   Functions unrelated to the core hiring, readiness, evidence, and process-learning lifecycle are outside Gap2Hire's product purpose.
# 9. Future Scope

Gap2Hire will evolve beyond the initial evidence-based hiring workflow into a continuous hiring, readiness, development, and hiring-process improvement platform.

The following capabilities are part of the **final product vision** and will be implemented progressively after the MVP foundation.

## 9.1 AI Adaptive Interviews

Gap2Hire will provide AI-assisted interviews that dynamically adapt based on:

* Job capabilities
* Candidate evidence
* Identified gaps
* Previous answers
* Verification results

The system will focus questions on areas where additional evidence is useful rather than following the same fixed interview for every candidate.

Human oversight will remain part of important evaluation and hiring decisions.

## 9.2 Email Ingestion

Gap2Hire will support email-based candidate application ingestion.

The system will be able to process permitted recruitment emails, identify application information, extract resumes and relevant details, and create or update candidate applications.

Email ingestion will use the same underlying application and evidence pipeline as direct applications.

## 9.3 RAG and Company Knowledge

Gap2Hire will provide a company knowledge layer using Retrieval-Augmented Generation (RAG).

Company-approved knowledge may include:

* Internal documentation
* Role expectations
* Engineering practices
* Processes
* Policies
* Product information
* Onboarding material
* Training resources

This knowledge will support candidate evaluation and, after hiring, employee readiness and training.

Access to company knowledge will be controlled according to organization and user permissions.

## 9.4 Personalized Training

After hiring, Gap2Hire will use hiring evidence, identified capability gaps, job requirements, and approved company knowledge to create personalized employee readiness plans.

The system may recommend:

* Learning resources
* Practical exercises
* Company-specific tasks
* Skill-building activities
* Assessments
* Projects
* Follow-up verification

Training progress and newly generated evidence can update the employee's capability profile.

## 9.5 Post-Hire Outcomes

Gap2Hire will eventually connect hiring expectations and evidence with permitted post-hire outcomes.

Examples may include:

* Expected capabilities versus demonstrated capabilities
* Readiness progress
* Skill development
* Practical work evidence
* Manager feedback
* Role-specific outcomes

The purpose is to understand whether the hiring process produced useful evidence and where improvement may be needed.

Gap2Hire will avoid treating these relationships as automatic proof of causation.

## 9.6 Decision Replay

Gap2Hire will provide a structured way to review previous hiring decisions.

A decision replay may reconstruct:

* Job requirements
* Capability blueprint
* Candidate evidence available at the time
* Identified gaps
* Verification results
* Interview evidence
* Hiring decision
* Later permitted outcomes

This allows organizations to understand what information was available when the decision was made and how the decision can be improved.

## 9.7 Hiring Autopsy

Gap2Hire will provide deeper analysis of completed hiring processes.

The system may identify patterns such as:

* Frequently missed capabilities
* Repeated verification failures
* Weak job requirements
* Inconsistent evaluation practices
* Evidence that was insufficiently verified
* Differences between hiring expectations and later outcomes

The goal is to help organizations improve their hiring process rather than simply evaluate individual candidates.

Recommendations will remain subject to human review.

## 9.8 Candidate Rediscovery

Gap2Hire will maintain structured candidate capability and evidence information that can support future candidate rediscovery.

When a new role is created, the system may identify previously evaluated candidates whose verified or sufficiently supported capabilities match the new role.

Rediscovery can consider:

* Capability requirements
* Evidence strength
* Verification results
* Previous applications
* Skill freshness
* Candidate permissions and availability

This reduces repeated evaluation of candidates who may already have relevant evidence.

## 9.9 Final Product Lifecycle

The long-term Gap2Hire platform will connect the complete lifecycle:

**Job Requirements**
→ **Capability Blueprint**
→ **Candidate Application**
→ **Resume / Evidence**
→ **Gap & Uncertainty Analysis**
→ **Verification**
→ **AI Adaptive Interview**
→ **Human Hiring Decision**
→ **Employee Readiness**
→ **Personalized Training**
→ **Skill Proof**
→ **Post-Hire Outcomes**
→ **Decision Replay**
→ **Hiring Autopsy**
→ **Hiring Process Improvement**
→ **Candidate Rediscovery**
→ **Next Hiring Cycle**

Email ingestion and company knowledge/RAG will support multiple stages of this lifecycle.

## 9.10 Long-Term Platform Vision

The long-term vision is to make Gap2Hire an evidence-driven capability platform connecting:

**People ↔ Capabilities ↔ Evidence ↔ Companies ↔ Work ↔ Outcomes**

Future concepts such as portable capability evidence and the previously explored **ProofMesh** infrastructure may be considered after the core Gap2Hire platform has matured.

These concepts are **not part of the current MVP implementation** and will not drive the initial architecture unnecessarily.
