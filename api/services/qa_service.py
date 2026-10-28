"""Document question answering.

Wraps the V3 ``agent.qa_agent.answer_question`` entrypoint, which is the same
Q&A round ``main.py`` runs after ingestion. Retrieval, prompting, and the LLM
choice stay in V3; this module only validates the request and maps failures to
safe API errors.
"""

from __future__ import annotations

from api.errors import ApiError
from api.schemas import AskResponse


def _answer_question(question: str) -> str:
    # Imported lazily: agent.qa_agent pulls in config and the LLM clients.
    from agent.qa_agent import answer_question

    return answer_question(question)


def ask_document(document_hash: str, question: str) -> AskResponse:
    from api.services.graph_service import get_document

    document = get_document(document_hash)
    cleaned = question.strip()
    if not cleaned:
        raise ApiError(400, "empty_question", "Enter a question first.")
    if document.status not in {"completed", "partial"}:
        raise ApiError(
            409,
            "document_not_ready",
            "This document has not finished ingesting yet. Ask again once ingestion completes.",
        )

    try:
        answer = _answer_question(cleaned)
    except Exception as exc:
        # Keep provider/database details in the logs, not in the browser.
        raise ApiError(
            503,
            "question_unavailable",
            "The document assistant is unavailable. Check the model and database configuration.",
        ) from exc

    if not answer:
        raise ApiError(
            502,
            "empty_answer",
            "The assistant returned an empty answer. Try rephrasing the question.",
        )

    return AskResponse(document_hash=document_hash, question=cleaned, answer=answer)
