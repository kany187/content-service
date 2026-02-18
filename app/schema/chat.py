"""Chat API schemas."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    message: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = Field(None, description="User ID for personalization and context")
    event_id: Optional[str] = Field(None, description="Current event context (if user is viewing an event)")
    user_type: Optional[Literal["attendee", "organizer"]] = Field(
        None, description="attendee or organizer for tailored support"
    )
    conversation_id: Optional[str] = Field(None, description="For threading (future use)")
    language: Optional[str] = Field("fr", description="Preferred response language (fr, en)")


class ChatResponse(BaseModel):
    """Response from the chat service."""

    reply: str
    conversation_id: Optional[str] = None
