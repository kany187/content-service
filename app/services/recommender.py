"""
Event recommendation service.
Uses userInterestProfiles (AI & personalization) and eventAnalytics (trending).
Falls back to trending when user has no profile.
"""
import logging
from datetime import datetime, timezone
from typing import Any

from app.services.firestore_client import get_db

logger = logging.getLogger(__name__)

MAX_RECOMMENDATIONS = 10
MAX_CANDIDATES = 100


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


def recommend_events(user_id: str | None = None, limit: int = MAX_RECOMMENDATIONS) -> dict:
    """
    Get personalized or trending event recommendations.
    - If user_id and userInterestProfiles exists: score by topCategories, topCities, pricePreference
    - Else: use eventAnalytics (trending)
    - Excludes past events
    """
    events = get_upcoming_events(limit=MAX_CANDIDATES)
    if not events:
        return {"events": [], "source": "none"}

    profile = get_user_interest_profile(user_id) if user_id else None
    analytics = get_event_analytics([e.get("id") for e in events if e.get("id")])

    # Filter past events
    now = datetime.now(timezone.utc)
    events = [e for e in events if (_parse_event_date(e) or now) >= now]

    if profile and (profile.get("topCategories") or profile.get("topCities")):
        # Personalized scoring
        scored = [
            (e, score_event_with_profile(e, profile))
            for e in events
        ]
        # Sort by score desc, then by date asc (soonest first)
        def _sort_key(item):
            e, s = item
            d = _parse_event_date(e)
            ts = d.timestamp() if d else float("inf")
            return (s, -ts)  # higher score first; same score -> sooner date first

        scored.sort(key=_sort_key, reverse=True)
        source = "personalized"
    else:
        # Trending fallback (secondary sort by date when no analytics)
        scored = [
            (e, score_event_trending(e, analytics))
            for e in events
        ]

        def _sort_key(item):
            e, s = item
            d = _parse_event_date(e)
            ts = d.timestamp() if d else float("inf")
            return (s, -ts)

        scored.sort(key=_sort_key, reverse=True)
        source = "trending"

    # Take top N, serialize for response
    recommended = [e for e, _ in scored[:limit]]
    out = [
        _serialize_value({**e, "id": e.get("id")})
        for e in recommended
    ]

    return {"events": out, "source": source}
