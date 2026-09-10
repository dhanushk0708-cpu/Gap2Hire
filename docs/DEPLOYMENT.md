# Gap2Hire Deployment

## 1. Development

Gap2Hire will be developed and tested locally using:

* FastAPI
* PostgreSQL / Supabase
* Redis
* Background workers
* AI services
* Docker where appropriate

Development configuration will be managed using environment variables.

## 2. Cloud

Supabase will provide the managed PostgreSQL database for cloud environments.

The application backend can be deployed separately and will connect securely to the Supabase database.

## 3. Environment Configuration

Separate configuration will be maintained for:

* Development
* Testing
* Production

Secrets such as database credentials and AI API keys shall not be committed to the repository.

## 4. Docker

Docker will be used to provide consistent development and deployment environments.

The application should be runnable without depending on machine-specific configuration.

## 5. Health Checks

The backend shall provide health checks for important dependencies where appropriate.

Example:

```text
GET /health
```

## 6. Deployment Principle

> **Develop locally, keep the application deployment-ready, and introduce production infrastructure only when required.**
