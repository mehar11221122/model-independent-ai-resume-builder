"""Resume vertical endpoints.

This module contains zero resume-specific business logic - it only wires
HTTP <-> the generic engine workflow registered under the "resume" key. That
is deliberate: it doubles as the reference implementation for how a future
vertical (marketing, automotive, legal) would expose its own routes.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import require_api_key
from app.graph.registry import get_workflow
from app.ingestion.dispatch import load_any
from app.ingestion.merge import merge_documents
from app.schemas.common import AnswersRequest, SessionResponse
from app.storage.dispatch import save_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resume", tags=["resume"], dependencies=[Depends(require_api_key)])


def _state_to_response(thread_id: str, state: dict) -> SessionResponse:
    return SessionResponse(
        thread_id=thread_id,
        status=state.get("status", "in_progress"),
        follow_up_questions=state.get("follow_up_questions", []),
        structured_output=state.get("structured_output"),
        validation_errors=state.get("validation_errors", []),
    )


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    language: str = Form(default="en"),
    text: str | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None),
) -> SessionResponse:
    documents = []

    if text:
        from app.ingestion.text_loader import load_text

        documents.append(load_text("inline_text", text))

    for upload in files or []:
        data = await upload.read()
        try:
            document = load_any(upload.filename, data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            document.storage_uri = save_upload(upload.filename, data)
        except Exception:  # noqa: BLE001 - storage failure shouldn't block generation
            logger.warning("Failed to persist upload %s to storage backend.", upload.filename)

        documents.append(document)

    if not documents:
        raise HTTPException(status_code=400, detail="Provide at least one of: text, files.")

    merged_text = merge_documents(documents)
    thread_id = str(uuid.uuid4())

    workflow = get_workflow("resume")
    initial_state = {
        "thread_id": thread_id,
        "vertical": "resume",
        "language": language,
        "raw_documents": [doc.model_dump() for doc in documents],
        "merged_text": merged_text,
        "extracted_data": {},
        "user_answers": {},
        "retry_count": 0,
        "status": "in_progress",
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = workflow.invoke(initial_state, config)

    return _state_to_response(thread_id, result)


@router.post("/sessions/{thread_id}/answers", response_model=SessionResponse)
def submit_answers(thread_id: str, payload: AnswersRequest) -> SessionResponse:
    from app.graph.workflow import resume_with_answers

    workflow = get_workflow("resume")
    result = resume_with_answers(workflow, thread_id, payload.answers)
    return _state_to_response(thread_id, result)


@router.get("/sessions/{thread_id}", response_model=SessionResponse)
def get_session(thread_id: str) -> SessionResponse:
    workflow = get_workflow("resume")
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = workflow.get_state(config)

    if not snapshot or not snapshot.values:
        raise HTTPException(status_code=404, detail="Session not found.")

    return _state_to_response(thread_id, snapshot.values)
