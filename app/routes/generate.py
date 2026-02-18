import logging

import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import settings
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


@router.get("/status")
def status_check():
    """Check if API key format is valid (does not expose the key)."""
    key = settings.OPENAI_API_KEY
    has_newline = "\n" in key or "\r" in key
    return {
        "status": "ok",
        "api_key_format_valid": not has_newline and key.startswith("sk-") and len(key) > 20,
    }


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
    try:
        return generate_form_assist(data)
    except httpx.HTTPError as e:
        logging.exception("Form assist HTTP error: %s", e)
        err = str(e).lower()
        if "illegal header" in err or "header value" in err or "\\n" in repr(e):
            raise HTTPException(
                status_code=503,
                detail="API key invalid (trailing newline?). Update openai-api-key in Secret Manager with: echo -n 'sk-...' | gcloud secrets versions add openai-api-key --data-file=-",
            )
        raise HTTPException(status_code=503, detail="AI service connection error. Please try again.")
    except Exception as e:
        logging.exception("Form assist failed: %s", e)
        err = str(e).lower()
        if "api_key" in err or "authentication" in err:
            raise HTTPException(status_code=503, detail="AI service misconfigured. Check OPENAI_API_KEY.")
        if "rate" in err or "quota" in err:
            raise HTTPException(status_code=503, detail="AI service temporarily unavailable. Try again later.")
        raise HTTPException(status_code=503, detail="AI service error. Please try again later.")
