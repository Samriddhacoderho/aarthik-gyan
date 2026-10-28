from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile, status

from api.errors import ApiError
from api.schemas import (
    AskRequest,
    AskResponse,
    CompanySummary,
    DeleteDocumentResponse,
    DocumentSummary,
    EvidenceHit,
    EvidenceSearchResponse,
    JobResponse,
    UploadResponse,
)
from api.services import document_service, graph_service, ingestion_service, qa_service

router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents() -> list[DocumentSummary]:
    return graph_service.list_documents()


@router.get("/documents/{document_hash}", response_model=DocumentSummary)
def get_document(document_hash: str) -> DocumentSummary:
    return graph_service.get_document(document_hash)


@router.delete("/documents/{document_hash}", response_model=DeleteDocumentResponse)
def delete_document(document_hash: str) -> DeleteDocumentResponse:
    return document_service.delete_document(document_hash)


@router.post(
    "/documents/{document_hash}/retry",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_document(
    document_hash: str,
    background_tasks: BackgroundTasks,
) -> JobResponse:
    job_id, path = ingestion_service.prepare_retry(document_hash)
    background_tasks.add_task(ingestion_service.run_ingest_job, job_id, str(path))
    return JobResponse(**ingestion_service.get_job(job_id))


@router.get(
    "/documents/{document_hash}/companies",
    response_model=list[CompanySummary],
)
def get_document_companies(document_hash: str) -> list[CompanySummary]:
    return graph_service.get_document_companies(document_hash)


@router.get("/documents/{document_hash}/search", response_model=EvidenceSearchResponse)
def search_document(
    document_hash: str,
    query: str = Query(min_length=1, max_length=500),
    top_k: int = Query(default=5, ge=1, le=10),
) -> EvidenceSearchResponse:
    graph_service.get_document(document_hash)
    try:
        from vectorstore.indexer import search_chunks

        rows = search_chunks(query, top_k=top_k, document_hash=document_hash)
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(
            503,
            "vector_search_unavailable",
            "Document evidence search is unavailable. Check Qdrant connectivity.",
        ) from exc

    return EvidenceSearchResponse(
        document_hash=document_hash,
        query=query,
        results=[
            EvidenceHit(
                text=str(row.get("text", "")),
                filename=row.get("filename"),
                score=float(row.get("score", 0.0)),
            )
            for row in rows
        ],
    )


@router.post("/documents/{document_hash}/ask", response_model=AskResponse)
def ask_document(document_hash: str, payload: AskRequest) -> AskResponse:
    return qa_service.ask_document(document_hash, payload.question)


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs() -> list[JobResponse]:
    return [JobResponse(**job) for job in ingestion_service.list_jobs()]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    return JobResponse(**ingestion_service.get_job(job_id))


@router.post(
    "/documents",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> UploadResponse:
    document_hash, filename, size, path = await ingestion_service.save_upload(file)
    job_id = ingestion_service.create_job(filename, document_hash, path)
    background_tasks.add_task(ingestion_service.run_ingest_job, job_id, str(path))
    return UploadResponse(
        job_id=job_id,
        status="queued",
        filename=filename,
        size_bytes=size,
        document_hash=document_hash,
    )
