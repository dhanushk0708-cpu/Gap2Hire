from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.interview_dataset import (
    DatasetUploadResponse,
    InterviewDatasetFileResponse,
    QuestionDatasetItem,
)
from app.services.interview_dataset import (
    DatasetNotFoundError,
    DatasetParsingError,
    get_interview_dataset_file,
    list_interview_dataset_files,
    save_uploaded_interview_dataset,
)

router = APIRouter(
    prefix="/api/v1/interview-datasets",
    tags=["Interview Datasets"],
)

require_hr = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_interview_dataset_endpoint(
    file: UploadFile = File(...),
    job_id: UUID | None = Form(None),
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Uploads and parses an Excel (.xlsx) file containing interview question datasets.
    Understands multiple distinct datasets/concepts within the single uploaded file.
    Validates structure, prevents corrupt data, and saves under tenant isolation.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty.",
        )

    file_bytes = await file.read()
    try:
        dataset_file = await save_uploaded_interview_dataset(
            session=session,
            organization_id=current_user.organization_id,
            filename=file.filename,
            file_bytes=file_bytes,
            job_id=job_id,
            created_by=current_user.id,
        )

        return DatasetUploadResponse(
            file_id=dataset_file.id,
            filename=dataset_file.filename,
            total_questions=dataset_file.total_questions,
            datasets=[
                QuestionDatasetItem(
                    id=d.id,
                    name=d.name,
                    concept=d.concept,
                    description=d.description,
                    question_count=d.question_count,
                    questions=[],
                )
                for d in dataset_file.datasets
            ],
            warnings=[],
        )
    except DatasetParsingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except DatasetNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "",
    response_model=list[InterviewDatasetFileResponse],
    status_code=status.HTTP_200_OK,
)
async def list_interview_datasets_endpoint(
    job_id: UUID | None = None,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """Lists uploaded interview dataset files for the organization."""
    files = await list_interview_dataset_files(
        session=session,
        organization_id=current_user.organization_id,
        job_id=job_id,
    )
    results = []
    for f in files:
        results.append(
            InterviewDatasetFileResponse(
                id=f.id,
                filename=f.filename,
                job_id=f.job_id,
                total_questions=f.total_questions,
                dataset_count=len(f.datasets),
                datasets=[
                    QuestionDatasetItem(
                        id=d.id,
                        name=d.name,
                        concept=d.concept,
                        description=d.description,
                        question_count=d.question_count,
                        questions=[],
                    )
                    for d in f.datasets
                ],
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
        )
    return results


@router.get(
    "/{file_id}",
    response_model=InterviewDatasetFileResponse,
    status_code=status.HTTP_200_OK,
)
async def get_interview_dataset_endpoint(
    file_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """Fetches details and all questions for an interview dataset file."""
    try:
        f = await get_interview_dataset_file(
            session=session,
            organization_id=current_user.organization_id,
            file_id=file_id,
        )
        return InterviewDatasetFileResponse(
            id=f.id,
            filename=f.filename,
            job_id=f.job_id,
            total_questions=f.total_questions,
            dataset_count=len(f.datasets),
            datasets=[
                QuestionDatasetItem(
                    id=d.id,
                    name=d.name,
                    concept=d.concept,
                    description=d.description,
                    question_count=d.question_count,
                    questions=d.questions,
                )
                for d in f.datasets
            ],
            created_at=f.created_at,
            updated_at=f.updated_at,
        )
    except DatasetNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
