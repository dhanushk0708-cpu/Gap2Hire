import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.applications import router as applications_router
from app.api.auth import router as auth_router
from app.api.candidate_sources import router as candidate_sources_router
from app.api.candidates import router as candidates_router
from app.api.capabilities import router as capabilities_router
from app.api.email_connections import email_router, router as email_connections_router
from app.api.interview_rounds import router as interview_rounds_router
from app.api.interview_ws import router as interview_ws_router
from app.api.interviews import router as interviews_router
from app.api.jd_analysis import router as jd_analysis_router
from app.api.jobs import router as jobs_router
from app.api.research_state import router as research_state_router
from app.api.demo import router as demo_router
from app.api.interview_datasets import router as interview_datasets_router
from app.api.interview_plans import router as interview_plans_router
from app.api.interview_schedules import router as interview_schedules_router
from app.api.screening import router as screening_router
from app.api.verifications import router as verifications_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

# CORS middleware for seamless browser communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(capabilities_router)
app.include_router(jd_analysis_router)
app.include_router(candidates_router)
app.include_router(applications_router)
app.include_router(candidate_sources_router)
app.include_router(research_state_router)
app.include_router(verifications_router)
app.include_router(interview_rounds_router)
app.include_router(interviews_router)
app.include_router(interview_schedules_router)
app.include_router(interview_ws_router)
app.include_router(email_connections_router)
app.include_router(email_router)
app.include_router(screening_router)
app.include_router(demo_router)
app.include_router(interview_datasets_router)
app.include_router(interview_plans_router)



@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "environment": settings.environment,
    }


# Mount Frontend Static SPA
static_dir = Path(__file__).resolve().parent / "static"
if not static_dir.exists():
    static_dir.mkdir(parents=True, exist_ok=True)

app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")