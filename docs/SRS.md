# 1. System Requirements

Gap2Hire shall provide an evidence-based hiring and employee-readiness platform that connects job requirements, candidate evidence, verification, hiring decisions, employee development, and post-hire learning.

## 1.1 Core Requirements

The system shall:

1. Support secure user authentication and role-based access.
2. Support organization-level data isolation.
3. Allow companies to create and manage job openings.
4. Convert job descriptions into structured capability requirements.
5. Allow candidates to submit applications and resumes.
6. Process resumes and create structured candidate information.
7. Analyze candidate evidence against required capabilities.
8. Identify strong, weak, and insufficient evidence.
9. Support targeted verification through practical assessments and interviews.
10. Provide HR and hiring managers with an evidence-based candidate view.
11. Keep final hiring decisions under human control.
12. Support AI-assisted adaptive interviews.
13. Support email-based application ingestion.
14. Support company knowledge through RAG.
15. Support personalized employee training and readiness.
16. Store permitted post-hire outcomes and development evidence.
17. Support hiring decision replay and hiring-process analysis.
18. Support candidate rediscovery for future job opportunities.

## 1.2 System Principles

The system shall follow these principles:

* Evidence over unsupported claims.
* Insufficient evidence does not mean lack of skill.
* AI assists; humans make important decisions.
* Candidate and company data must be appropriately protected.
* AI outputs should be structured, traceable, and reviewable.
* The system should be modular so future capabilities can be added without major architectural changes.


# 2. Functional Requirements

## 2.1 Authentication & Users

* Users shall be able to register and authenticate securely.
* The system shall support Company Admin, Recruiter/HR, Hiring Manager, Candidate, and Platform Admin roles.
* Users shall only access resources permitted by their role and organization.

## 2.2 Job Management

* HR users shall create, update, activate, and manage jobs.
* Users shall submit job descriptions for analysis.
* The system shall generate a structured capability blueprint from the job description.
* HR shall be able to review and modify the generated blueprint.

## 2.3 Candidate Applications

* Candidates shall be able to apply for jobs.
* The system shall accept and validate supported resume files.
* The system shall extract relevant information from resumes.
* Email ingestion shall provide an additional application entry point.

## 2.4 Evidence & Gap Analysis

* The system shall represent required job capabilities.
* Candidate evidence shall be mapped to relevant capabilities.
* Evidence shall be classified according to its strength and sufficiency.
* The system shall identify weak or insufficient evidence.
* The system shall provide traceability for important evidence and AI-generated results.

## 2.5 Verification & Interviews

* The system shall identify capabilities that require additional verification.
* HR shall be able to request or approve verification activities.
* Candidates shall be able to complete permitted verification tasks.
* The system shall store verification results as evidence.
* AI adaptive interviews shall adjust questions based on candidate evidence and identified gaps.

## 2.6 Hiring Decisions

* HR and Hiring Managers shall be able to review candidate evidence.
* The system shall present evidence, verification results, and interview information.
* Authorized users shall record hiring decisions.
* AI shall not make the final hiring decision.

## 2.7 Company Knowledge & Training

* Companies shall be able to provide approved knowledge sources.
* The system shall retrieve relevant company knowledge using RAG.
* The system shall use permitted hiring evidence and identified gaps to support personalized training.
* Training progress and newly generated skill evidence may be recorded.

## 2.8 Post-Hire & Process Learning

* The system shall support recording permitted post-hire outcomes.
* The system shall support replaying previous hiring decisions using available evidence.
* The system shall analyze hiring processes to identify improvement opportunities.
* The system shall support rediscovering suitable previous candidates for new roles.

## 2.9 Auditability

* Important hiring, verification, AI-analysis, and administrative actions shall be recorded.
* Changes to important records shall be traceable where required.

# 3. Non-Functional Requirements

## 3.1 Security

* Authentication and authorization shall be implemented securely.
* Organization data shall be isolated between tenants.
* User input and uploaded files shall be validated.
* Sensitive data shall be appropriately protected.
* AI tools and external integrations shall use controlled permissions.

## 3.2 Reliability

* The system shall handle expected errors gracefully.
* Invalid requests shall return clear and consistent errors.
* Important operations shall maintain data consistency.
* Background processing failures shall be handled safely.

## 3.3 Performance

* APIs shall provide reasonable response times for normal operations.
* Long-running tasks such as resume processing and AI analysis shall be handled asynchronously where appropriate.
* Database queries shall be designed for efficient retrieval.

## 3.4 Scalability

* The backend shall use a modular architecture.
* Background workers shall allow processing workloads to scale independently.
* The system shall support multiple organizations without exposing cross-organization data.

## 3.5 Maintainability

* Code shall follow clear project structure and separation of responsibilities.
* Python code shall use type hints and consistent conventions.
* Configuration shall be environment-based.
* Database changes shall use migrations.
* Core functionality shall have automated tests.

## 3.6 AI Quality

* AI outputs shall use structured formats where appropriate.
* Important AI-generated results shall be reviewable by humans.
* AI behavior shall be evaluated using defined test cases and datasets.
* The system shall avoid treating unsupported AI output as verified evidence.

# 4. Technology Stack

| Area                    | Technology                              |
| ----------------------- | --------------------------------------- |
| Backend                 | Python + FastAPI                        |
| Database                | PostgreSQL                              |
| Cloud Database          | Supabase                                |
| Vector Search           | pgvector                                |
| Cache / Background Jobs | Redis                                   |
| AI / LLM                | LLM APIs                                |
| AI Frameworks           | LangChain / LangGraph where appropriate |
| RAG                     | PostgreSQL + pgvector                   |
| Local Environment       | Docker                                  |
| API Documentation       | FastAPI / OpenAPI                       |
| Testing                 | Pytest                                  |
| Version Control         | Git + GitHub                            |

The system shall be designed so that local development and cloud deployment can use the same core application architecture.
