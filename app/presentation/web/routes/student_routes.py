from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.presentation.web.templates_env import templates
from app.presentation.web.fake_repo import TASKS, SUBMISSIONS
from sqlalchemy import select
from app.infra.db import SessionLocal
from app.infra.models import (
    User,
    Task,
    TaskSubmission,
    StudentProfile,
    SubmissionFile,
    School,
    ClassGroup,
    PointsLedger,
)
from fastapi import UploadFile
import os
import uuid
from pathlib import Path

router = APIRouter(tags=["student"])


def _get_user(request: Request) -> dict | None:
    role = request.cookies.get("mh_role")
    email = request.cookies.get("mh_email")
    if not role or not email:
        return None
    return {"role": role, "email": email}


def _require_student(request: Request):
    user = _get_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    if user["role"] != "student":
        return RedirectResponse(url="/admin", status_code=303)
    return user

def _get_current_db_user(request: Request):
    email = request.cookies.get("mh_email")
    if not email:
        return None

    with SessionLocal() as db:
        return db.scalar(select(User).where(User.email == email))

def _get_or_create_student_profile(user_id: int):
    with SessionLocal() as db:
        profile = db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == user_id)
        )
        if profile:
            return profile

        profile = StudentProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

@router.get("/", response_class=HTMLResponse)
def student_dashboard(request: Request):
    user_or_redirect = _require_student(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    db_user = _get_current_db_user(request)
    if not db_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    with SessionLocal() as db:

        profile = db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == db_user.id)
        )

        submissions = db.execute(
            select(TaskSubmission, Task)
            .join(Task, Task.id == TaskSubmission.task_id)
            .where(TaskSubmission.user_id == db_user.id)
            .order_by(TaskSubmission.created_at.desc())
        ).all()

    balance = profile.points_balance if profile else 0

    stats = {
        "total": len(submissions),
        "approved": sum(1 for s, t in submissions if s.status == "approved"),
        "pending": sum(1 for s, t in submissions if s.status == "pending"),
        "rejected": sum(1 for s, t in submissions if s.status == "rejected"),
    }

    recent = []

    for sub, task in submissions[:5]:
        status_map = {
            "approved": "Зачтено",
            "pending": "Проверяется",
            "rejected": "Отклонено",
        }

        recent.append({
            "title": task.title,
            "status": status_map.get(sub.status, sub.status),
            "points": task.points if sub.status == "approved" else 0,
        })

    return templates.TemplateResponse(
        "student/dashboard.html",
        {
            "request": request,
            "page_title": "Дашборд",
            "user": user,
            "active_nav": "dashboard",
            "balance": balance,
            "recent": recent,
            "stats": stats,
        },
    )


