from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.presentation.web.templates_env import templates

from app.infra.db import SessionLocal
from app.infra.models import User, StudentProfile, School, ClassGroup
from app.infra.security import verify_password, hash_password
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
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
            request,
            "auth/login.html",
            {
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
            request,
            "auth/login.html",
            {
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

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    with SessionLocal() as db:
        class_groups = db.execute(
            select(ClassGroup, School)
            .join(School, School.id == ClassGroup.school_id)
            .order_by(School.name, ClassGroup.name)
        ).all()

    return templates.TemplateResponse(
        request,
        "auth/register.html",
        {
            "page_title": "Регистрация",
            "user": None,
            "active_nav": "register",
            "class_groups": class_groups,
            "form": {},
        },
    )


@router.post("/register", response_class=HTMLResponse)
async def register_post(request: Request):
    form = await request.form()

    email = (form.get("email") or "").strip().lower()
    password = (form.get("password") or "").strip()
    password_repeat = (form.get("password_repeat") or "").strip()
    full_name = (form.get("full_name") or "").strip()
    class_group_id_raw = (form.get("class_group_id") or "").strip()

    def render(error: str | None = None):
        with SessionLocal() as db:
            class_groups = db.execute(
                select(ClassGroup, School)
                .join(School, School.id == ClassGroup.school_id)
                .order_by(School.name, ClassGroup.name)
            ).all()

        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {
                "page_title": "Регистрация",
                "user": None,
                "active_nav": "register",
                "error": error,
                "class_groups": class_groups,
                "form": {
                    "email": email,
                    "full_name": full_name,
                    "class_group_id": class_group_id_raw,
                },
            },
            status_code=400,
        )

    if not full_name:
        return render("Укажи ФИО.")

    if not email or "@" not in email:
        return render("Укажи корректный email.")

    if len(password) < 6:
        return render("Пароль должен быть минимум 6 символов.")

    if password != password_repeat:
        return render("Пароли не совпадают.")

    try:
        class_group_id = int(class_group_id_raw)
    except ValueError:
        return render("Выбери школу и класс.")

    with SessionLocal() as db:
        class_group_row = db.execute(
            select(ClassGroup, School)
            .join(School, School.id == ClassGroup.school_id)
            .where(ClassGroup.id == class_group_id)
        ).first()

        if not class_group_row:
            return render("Выбранный класс не найден.")

        class_group, school = class_group_row

        exists = db.scalar(select(User).where(User.email == email))
        if exists:
            return render("Пользователь с таким email уже существует.")

        new_user = User(
            email=email,
            password_hash=hash_password(password),
            role="student",
        )
        db.add(new_user)
        db.flush()

        profile = StudentProfile(
            user_id=new_user.id,
            full_name=full_name,
            class_group_id=class_group.id,
            class_name=class_group.name,
            school_name=school.name,
            points_balance=0,
        )
        db.add(profile)
        db.commit()

    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie("mh_role", "student", httponly=True, samesite="lax")
    resp.set_cookie("mh_email", email, httponly=True, samesite="lax")
    return resp


@router.post("/logout")
def logout():
    resp = RedirectResponse(url="/auth/login", status_code=303)
    resp.delete_cookie("mh_role")
    resp.delete_cookie("mh_email")
    return resp