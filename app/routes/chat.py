"""AI chat support API routes."""
from fastapi import APIRouter, HTTPException

from app.schema.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, summary="Send a chat message")
def chat_endpoint(req: ChatRequest) -> ChatResponse:
    """
    Send a message to the AI support assistant. Returns a helpful reply.
    Optionally provide user_id, event_id, user_type for personalized context.
    """
    try:
        result = chat(
            message=req.message,
            user_id=req.user_id,
            event_id=req.event_id,
            user_type=req.user_type,
            language=req.language,
        )
        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail="Chat service temporarily unavailable. Please try again.",
        ) from e
