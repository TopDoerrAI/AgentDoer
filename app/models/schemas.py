"""API request and response models."""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to the agent")
    session_id: str | None = Field(None, description="Conversation session; omit for a new conversation")
    user_id: str | None = Field(None, description="Optional user id for persistence")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Agent reply")
    session_id: str = Field(..., description="Session id (use for follow-up messages)")
