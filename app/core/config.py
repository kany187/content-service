from pathlib import Path

from pydantic_settings import BaseSettings

# Load .env from project root only if it exists (Cloud Run uses env vars)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
_model_config: dict = {}
if _env_path.exists():
    _model_config["env_file"] = _env_path


class Settings(BaseSettings):
    OPENAI_API_KEY: str

    model_config = _model_config


settings = Settings()

