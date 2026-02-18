"""Firestore client for content-service."""
from functools import lru_cache

from google.cloud import firestore

from app.core.config import settings


@lru_cache(maxsize=1)
def get_db() -> firestore.Client:
    """Get Firestore client (cached singleton)."""
    return firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
