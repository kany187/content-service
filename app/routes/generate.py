from fastapi import APIRouter

from app.schema.event import (
    DescriptionInput,
    EventInput,
    FormAssistInput,
    PoliciesInput,
    TagsInput,
)
from app.services.ai_generator import (
    generate_description,
    generate_form_assist,
    generate_policies,
    generate_tags,
)

router = APIRouter(prefix="/ai")


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/generate", summary="Generate description (legacy)")
def generate_legacy(data: EventInput):
    """Legacy endpoint: generates description from title, city, category."""
    return generate_description(data)


@router.post("/generate/description", summary="Generate event description")
def generate_description_endpoint(data: DescriptionInput):
    """Generate a captivating event description. Supports venue, eventType, language."""
    return generate_description(data)


@router.post("/generate/tags", summary="Suggest tags")
def generate_tags_endpoint(data: TagsInput):
    """Generate relevant tags for discovery and search."""
    return generate_tags(data)


@router.post("/generate/policies", summary="Generate policy templates")
def generate_policies_endpoint(data: PoliciesInput):
    """Generate refund and cancellation policy templates."""
    return generate_policies(data)


@router.post("/generate/form-assist", summary="Form assist (combined)")
def generate_form_assist_endpoint(data: FormAssistInput):
    """Generate description, tags, suggested venue, and policies in one call."""
    return generate_form_assist(data)
