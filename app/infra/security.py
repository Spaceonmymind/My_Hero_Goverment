from __future__ import annotations

import bcrypt
import base64
import hashlib
import hmac
import json
import time

from app.config import settings

def hash_password(password: str) -> str:
    pw = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw, salt).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_auth_token(email: str, role: str) -> str:
    payload = {
        "email": email,
        "role": role,
        "iat": int(time.time()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_part = _b64encode(payload_bytes)
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_part}.{_b64encode(signature)}"


def verify_auth_token(token: str, max_age_seconds: int = 60 * 60 * 24 * 30) -> dict | None:
    try:
        payload_part, signature_part = token.split(".", 1)
        expected_signature = hmac.new(
            settings.secret_key.encode("utf-8"),
            payload_part.encode("ascii"),
            hashlib.sha256,
        ).digest()
        actual_signature = _b64decode(signature_part)
        if not hmac.compare_digest(actual_signature, expected_signature):
            return None

        payload = json.loads(_b64decode(payload_part).decode("utf-8"))
        if int(time.time()) - int(payload.get("iat", 0)) > max_age_seconds:
            return None

        email = str(payload.get("email") or "").strip().lower()
        role = str(payload.get("role") or "").strip()
        if not email or role not in ("student", "admin", "mentor"):
            return None

        return {"email": email, "role": role}
    except Exception:
        return None
