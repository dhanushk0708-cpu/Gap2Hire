from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


app.include_router(auth_router)
app.include_router(jobs_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "environment": settings.environment,
    }