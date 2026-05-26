from datetime import datetime
from fastapi import APIRouter, Request, UploadFile
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
    TaskTeam,
    TaskTeamMember,
    TaskMaterial,
)
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

        recent.append(
            {
                "title": task.title,
                "status": status_map.get(sub.status, sub.status),
                "points": task.points if sub.status == "approved" else 0,
            }
        )

    return templates.TemplateResponse(
        request,
        "student/dashboard.html",
        {
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
            select(Task)
            .where(Task.is_active == True)
            .order_by(Task.sort_order.asc(), Task.id.desc())
        ).all()

        submissions = db.scalars(
            select(TaskSubmission).where(TaskSubmission.user_id == db_user.id)
        ).all()

    submission_map = {s.task_id: s for s in submissions}

    intro_done = any(
        t.is_intro
        and submission_map.get(t.id)
        and submission_map[t.id].status == "approved"
        for t in tasks
    )

    blocks = {}

    for task in tasks:
        task.submission = submission_map.get(task.id)

        task.is_locked = (
            task.is_locked_by_intro
            and not task.is_intro
            and not intro_done
        )

        blocks.setdefault(task.block or "Общее", []).append(task)

    return templates.TemplateResponse(
        request,
        "student/tasks.html",
        {
            "page_title": "Задания",
            "user": user,
            "active_nav": "student_tasks",
            "tasks": tasks,
            "blocks": blocks,
            "submission_map": submission_map,
            "intro_done": intro_done,
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

        intro_done = db.scalar(
            select(TaskSubmission)
            .join(Task, Task.id == TaskSubmission.task_id)
            .where(
                TaskSubmission.user_id == db_user.id,
                Task.is_intro == True,
                TaskSubmission.status == "approved",
            )
        )

        if task.is_locked_by_intro and not task.is_intro and not intro_done:
            return RedirectResponse(url="/tasks", status_code=303)

        materials = db.scalars(
            select(TaskMaterial)
            .where(TaskMaterial.task_id == task.id)
            .order_by(TaskMaterial.id.desc())
        ).all()

        teams = []
        team_members_map = {}
        current_team_id = None
        current_team = None

        if task.assignment_type == "team":
            teams = db.scalars(
                select(TaskTeam)
                .where(TaskTeam.task_id == task.id)
                .order_by(TaskTeam.id.desc())
            ).all()

            for team in teams:
                members = db.scalars(
                    select(TaskTeamMember)
                    .where(TaskTeamMember.team_id == team.id)
                    .order_by(TaskTeamMember.id.asc())
                ).all()

                member_items = []

                for member in members:
                    member_user = db.get(User, member.user_id)

                    member_profile = db.scalar(
                        select(StudentProfile).where(
                            StudentProfile.user_id == member.user_id
                        )
                    )

                    member_items.append(
                        {
                            "member": member,
                            "user": member_user,
                            "profile": member_profile,
                        }
                    )

                    if member.user_id == db_user.id:
                        current_team_id = team.id

                team_members_map[team.id] = member_items
                team.members_count = len(member_items)
                team.is_full = len(member_items) >= task.required_members
                team.joined = current_team_id == team.id

                if current_team_id == team.id:
                    current_team = team

        submission = None

        if task.assignment_type == "individual":
            submission = db.scalar(
                select(TaskSubmission).where(
                    TaskSubmission.task_id == task.id,
                    TaskSubmission.user_id == db_user.id,
                )
            )
        else:
            if current_team_id:
                submission = db.scalar(
                    select(TaskSubmission).where(
                        TaskSubmission.task_id == task.id,
                        TaskSubmission.team_id == current_team_id,
                    )
                )

        files = []
        if submission:
            files = db.scalars(
                select(SubmissionFile)
                .where(SubmissionFile.submission_id == submission.id)
                .order_by(SubmissionFile.id.desc())
            ).all()

    return templates.TemplateResponse(
        request,
        "student/task_detail.html",
        {
            "page_title": task.title,
            "user": user,
            "active_nav": "student_tasks",
            "task": task,
            "submission": submission,
            "files": files,
            "materials": materials,
            "teams": teams,
            "team_members_map": team_members_map,
            "current_team_id": current_team_id,
            "current_team": current_team,
            "intro_done": bool(intro_done),
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
    essay_text = (form.get("essay_text") or "").strip()
    video_url = (form.get("video_url") or "").strip()

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

        intro_done = db.scalar(
            select(TaskSubmission)
            .join(Task, Task.id == TaskSubmission.task_id)
            .where(
                TaskSubmission.user_id == db_user.id,
                Task.is_intro == True,
                TaskSubmission.status == "approved",
            )
        )

        if task.is_locked_by_intro and not task.is_intro and not intro_done:
            return RedirectResponse(url="/tasks", status_code=303)

        if task.requires_essay:
            essay_len = len(essay_text)

            if essay_len < task.min_essay_len:
                return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)

            if task.max_essay_len and essay_len > task.max_essay_len:
                return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)

        if video_url and not task.allows_video_link:
            video_url = ""

        if uploaded_files and not task.allows_extra_files:
            uploaded_files = []

        current_team = None

        if task.assignment_type == "team":
            member = db.scalar(
                select(TaskTeamMember)
                .join(TaskTeam, TaskTeam.id == TaskTeamMember.team_id)
                .where(
                    TaskTeam.task_id == task.id,
                    TaskTeamMember.user_id == db_user.id,
                )
            )

            if not member:
                return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)

            current_team = db.get(TaskTeam, member.team_id)
            if not current_team:
                return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)

            members_count = db.query(TaskTeamMember).filter(
                TaskTeamMember.team_id == current_team.id
            ).count()

            if members_count < task.required_members:
                return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)

        if task.assignment_type == "individual":
            submission = db.scalar(
                select(TaskSubmission).where(
                    TaskSubmission.task_id == task.id,
                    TaskSubmission.user_id == db_user.id,
                )
            )
        else:
            submission = db.scalar(
                select(TaskSubmission).where(
                    TaskSubmission.task_id == task.id,
                    TaskSubmission.team_id == current_team.id,
                )
            )

        if submission:
            if submission.status == "approved":
                return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)

            submission.comment = comment
            submission.essay_text = essay_text
            submission.video_url = video_url
            submission.status = "pending"
        else:
            submission = TaskSubmission(
                user_id=db_user.id,
                task_id=task.id,
                team_id=current_team.id if current_team else None,
                comment=comment,
                essay_text=essay_text,
                video_url=video_url,
                status="pending",
            )
            db.add(submission)
            db.flush()

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

