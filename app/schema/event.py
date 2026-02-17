from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DescriptionInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    title: str
    city: str
    category: str
    venue: Optional[str] = None
    event_type: Optional[str] = Field(None, alias="eventType")
    language: Optional[str] = "fr"
    max_length: Optional[int] = Field(500, alias="maxLength")


class DescriptionOutput(BaseModel):
    description: str


class TagsInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    title: str
    category: str
    city: Optional[str] = None


class TagsOutput(BaseModel):
    tags: list[str]


class PoliciesInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    event_type: Optional[str] = Field("paid", alias="eventType")
    currency: Optional[str] = "CDF"
    language: Optional[str] = "fr"


class PoliciesOutput(BaseModel):
    refund_policy: str = Field(..., alias="refundPolicy")
    cancellation_policy: str = Field(..., alias="cancellationPolicy")


class FormAssistInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    title: str
    category: str
    city: Optional[str] = None
    venue: Optional[str] = None
    language: Optional[str] = "fr"


class FormAssistOutput(BaseModel):
    description: str
    tags: list[str]
    suggested_venue: Optional[str] = Field(None, alias="suggestedVenue")
    refund_policy: str = Field(..., alias="refundPolicy")
    cancellation_policy: str = Field(..., alias="cancellationPolicy")


# Backward compatibility alias
class EventInput(BaseModel):
    title: str
    city: str
    category: str
