"""
Event recommendation service.
Uses userInterestProfiles (AI & personalization) and eventAnalytics (trending).
Falls back to trending when user has no profile.
"""
import logging
import math
from datetime import datetime, timezone
from typing import Any

from app.services.firestore_client import get_db

logger = logging.getLogger(__name__)

MAX_RECOMMENDATIONS = 10
MAX_CANDIDATES = 100

# Geographic re-ranking: events within DISTANCE_BONUS_RADIUS_KM get a bonus
# inversely proportional to distance, capped at DISTANCE_BONUS_MAX.
DISTANCE_BONUS_MAX = 5.0
DISTANCE_BONUS_RADIUS_KM = 20.0


def _coerce_user_coords(lat: Any, lng: Any) -> tuple[float, float] | None:
    """
    Validate user GPS coords. Both must be finite floats and in valid lat/lng
    bounds. If either is missing or invalid, returns None (the caller silently
    drops the geographic bonus rather than erroring).
    """
    if lat is None or lng is None:
        return None
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat_f) and math.isfinite(lng_f)):
        return None
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
        return None
    return (lat_f, lng_f)


def _extract_event_coords(event: dict) -> tuple[float, float] | None:
    """
    Read finite (lat, lng) from event['venueCoordinates']. Supports a plain
    dict {lat, lng} (the documented shape) and a Firestore GeoPoint as a
    defensive fallback. Returns None for any other shape so the event is
    skipped from the distance bonus without being penalized.
    """
    coords = event.get("venueCoordinates")
    if coords is None:
        return None

    if isinstance(coords, dict):
        lat = coords.get("lat")
        lng = coords.get("lng")
    elif hasattr(coords, "latitude") and hasattr(coords, "longitude"):
        # Firestore GeoPoint
        lat = coords.latitude
        lng = coords.longitude
    else:
        return None

    if lat is None or lng is None:
        return None
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat_f) and math.isfinite(lng_f)):
        return None
    return (lat_f, lng_f)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km between two (lat, lng) points."""
    earth_radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def _distance_bonus(distance_km: float) -> float:
    """5 * max(0, 1 - min(distanceKm, 20) / 20). Zero past 20km, max at 0km."""
    return DISTANCE_BONUS_MAX * max(
        0.0, 1.0 - min(distance_km, DISTANCE_BONUS_RADIUS_KM) / DISTANCE_BONUS_RADIUS_KM
    )


def _serialize_doc(doc: Any) -> dict | None:
    """Convert Firestore doc to JSON-serializable dict."""
    if not doc or not doc.exists:
        return None
    data = doc.to_dict()
    if data is None:
        return None
    out = {"id": doc.id, **_serialize_value(data)}
    return out


def _serialize_value(val: Any) -> Any:
    """Recursively serialize Firestore values."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    if hasattr(val, "timestamp"):
        return datetime.fromtimestamp(val.timestamp(), tz=timezone.utc).isoformat()
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_serialize_value(v) for v in val]
    return val


