"""API routes for event recommendations."""
from fastapi import APIRouter, HTTPException, Query

from app.services.recommender import recommend_events

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", summary="Get recommended events")
def get_recommendations(
    user_id: str | None = Query(None, description="User ID for personalized recommendations (optional)"),
    limit: int = Query(10, ge=1, le=50, description="Max number of events to return"),
    # lat/lng are accepted as strings so that malformed values can be silently
    # ignored (per spec: "if either is missing or invalid, ignore both, don't
    # error") instead of producing a FastAPI 422. Validation happens in the
    # service's _coerce_user_coords.
    lat: str | None = Query(None, description="User latitude for distance-based ranking (optional)"),
    lng: str | None = Query(None, description="User longitude for distance-based ranking (optional)"),
):
    """
    Returns personalized event recommendations when user_id is provided and
    userInterestProfiles exists. Otherwise returns trending events from eventAnalytics.
    When valid lat/lng are provided, events near the user (within 20km) get a
    small ranking bonus and a distanceKm field on the response.
    """
    try:
        return recommend_events(user_id=user_id, limit=limit, user_lat=lat, user_lng=lng)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Recommendation service unavailable: {str(e)}")
