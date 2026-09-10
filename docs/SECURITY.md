# Gap2Hire Security

## 1. Authentication

* Protected APIs shall require authenticated users.
* Passwords shall never be stored in plain text.
* Authentication tokens shall be handled securely.
* Sessions/tokens shall have appropriate expiration and validation.

## 2. Authorization

* Access shall be controlled using role-based permissions.
* Users shall only access resources they are authorized to access.
* Organization-owned resources shall be isolated between organizations.
* Platform Admin permissions shall be separate from company-level permissions.

## 3. Input & File Security

* API inputs shall be validated using defined schemas.
* Uploaded resumes and documents shall be validated for supported file types and size limits.
* File names and paths shall not be trusted directly from users.
* Untrusted document content shall not automatically be treated as instructions.

## 4. AI Security

* AI-generated content shall be treated as untrusted output.
* AI output shall be validated before being used by the application.
* Important AI decisions shall require appropriate human review.
* Prompt injection and malicious document content shall be considered during AI processing.
* AI tools shall only receive the permissions and data required for their task.

## 5. Data Protection

* Sensitive information shall be protected during storage and transmission.
* Secrets and API keys shall be stored using environment-based configuration and shall not be committed to source control.
* Production credentials shall be separated from development credentials.
* Access to company and candidate information shall be limited according to authorization rules.

## 6. Database Security

* Database access shall use controlled credentials.
* Foreign keys and constraints shall protect data integrity.
* Queries shall use parameterized/database-safe mechanisms.
* Cross-organization data access shall be prevented at the application level and strengthened with database-level controls where appropriate.

## 7. Auditability

Important actions shall be logged or audited where appropriate, including:

* Authentication events
* Permission-sensitive actions
* Hiring decisions
* Verification activities
* Important AI-generated evaluations
* Administrative changes

## 8. Security Principle

> **Treat user input, uploaded documents, AI output, and external data as untrusted until validated and authorized.**
