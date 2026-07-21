from __future__ import annotations

from fastapi import Request

from app.config import settings
from app.infra.security import verify_auth_token


def get_auth_user(request: Request) -> dict | None:
    role = request.cookies.get("mh_role")
    email = request.cookies.get("mh_email")
    if role and email:
        return {"role": role, "email": email.strip().lower()}

    if not settings.auth_url_token_enabled:
        return None

    token = request.query_params.get("auth", "")
    if not token:
        return None

    return verify_auth_token(token)
