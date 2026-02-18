import json

from app.services.openai_client import client

# Supported languages for prompts
LANGUAGES = {"fr": "French", "en": "English", "sw": "Swahili"}


def generate_description(data) -> dict:
    """Generate a captivating event description."""
    language = LANGUAGES.get(getattr(data, "language", None) or "fr", "French")
    venue = getattr(data, "venue", None)
    event_type = getattr(data, "event_type", None)
    max_len = getattr(data, "max_length", None) or 500
    venue_part = f"\nVenue: {venue}" if venue else ""
    event_type_part = f"\nEvent type: {event_type}" if event_type else ""

    prompt = f"""Write a captivating event description in {language}.

Event title: {data.title}
City: {data.city}
Category: {data.category}{venue_part}{event_type_part}

Requirements:
- Make it engaging and suitable for social media
- Keep it between 10 and {max_len} characters
- Highlight what makes this event special
- Use a tone that excites attendees"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a marketing expert for events in Africa. Write concise, engaging descriptions."},
            {"role": "user", "content": prompt},
        ],
    )

    description = response.choices[0].message.content
    if description and len(description) > max_len:
        description = description[: max_len - 3] + "..."

    return {"description": description}


def generate_tags(data) -> dict:
    """Generate relevant tags for an event."""
    city_part = f" in {data.city}" if data.city else ""

    prompt = f"""Suggest 5-8 relevant tags for this event. Return ONLY a JSON array of strings, nothing else.

Event: {data.title}
Category: {data.category}{city_part}

Tags should be: lowercase, comma-separated in the array, relevant for search/discovery, mix of generic (concert, live music) and specific (city name, genre)."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You return only valid JSON arrays of tag strings. No extra text."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content
    try:
        # Extract array if model wrapped it in markdown
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        tags = json.loads(text)
        if isinstance(tags, list):
            tags = [str(t).strip().lower() for t in tags if t][:8]
        else:
            tags = []
    except (json.JSONDecodeError, TypeError):
        # Fallback: split by comma
        tags = [t.strip().lower() for t in content.split(",") if t.strip()][:8]

    return {"tags": tags}


def generate_policies(data) -> dict:
    """Generate refund and cancellation policy templates."""
    language = LANGUAGES.get(getattr(data, "language", None) or "fr", "French")
    currency = getattr(data, "currency", None) or "CDF"
    event_type = getattr(data, "event_type", None) or "paid"

    prompt = f"""Generate two short policy templates in {language} for an event (currency: {currency}, type: {event_type}).

1. Refund policy: When attendees can get refunds, conditions, time limits. 80-150 words.
2. Cancellation policy: What happens if the event is cancelled/postponed by organizer. 80-150 words.

Return strictly in this JSON format:
{{"refundPolicy": "...", "cancellationPolicy": "..."}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You return only valid JSON with refundPolicy and cancellationPolicy keys."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content
    try:
        text = content.strip()
        if "```" in text:
            start = text.find("[") if "[" in text else text.find("{")
            end = text.rfind("]") + 1 if "]" in text else text.rfind("}") + 1
            text = text[start:end]
        obj = json.loads(text)
        refund = obj.get("refundPolicy", "").strip()
        cancellation = obj.get("cancellationPolicy", "").strip()
    except (json.JSONDecodeError, TypeError, AttributeError):
        refund = "Contact the organizer for refund conditions."
        cancellation = "In case of cancellation, attendees will be notified and refunded according to our refund policy."

    return {"refundPolicy": refund, "cancellationPolicy": cancellation}


def generate_form_assist(data) -> dict:
    """Generate all form fields in one call: description, tags, venue, policies."""
    language = LANGUAGES.get(data.language or "fr", "French")
    city_part = f" in {data.city}" if data.city else ""
    venue_part = f" at {data.venue}" if data.venue else ""

    prompt = f"""You are helping an event organizer fill out their form. Generate all fields in {language}.

Event: {data.title}
Category: {data.category}{city_part}{venue_part}

Return a JSON object with exactly these keys:
- description: 80-400 character captivating description for the event. Include 2-4 relevant emojis (e.g. 🎵 for concert, ⚽ for sports) to make it engaging.
- tags: array of 5-8 lowercase tags (e.g. ["concert", "live music", "kinshasa"])
- suggestedVenue: a plausible venue name if not provided, or null if venue was given
- refundPolicy: 80-150 word refund policy template
- cancellationPolicy: 80-150 word cancellation policy template

Return ONLY valid JSON, no extra text."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You return only valid JSON. No markdown, no explanation."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content
    try:
        text = content.strip()
        if "```" in text:
            start = max(text.find("{"), 0)
            end = text.rfind("}") + 1
            text = text[start:end]
        obj = json.loads(text)
        description = str(obj.get("description", ""))[:500]
        tags = obj.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        tags = [str(t).strip().lower() for t in tags if t][:8]
        suggested_venue = obj.get("suggestedVenue")
        if suggested_venue is not None:
            suggested_venue = str(suggested_venue).strip() or None
        refund = str(obj.get("refundPolicy", ""))[:500]
        cancellation = str(obj.get("cancellationPolicy", ""))[:500]
    except (json.JSONDecodeError, TypeError, AttributeError):
        # Fallback partial generation
        description = f"{data.title} - {data.category}{city_part}. Don't miss it!"
        tags = [data.category, "event"]
        if data.city:
            tags.append(data.city.lower())
        suggested_venue = None
        refund = "Contact the organizer for refund conditions."
        cancellation = "In case of cancellation, attendees will be notified."

    return {
        "description": description,
        "tags": tags,
        "suggestedVenue": suggested_venue,
        "refundPolicy": refund,
        "cancellationPolicy": cancellation,
    }
