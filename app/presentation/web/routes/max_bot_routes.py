from __future__ import annotations

import json
import logging
import secrets
from urllib import error, parse, request as urllib_request

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.config import settings

router = APIRouter(prefix="/max", tags=["max-bot"])
logger = logging.getLogger(__name__)


def _extract_recipient(update: dict) -> tuple[str, int] | None:
    if update.get("chat_id"):
        return "chat_id", update["chat_id"]

    message = update.get("message") or {}
    recipient = message.get("recipient") or {}
    if recipient.get("chat_id"):
        return "chat_id", recipient["chat_id"]

    user = update.get("user") or message.get("sender") or {}
    if user.get("user_id"):
        return "user_id", user["user_id"]

    return None


def _is_user_message(update: dict) -> bool:
    if update.get("update_type") != "message_created":
        return False

    sender = (update.get("message") or {}).get("sender") or {}
    return not sender.get("is_bot")


def _should_send_welcome(update: dict) -> bool:
    return update.get("update_type") == "bot_started" or _is_user_message(update)


def _mini_app_button() -> dict:
    mini_app_url = settings.max_mini_app_url or settings.base_url
    parsed_url = parse.urlparse(mini_app_url)
    is_max_deep_link = parsed_url.netloc in {"max.ru", "www.max.ru"} and parsed_url.path.strip("/")

    if is_max_deep_link:
        return {
            "type": "open_app",
            "text": settings.max_mini_app_button_text,
            "web_app": parsed_url.path.strip("/").split("/", 1)[0],
        }

    if mini_app_url.startswith("http://") or mini_app_url.startswith("https://"):
        return {
            "type": "link",
            "text": settings.max_mini_app_button_text,
            "url": mini_app_url,
        }

    button = {
        "type": "open_app",
        "text": settings.max_mini_app_button_text,
        "web_app": mini_app_url,
    }

    return button


def _send_max_welcome_message(update: dict) -> None:
    if not settings.max_bot_token:
        logger.warning("MAX_BOT_TOKEN is not set; welcome message was not sent")
        return

    recipient = _extract_recipient(update)
    if not recipient:
        logger.warning("Could not extract MAX recipient from update: %s", update)
        return

    recipient_key, recipient_id = recipient
    query = parse.urlencode({recipient_key: recipient_id})
    url = f"{settings.max_bot_api_base.rstrip('/')}/messages?{query}"

    body = {
        "text": settings.max_welcome_text,
        "attachments": [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [[_mini_app_button()]],
                },
            }
        ],
    }

    req = urllib_request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": settings.max_bot_token,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=10) as response:
            response.read()
        logger.info("MAX welcome message sent to %s=%s", recipient_key, recipient_id)
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        logger.error("MAX API returned %s: %s", exc.code, details)
    except error.URLError as exc:
        logger.error("Could not send MAX welcome message: %s", exc)


@router.post("/webhook")
async def max_webhook(request: Request, background_tasks: BackgroundTasks):
    if settings.max_webhook_secret:
        incoming_secret = request.headers.get("X-Max-Bot-Api-Secret", "")
        if not secrets.compare_digest(incoming_secret, settings.max_webhook_secret):
            raise HTTPException(status_code=403, detail="Invalid MAX webhook secret")

    update = await request.json()
    if _should_send_welcome(update):
        background_tasks.add_task(_send_max_welcome_message, update)

    return {"ok": True}