def _parse_event_date(event: dict) -> datetime | None:
    """Parse event date for comparison."""
    d = event.get("date")
    if d is None:
        return None
    if isinstance(d, datetime):
        return d
    if hasattr(d, "timestamp"):
        return datetime.fromtimestamp(d.timestamp(), tz=timezone.utc)
    if isinstance(d, str):
        try:
            return datetime.fromisoformat(d.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


def get_user_interest_profile(user_id: str) -> dict | None:
    """Fetch userInterestProfiles doc. Returns None if missing or empty."""
    try:
        doc = get_db().collection("userInterestProfiles").document(user_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if not data:
            return None
        return data
    except Exception as e:
        logger.warning("Failed to fetch userInterestProfiles for %s: %s", user_id, e)
        return None


def get_event_analytics(event_ids: list[str]) -> dict[str, dict]:
    """Fetch eventAnalytics for given event IDs. Returns {eventId: analytics_dict}."""
    if not event_ids:
        return {}
    result: dict[str, dict] = {}
    db = get_db()
    for eid in event_ids[:50]:
        try:
            doc = db.collection("eventAnalytics").document(eid).get()
            if doc.exists and doc.to_dict():
                result[eid] = doc.to_dict()
        except Exception as e:
            logger.debug("Failed to fetch eventAnalytics for %s: %s", eid, e)
    return result


def get_upcoming_events(limit: int = MAX_CANDIDATES) -> list[dict]:
    """Fetch active, public, upcoming events."""
    now = datetime.now(timezone.utc)
    events: list[dict] = []
    try:
        # Firestore: status==active
        q = (
            get_db()
            .collection("events")
            .where("status", "==", "active")
            .limit(limit)
        )
        for doc in q.stream():
            data = doc.to_dict()
            if data is None:
                continue
            if data.get("isPublic") is False:
                continue
            event_dt = _parse_event_date(data)
            if event_dt and event_dt < now:
                continue  # Skip past events
            events.append({"id": doc.id, **data})
    except Exception as e:
        logger.warning("Failed to fetch events: %s", e)
    return events


def score_event_with_profile(event: dict, profile: dict) -> float:
    """Score event based on userInterestProfiles."""
    score = 0.0
    top_categories = profile.get("topCategories") or {}
    top_cities = profile.get("topCities") or {}
    price_pref = profile.get("pricePreference")

    # Category match
    cat = event.get("category") or event.get("categoryName")
    if cat and cat in top_categories:
        score += float(top_categories.get(cat, 0))

    # City match
    city = event.get("city") or (event.get("location") or "").split(",")[0].strip()
    if city and city in top_cities:
        score += float(top_cities.get(city, 0))

    # Price preference
    price = event.get("price")
    if price is not None and price_pref:
        is_free = price == 0 or (
            isinstance(event.get("ticketTypes"), dict)
            and event.get("ticketTypes", {}).get("free", {}).get("price") == 0
        )
        if price_pref == "free" and is_free:
            score += 5
        elif price_pref == "paid" and not is_free:
            score += 2

    return score


def score_event_trending(event: dict, analytics: dict[str, dict]) -> float:
    """Score event based on eventAnalytics (views, favorites)."""
    eid = event.get("id")
    if not eid:
        return 0
    a = analytics.get(eid)
    if not a:
        return 0
    views = float(a.get("views", 0))
    favorites = float(a.get("favorites", 0))
    shares = float(a.get("shares", 0))
    conversion = float(a.get("conversionRate", 0))
    return views * 0.1 + favorites * 2 + shares * 1.5 + conversion * 10


def recommend_events(
    user_id: str | None = None,
    limit: int = MAX_RECOMMENDATIONS,
    user_lat: Any = None,
    user_lng: Any = None,
) -> dict:
    """
    Get personalized or trending event recommendations.
    - If user_id and userInterestProfiles exists: score by topCategories, topCities, pricePreference
    - Else: use eventAnalytics (trending)
    - Excludes past events
    - If valid user_lat / user_lng are provided AND the event has finite
      venueCoordinates.lat/lng, adds a small distance bonus (max +5 at 0km,
      0 past 20km) and includes distanceKm on the response item. Events
      without venue coords keep their pre-distance score (no penalty).
    """
    events = get_upcoming_events(limit=MAX_CANDIDATES)
    if not events:
        return {"events": [], "source": "none"}

    profile = get_user_interest_profile(user_id) if user_id else None
    analytics = get_event_analytics([e.get("id") for e in events if e.get("id")])
    user_coords = _coerce_user_coords(user_lat, user_lng)

    # Filter past events
    now = datetime.now(timezone.utc)
    events = [e for e in events if (_parse_event_date(e) or now) >= now]

    # Per-event distance: None when we can't compute it (no user coords or no
    # event coords). Stored in a side map keyed by id() so we don't mutate the
    # event dict before scoring.
    distances: dict[int, float] = {}
    if user_coords is not None:
        u_lat, u_lng = user_coords
        for e in events:
            ev_coords = _extract_event_coords(e)
            if ev_coords is None:
                continue
            distances[id(e)] = _haversine_km(u_lat, u_lng, ev_coords[0], ev_coords[1])

    def _bonus_for(e: dict) -> float:
        d = distances.get(id(e))
        return _distance_bonus(d) if d is not None else 0.0

    if profile and (profile.get("topCategories") or profile.get("topCities")):
        # Personalized scoring + distance bonus
        scored = [(e, score_event_with_profile(e, profile) + _bonus_for(e)) for e in events]
        source = "personalized"
    else:
        # Trending fallback + distance bonus
        scored = [(e, score_event_trending(e, analytics) + _bonus_for(e)) for e in events]
        source = "trending"

    # Sort by score desc, then by date asc (soonest first)
    def _sort_key(item):
        e, s = item
        d = _parse_event_date(e)
        ts = d.timestamp() if d else float("inf")
        return (s, -ts)

    scored.sort(key=_sort_key, reverse=True)

    # Take top N, serialize for response
    recommended = [e for e, _ in scored[:limit]]
    out: list[dict] = []
    for e in recommended:
        item = _serialize_value({**e, "id": e.get("id")})
        d = distances.get(id(e))
        # Only include distanceKm when we actually computed it; events without
        # venue coords (or when user coords were absent/invalid) get no field
        # rather than a misleading null.
        if d is not None:
            item["distanceKm"] = round(d, 2)
        out.append(item)

    return {"events": out, "source": source}
