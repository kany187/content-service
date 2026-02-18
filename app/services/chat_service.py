"""
AI chat support service for BissoEvent.
Answers questions about events, tickets, payments, refunds.
Uses Firestore for context (user, event, tickets).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.firestore_client import get_db
from app.services.openai_client import client

logger = logging.getLogger(__name__)

LANGUAGES = {"fr": "French", "en": "English"}


def _serialize_val(val: Any) -> Any:
    """Convert Firestore values to JSON-serializable."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    if hasattr(val, "timestamp"):
        return datetime.fromtimestamp(val.timestamp(), tz=timezone.utc).isoformat()
    if isinstance(val, dict):
        return {k: _serialize_val(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_serialize_val(v) for v in val]
    return val


def _get_user_context(user_id: Optional[str]) -> str:
    """Fetch user profile for context."""
    if not user_id:
        return ""
    try:
        doc = get_db().collection("users").document(user_id).get()
        if not doc.exists or not doc.to_dict():
            return ""
        d = doc.to_dict()
        user_type = d.get("userType") or "attendee"
        name = d.get("name") or d.get("email") or "Utilisateur"
        return f"Utilisateur: {name}, type: {user_type}."
    except Exception as e:
        logger.debug("Could not fetch user %s: %s", user_id, e)
        return ""


def _get_event_context(event_id: Optional[str]) -> str:
    """Fetch event details for context."""
    if not event_id:
        return ""
    try:
        doc = get_db().collection("events").document(event_id).get()
        if not doc.exists or not doc.to_dict():
            return ""
        d = doc.to_dict()
        title = d.get("title") or ""
        city = d.get("city") or d.get("location") or ""
        date = d.get("date")
        if hasattr(date, "isoformat"):
            date_str = date.isoformat()
        elif hasattr(date, "timestamp"):
            date_str = datetime.fromtimestamp(date.timestamp(), tz=timezone.utc).isoformat()
        else:
            date_str = str(date) if date else ""
        price = d.get("price") or 0
        currency = d.get("currency") or "CDF"
        refund = (d.get("refundPolicy") or "")[:300]
        cancel = (d.get("cancellationPolicy") or "")[:300]
        status = d.get("status") or "active"
        parts = [
            f"Événement: {title}",
            f"Ville: {city}",
            f"Date: {date_str}",
            f"Prix: {price} {currency}",
            f"Statut: {status}",
        ]
        if refund:
            parts.append(f"Politique de remboursement: {refund}...")
        if cancel:
            parts.append(f"Politique d'annulation: {cancel}...")
        return "\n".join(parts)
    except Exception as e:
        logger.debug("Could not fetch event %s: %s", event_id, e)
        return ""


def _get_tickets_context(user_id: Optional[str], event_id: Optional[str]) -> str:
    """Fetch user's tickets for event (if both provided)."""
    if not user_id or not event_id:
        return ""
    try:
        snapshot = (
            get_db()
            .collection("tickets")
            .where("userId", "==", user_id)
            .where("eventId", "==", event_id)
            .limit(5)
            .get()
        )
        if not snapshot:
            return ""
        count = len(snapshot.docs)
        return f"L'utilisateur a {count} billet(s) pour cet événement."
    except Exception as e:
        logger.debug("Could not fetch tickets: %s", e)
        return ""


def _build_system_prompt(lang: str) -> str:
    lang_name = LANGUAGES.get(lang or "fr", "French")
    return f"""Tu es l'assistant de support de BissoEvent, une application de billetterie et d'événements en Afrique (RD Congo, Congo, etc.).

Réponds TOUJOURS en {lang_name}.

Tu peux aider sur:
- Réservation de billets, paiement (Mobile Money, carte)
- Remboursements et annulations (politiques de l'événement)
- Informations sur les événements (date, lieu, prix)
- Compte organisateur (création d'événements, ventes)
- Problèmes techniques (application, QR codes)

Si tu ne connais pas la réponse ou si c'est hors de ton scope (ex: litige juridique), dis poliment de contacter le support: support@bissoevent.com ou via l'app.

Sois concis, utile et courtois. Maximum 3-4 phrases sauf si l'utilisateur demande plus de détails."""


def chat(
    message: str,
    user_id: Optional[str] = None,
    event_id: Optional[str] = None,
    user_type: Optional[str] = None,
    language: Optional[str] = "fr",
) -> dict:
    """
    Process a chat message and return an AI reply.
    Loads context from Firestore (user, event, tickets) for personalized answers.
    """
    user_ctx = _get_user_context(user_id)
    event_ctx = _get_event_context(event_id)
    tickets_ctx = _get_tickets_context(user_id, event_id)

    # user_type from request can override/supplement user doc
    type_ctx = f"Type utilisateur indiqué: {user_type}." if user_type else ""
    context_parts = [p for p in [type_ctx, user_ctx, event_ctx, tickets_ctx] if p]
    context_block = "\n\n".join(context_parts) if context_parts else "Aucun contexte utilisateur/événement fourni."

    system_content = _build_system_prompt(language)
    system_content += f"\n\n--- Contexte actuel ---\n{context_block}\n--- Fin contexte ---"

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": message},
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        reply = response.choices[0].message.content or "Désolé, je n'ai pas pu générer de réponse. Réessayez ou contactez le support."
        return {"reply": reply.strip(), "conversation_id": None}
    except Exception as e:
        logger.exception("Chat LLM error: %s", e)
        return {
            "reply": "Le service de chat est temporairement indisponible. Veuillez réessayer ou contacter support@bissoevent.com.",
            "conversation_id": None,
        }
