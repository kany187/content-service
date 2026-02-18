from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

# Load .env from project root only if it exists (Cloud Run uses env vars)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
_model_config: dict = {}
if _env_path.exists():
    _model_config["env_file"] = _env_path


class Settings(BaseSettings):
    OPENAI_API_KEY: str
    GOOGLE_CLOUD_PROJECT: str = "biso-event"

    model_config = _model_config

    @field_validator("OPENAI_API_KEY", mode="before")
    @classmethod
    def strip_api_key(cls, v: str) -> str:
        """Remove whitespace/newlines - Secret Manager often adds trailing newline."""
        return v.strip() if isinstance(v, str) else v


settings = Settings()