@router.post("/tasks/{task_id}/teams/create")
async def create_task_team(request: Request, task_id: int):

    user_or_redirect = _require_student(request)

    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    db_user = _get_current_db_user(request)

    if not db_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    form = await request.form()

    team_name = (form.get("team_name") or "").strip()

    with SessionLocal() as db:

        task = db.get(Task, task_id)

        if not task:
            return RedirectResponse(url="/tasks", status_code=303)

        if task.assignment_type != "team":
            return RedirectResponse(
                url=f"/tasks/{task_id}",
                status_code=303
            )

        existing_member = db.scalar(
            select(TaskTeamMember)
            .join(TaskTeam, TaskTeam.id == TaskTeamMember.team_id)
            .where(
                TaskTeam.task_id == task_id,
                TaskTeamMember.user_id == db_user.id
            )
        )

        if existing_member:
            return RedirectResponse(
                url=f"/tasks/{task_id}",
                status_code=303
            )

        team = TaskTeam(
            task_id=task.id,
            name=team_name or f"Команда {db_user.id}",
            status="forming",
            created_by_user_id=db_user.id,
        )

        db.add(team)
        db.commit()
        db.refresh(team)

        member = TaskTeamMember(
            team_id=team.id,
            user_id=db_user.id,
        )

        db.add(member)
        db.commit()

    return RedirectResponse(
        url=f"/tasks/{task_id}",
        status_code=303
    )


@router.post("/tasks/{task_id}/teams/{team_id}/join")
def join_task_team(
    request: Request,
    task_id: int,
    team_id: int
):

    user_or_redirect = _require_student(request)

    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    db_user = _get_current_db_user(request)

    if not db_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    with SessionLocal() as db:

        task = db.get(Task, task_id)

        if not task:
            return RedirectResponse(url="/tasks", status_code=303)

        team = db.get(TaskTeam, team_id)

        if not team or team.task_id != task.id:
            return RedirectResponse(
                url=f"/tasks/{task_id}",
                status_code=303
            )

        existing_member = db.scalar(
            select(TaskTeamMember)
            .join(TaskTeam, TaskTeam.id == TaskTeamMember.team_id)
            .where(
                TaskTeam.task_id == task_id,
                TaskTeamMember.user_id == db_user.id
            )
        )

        if existing_member:
            return RedirectResponse(
                url=f"/tasks/{task_id}",
                status_code=303
            )

        members_count = db.query(TaskTeamMember).filter(
            TaskTeamMember.team_id == team.id
        ).count()

        if members_count >= task.required_members:
            return RedirectResponse(
                url=f"/tasks/{task_id}",
                status_code=303
            )

        member = TaskTeamMember(
            team_id=team.id,
            user_id=db_user.id,
        )

        db.add(member)

        members_count += 1

        if members_count >= task.required_members:
            team.status = "ready"

        db.commit()

    return RedirectResponse(
        url=f"/tasks/{task_id}",
        status_code=303
    )


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

        items.append(
            {
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
            }
        )

    items.sort(key=lambda x: x["submission_id"] or 0, reverse=True)

    return templates.TemplateResponse(
        request,
        "student/history.html",
        {
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
        db_user = db.scalar(select(User).where(User.email == user["email"]))
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
        request,
        "student/profile.html",
        {
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
        request,
        "student/profile.html",
        {
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

@router.get("/rating", response_class=HTMLResponse)
def student_rating(request: Request):
    user_or_redirect = _require_student(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    user = user_or_redirect

    db_user = _get_current_db_user(request)
    if not db_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    with SessionLocal() as db:
        rows = db.execute(
            select(StudentProfile, User)
            .join(User, User.id == StudentProfile.user_id)
            .order_by(StudentProfile.points_balance.desc(), StudentProfile.id.asc())
        ).all()

        rating = []
        current_position = None

        for index, (profile, rating_user) in enumerate(rows, start=1):
            item = {
                "position": index,
                "user_id": rating_user.id,
                "email": rating_user.email,
                "full_name": profile.full_name or rating_user.email,
                "school_name": profile.school_name,
                "class_name": profile.class_name,
                "points": profile.points_balance,
                "is_current": rating_user.id == db_user.id,
            }

            if item["is_current"]:
                current_position = index

            rating.append(item)

    return templates.TemplateResponse(
        request,
        "student/rating.html",
        {
            "page_title": "Рейтинг",
            "user": user,
            "active_nav": "student_rating",
            "rating": rating,
            "current_position": current_position,
        },
    )