@router.get("/tasks", response_class=HTMLResponse)
def student_tasks(request: Request):
    user_or_redirect = _require_student(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    db_user = _get_current_db_user(request)
    if not db_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    with SessionLocal() as db:
        tasks = db.scalars(
            select(Task).where(Task.is_active == True).order_by(Task.id.desc())
        ).all()

        submissions = db.scalars(
            select(TaskSubmission).where(TaskSubmission.user_id == db_user.id)
        ).all()

    submission_map = {s.task_id: s for s in submissions}

    for t in tasks:
        t.submission = submission_map.get(t.id)
        t.badge = None

    return templates.TemplateResponse(
        "student/tasks.html",
        {
            "request": request,
            "page_title": "Задания",
            "user": user,
            "active_nav": "student_tasks",
            "tasks": tasks,
            "submission_map": submission_map,
        },
    )

@router.get("/tasks/{task_id}", response_class=HTMLResponse)
def student_task_detail(request: Request, task_id: int):
    user_or_redirect = _require_student(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    db_user = _get_current_db_user(request)
    if not db_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if not task or not task.is_active:
            return RedirectResponse(url="/tasks", status_code=303)

        submission = db.scalar(
            select(TaskSubmission).where(
                TaskSubmission.task_id == task_id,
                TaskSubmission.user_id == db_user.id,
            )
        )

        files = []
        if submission:
            files = db.scalars(
                select(SubmissionFile).where(
                    SubmissionFile.submission_id == submission.id
                ).order_by(SubmissionFile.id.desc())
            ).all()

    return templates.TemplateResponse(
        "student/task_detail.html",
        {
            "request": request,
            "page_title": task.title,
            "user": user,
            "active_nav": "student_tasks",
            "task": task,
            "submission": submission,
            "files": files,
        },
    )

@router.post("/tasks/{task_id}/submit")
async def submit_task(request: Request, task_id: int):
    user_or_redirect = _require_student(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    db_user = _get_current_db_user(request)
    if not db_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    form = await request.form()
    comment = (form.get("comment") or "").strip()

    uploaded_files = []
    for value in form.getlist("files"):
        if hasattr(value, "filename") and value.filename:
            uploaded_files.append(value)

    upload_dir = Path("uploads/submissions")
    upload_dir.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if not task or not task.is_active:
            return RedirectResponse(url="/tasks", status_code=303)

        submission = db.scalar(
            select(TaskSubmission).where(
                TaskSubmission.task_id == task_id,
                TaskSubmission.user_id == db_user.id,
            )
        )

        if submission:
            submission.comment = comment
            submission.status = "pending"
        else:
            submission = TaskSubmission(
                user_id=db_user.id,
                task_id=task_id,
                comment=comment,
                status="pending",
            )
            db.add(submission)
            db.flush()

        # сохраняем новые файлы
        for file in uploaded_files:
            ext = Path(file.filename).suffix
            stored_name = f"{uuid.uuid4().hex}{ext}"
            file_path = upload_dir / stored_name

            content = await file.read()
            file_size = len(content)

            with open(file_path, "wb") as f:
                f.write(content)

            db.add(
                SubmissionFile(
                    submission_id=submission.id,
                    original_name=file.filename,
                    stored_name=stored_name,
                    file_path=f"/uploads/submissions/{stored_name}",
                    content_type=file.content_type or "",
                    file_size=file_size,
                )
            )

        db.commit()

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)

STATUS_LABEL = {
    "pending": "Проверяется",
    "approved": "Одобрено",
    "rejected": "Отклонено",
}

@router.get("/history", response_class=HTMLResponse)
def student_history(request: Request):
    user_or_redirect = _require_student(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    from app.presentation.web.fake_repo import TASKS, SUBMISSIONS

    # собираем элементы истории для текущего юзера
    items = []
    for s in SUBMISSIONS:
        if s.get("user") != user["email"]:
            continue
        t = TASKS.get(s["task_id"])
        if not t:
            continue

        status = s.get("status", "pending")
        points = t["points"] if status == "approved" else 0

        raw = s.get("created_at")
        created = None
        if raw:
            try:
                created = datetime.fromisoformat(raw).strftime("%d.%m.%Y %H:%M")
            except ValueError:
                created = raw

        items.append({
            "submission_id": s.get("id"),
            "task_id": t["id"],
            "title": t["title"],
            "category": t.get("category"),
            "status": status,
            "status_label": STATUS_LABEL.get(status, status),
            "points": points,
            "comment": s.get("comment") or "",
            "reason": s.get("reason") or "",
            "created_at": created,
        })

    # новые сверху
    items.sort(key=lambda x: x["submission_id"] or 0, reverse=True)

    return templates.TemplateResponse(
        "student/history.html",
        {
            "request": request,
            "page_title": "История",
            "user": user,
            "active_nav": "history",
            "items": items,
        },
    )

@router.get("/profile", response_class=HTMLResponse)
def student_profile(request: Request):
    user_or_redirect = _require_student(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    user = user_or_redirect

    with SessionLocal() as db:
        db_user = db.scalar(
            select(User).where(User.email == user["email"])
        )
        if not db_user:
            return RedirectResponse(url="/auth/login", status_code=303)

        profile = db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == db_user.id)
        )

        if not profile:
            profile = StudentProfile(user_id=db_user.id)
            db.add(profile)
            db.commit()
            db.refresh(profile)

        submissions = db.scalars(
            select(TaskSubmission).where(TaskSubmission.user_id == db_user.id)
        ).all()

        ledger_entries = db.scalars(
            select(PointsLedger)
            .where(PointsLedger.user_id == db_user.id)
            .order_by(PointsLedger.created_at.desc(), PointsLedger.id.desc())
        ).all()

        class_group = None
        school = None

        if profile.class_group_id:
            class_group = db.get(ClassGroup, profile.class_group_id)
            if class_group:
                school = db.get(School, class_group.school_id)

    stats = {
        "total_submissions": len(submissions),
        "approved_count": sum(1 for s in submissions if s.status == "approved"),
        "pending_count": sum(1 for s in submissions if s.status == "pending"),
        "rejected_count": sum(1 for s in submissions if s.status == "rejected"),
    }

    return templates.TemplateResponse(
        "student/profile.html",
        {
            "request": request,
            "page_title": "Профиль",
            "user": user,
            "profile": profile,
            "stats": stats,
            "class_group": class_group,
            "school": school,
            "ledger_entries": ledger_entries,
            "active_nav": "profile",
        },
    )

@router.post("/profile", response_class=HTMLResponse)
async def student_profile_save(request: Request):
    user_or_redirect = _require_student(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    db_user = _get_current_db_user(request)
    if not db_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    form = await request.form()

    full_name = (form.get("full_name") or "").strip()
    class_name = (form.get("class_name") or "").strip()
    school_name = (form.get("school_name") or "").strip()
    birth_date = (form.get("birth_date") or "").strip()
    parent_name = (form.get("parent_name") or "").strip()
    parent_phone = (form.get("parent_phone") or "").strip()
    about = (form.get("about") or "").strip()
    avatar_url = (form.get("avatar_url") or "").strip()

    with SessionLocal() as db:
        profile = db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == db_user.id)
        )
        if not profile:
            profile = StudentProfile(user_id=db_user.id)
            db.add(profile)
            db.flush()

        profile.full_name = full_name
        profile.class_name = class_name
        profile.school_name = school_name
        profile.birth_date = birth_date
        profile.parent_name = parent_name
        profile.parent_phone = parent_phone
        profile.about = about
        profile.avatar_url = avatar_url

        db.commit()
        db.refresh(profile)

        submissions = db.scalars(
            select(TaskSubmission).where(TaskSubmission.user_id == db_user.id)
        ).all()

        ledger_entries = db.scalars(
            select(PointsLedger)
            .where(PointsLedger.user_id == db_user.id)
            .order_by(PointsLedger.created_at.desc(), PointsLedger.id.desc())
        ).all()

        class_group = None
        school = None

        if profile.class_group_id:
            class_group = db.get(ClassGroup, profile.class_group_id)
            if class_group:
                school = db.get(School, class_group.school_id)

    stats = {
        "total_submissions": len(submissions),
        "approved_count": sum(1 for s in submissions if s.status == "approved"),
        "pending_count": sum(1 for s in submissions if s.status == "pending"),
        "rejected_count": sum(1 for s in submissions if s.status == "rejected"),
    }

    return templates.TemplateResponse(
        "student/profile.html",
        {
            "request": request,
            "page_title": "Мой профиль",
            "user": user,
            "active_nav": "student_profile",
            "profile": profile,
            "stats": stats,
            "ledger_entries": ledger_entries,
            "class_group": class_group,
            "school": school,
            "success": "Профиль сохранён.",
            "error": None,
        },
    )


