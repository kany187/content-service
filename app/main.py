import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routes import chat, generate, recommend

app = FastAPI(title='AI Content Service')

app.include_router(generate.router)
app.include_router(recommend.router)
app.include_router(chat.router)


@app.on_event("startup")
def validate_api_key():
    """Check API key format at startup - log warning if suspicious."""
    key = settings.OPENAI_API_KEY
    if "\n" in key or "\r" in key:
        logging.warning("OPENAI_API_KEY contains newline/carriage return - this will cause requests to fail")
    if not key.startswith("sk-"):
        logging.warning("OPENAI_API_KEY does not start with sk- - may be invalid")


@app.exception_handler(Exception)
async def catch_all_handler(request: Request, exc: Exception):
    """Catch any unhandled exception and return 503 instead of 500."""
    logging.exception("Unhandled exception: %s", exc)
    err = str(exc).lower()
    if "illegal header" in err or "header value" in err:
        return JSONResponse(
            status_code=503,
            content={"detail": "API key has invalid characters (e.g. newline). Re-add secret with: echo -n 'sk-...' | gcloud secrets versions add openai-api-key --data-file=-"},
        )
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable. Please try again."},
    )