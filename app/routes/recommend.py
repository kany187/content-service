"""API routes for event recommendations."""
from fastapi import APIRouter, HTTPException, Query

from app.services.recommender import recommend_events

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", summary="Get recommended events")
def get_recommendations(
    user_id: str | None = Query(None, description="User ID for personalized recommendations (optional)"),
    limit: int = Query(10, ge=1, le=50, description="Max number of events to return"),
):
    """
    Returns personalized event recommendations when user_id is provided and
    userInterestProfiles exists. Otherwise returns trending events from eventAnalytics.
    """
    try:
        return recommend_events(user_id=user_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Recommendation service unavailable: {str(e)}")
