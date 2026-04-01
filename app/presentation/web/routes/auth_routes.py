# app/presentation/web/routes/auth_routes.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.presentation.web.templates_env import templates

from app.infra.db import SessionLocal
from app.infra.models import User
from app.infra.security import verify_password
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "page_title": "Вход",
            "user": None,
            "active_nav": "login",
        },
    )


@router.post("/login")
async def login_post(request: Request):
    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""

    if not email or not password:
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "page_title": "Вход",
                "user": None,
                "active_nav": "login",
                "error": "Введите email и пароль",
            },
            status_code=400,
        )

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "page_title": "Вход",
                "user": None,
                "active_nav": "login",
                "error": "Неверный email или пароль",
            },
            status_code=401,
        )

    if user.role == "admin":
        target = "/admin"
    elif user.role == "mentor":
        target = "/mentor"
    else:
        target = "/"

    resp = RedirectResponse(url=target, status_code=303)
    resp.set_cookie("mh_role", user.role, httponly=True, samesite="lax")
    resp.set_cookie("mh_email", user.email, httponly=True, samesite="lax")
    return resp


@router.post("/logout")
def logout():
    resp = RedirectResponse(url="/auth/login", status_code=303)
    resp.delete_cookie("mh_role")
    resp.delete_cookie("mh_email")
    return resp
