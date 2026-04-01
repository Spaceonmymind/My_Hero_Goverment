from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.presentation.web.templates_env import templates
from sqlalchemy import select
from app.infra.db import SessionLocal
from app.infra.models import User, Task, StudentProfile, TaskSubmission, SubmissionFile, School, ClassGroup, MentorProfile, MentorClassLink, PointsLedger
from app.infra.security import hash_password


router = APIRouter(prefix="/admin", tags=["admin"])


def _get_user(request: Request) -> dict | None:
    role = request.cookies.get("mh_role")
    email = request.cookies.get("mh_email")
    if not role or not email:
        return None
    return {"role": role, "email": email}


def _require_admin(request: Request):
    user = _get_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    if user["role"] != "admin":
        return RedirectResponse(url="/", status_code=303)
    return user


@router.get("", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    user = user_or_redirect
    db = SessionLocal()

    users_count = db.query(User).count()
    tasks_count = db.query(Task).count()
    submissions_count = db.query(TaskSubmission).count()

    pending_count = db.query(TaskSubmission).filter(
        TaskSubmission.status == "pending"
    ).count()

    stats = {
        "users": users_count,
        "tasks": tasks_count,
        "submissions": submissions_count,
        "pending": pending_count,
    }

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "page_title": "Админ-панель",
            "user": user,
            "active_nav": "admin_dashboard",
            "stats": stats,
        },
    )


@router.get("/tasks", response_class=HTMLResponse)
def admin_tasks(request: Request):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    with SessionLocal() as db:
        tasks = db.scalars(select(Task).order_by(Task.id.desc())).all()

    return templates.TemplateResponse(
        request,
        "admin/tasks.html",
        {
            "page_title": "Задания",
            "user": user,
            "active_nav": "admin_tasks",
            "tasks": tasks,
            "error": None,
            "success": None,
            "form": {
                "title": "",
                "description": "",
                "category": "Общее",
                "points": 0,
                "is_active": True,
            },
        },
    )

@router.post("/tasks", response_class=HTMLResponse)
async def admin_tasks_create(request: Request):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    form = await request.form()
    title = (form.get("title") or "").strip()
    description = (form.get("description") or "").strip()
    category = (form.get("category") or "Общее").strip()
    points_raw = form.get("points") or "0"
    is_active = form.get("is_active") == "on"

    try:
        points = int(points_raw)
    except ValueError:
        points = -1

    def render(error=None, success=None):
        with SessionLocal() as db:
            tasks = db.scalars(select(Task).order_by(Task.id.desc())).all()

        return templates.TemplateResponse(
            request,
            "admin/tasks.html",
            {
                "page_title": "Задания",
                "user": user,
                "active_nav": "admin_tasks",
                "tasks": tasks,
                "error": error,
                "success": success,
                "form": {
                    "title": title,
                    "description": description,
                    "category": category,
                    "points": points_raw,
                    "is_active": is_active,
                },
            },
            status_code=400 if error else 200,
        )

    if not title:
        return render(error="Укажи название задания.")
    if points < 0:
        return render(error="Баллы должны быть числом 0 или больше.")

    with SessionLocal() as db:
        task = Task(
            title=title,
            description=description,
            category=category or "Общее",
            points=points,
            is_active=is_active,
        )
        db.add(task)
        db.commit()

    return render(success="Задание создано.")

@router.post("/tasks/{task_id}/toggle")
def admin_task_toggle(request: Request, task_id: int):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task:
            task.is_active = not task.is_active
            db.commit()

    return RedirectResponse(url="/admin/tasks", status_code=303)

@router.post("/tasks/{task_id}/delete")
def admin_task_delete(request: Request, task_id: int):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task:
            db.delete(task)
            db.commit()

    return RedirectResponse(url="/admin/tasks", status_code=303)


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
def admin_task_detail(request: Request, task_id: int):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    # MVP-заглушка: ищем в локальном списке
    tasks = [
        {"id": 1, "title": "Участие в акции", "category": "События", "points": 20, "active": True},
        {"id": 2, "title": "Посещение кружка", "category": "Образование", "points": 15, "active": True},
        {"id": 3, "title": "Волонтёрство", "category": "Соц. активность", "points": 50, "active": False},
    ]
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return RedirectResponse(url="/admin/tasks", status_code=303)

    return templates.TemplateResponse(
        request,
        "admin/task_detail.html",
        {
            "page_title": f"Задание #{task_id}",
            "user": user,
            "active_nav": "admin_tasks",
            "task": task,
        },
    )

@router.get("/reviews", response_class=HTMLResponse)
def admin_reviews(request: Request):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    with SessionLocal() as db:
        submissions = db.execute(
            select(TaskSubmission, Task, User)
            .join(Task, Task.id == TaskSubmission.task_id)
            .join(User, User.id == TaskSubmission.user_id)
            .order_by(TaskSubmission.created_at.desc())
        ).all()

    reviews = []

    for sub, task, student in submissions:
        reviews.append({
            "id": sub.id,
            "student": student.email,
            "student_email": student.email,
            "task_id": task.id,
            "task_title": task.title,
            "points": task.points,
            "submitted_at": sub.created_at.strftime("%Y-%m-%d %H:%M"),
            "status": sub.status,
        })

    return templates.TemplateResponse(
        request,
        "admin/reviews.html",
        {
            "page_title": "Очередь проверок",
            "user": user,
            "active_nav": "admin_reviews",
            "reviews": reviews,
        },
    )


@router.get("/reviews/{review_id}", response_class=HTMLResponse)
def admin_review_detail(request: Request, review_id: int):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    with SessionLocal() as db:
        row = db.execute(
            select(TaskSubmission, Task, User)
            .join(Task, Task.id == TaskSubmission.task_id)
            .join(User, User.id == TaskSubmission.user_id)
            .where(TaskSubmission.id == review_id)
        ).first()

        if not row:
            return RedirectResponse(url="/admin/reviews", status_code=303)

        sub, task, student = row

        files = db.scalars(
            select(SubmissionFile)
            .where(SubmissionFile.submission_id == sub.id)
            .order_by(SubmissionFile.id.desc())
        ).all()

    review = {
        "id": sub.id,
        "student": student.email,
        "student_email": student.email,
        "task_id": task.id,
        "task_title": task.title,
        "points": task.points,
        "submitted_at": sub.created_at.strftime("%Y-%m-%d %H:%M") if sub.created_at else "",
        "status": sub.status,
        "comment": sub.comment,
        "files": files,
    }

    return templates.TemplateResponse(
        request,
        "admin/review_detail.html",
        {
            "page_title": f"Проверка #{review_id}",
            "user": user,
            "active_nav": "admin_reviews",
            "review": review,
        },
    )

@router.post("/reviews/{review_id}/approve")
def admin_review_approve(request: Request, review_id: int):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    with SessionLocal() as db:
        row = db.execute(
            select(TaskSubmission, Task)
            .join(Task, Task.id == TaskSubmission.task_id)
            .where(TaskSubmission.id == review_id)
        ).first()

        if not row:
            return RedirectResponse(url="/admin/reviews", status_code=303)

        sub, task = row

        already_approved = sub.status == "approved"
        sub.status = "approved"

        profile = db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == sub.user_id)
        )
        if not profile:
            profile = StudentProfile(user_id=sub.user_id)
            db.add(profile)
            db.flush()

        if not already_approved:
            profile.points_balance += task.points

            db.add(
                PointsLedger(
                    user_id=sub.user_id,
                    submission_id=sub.id,
                    points=task.points,
                    reason=f"Зачтено задание: {task.title}",
                    source_role="admin",
                )
            )

        db.commit()

    return RedirectResponse(url=f"/admin/reviews/{review_id}", status_code=303)

@router.post("/reviews/{review_id}/reject")
def admin_review_reject(request: Request, review_id: int):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    with SessionLocal() as db:
        sub = db.get(TaskSubmission, review_id)
        if sub:
            sub.status = "rejected"
            db.commit()

    return RedirectResponse(url=f"/admin/reviews/{review_id}", status_code=303)

@router.get("/users/new", response_class=HTMLResponse)
def admin_user_new(request: Request):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.id.desc())).all()

        class_groups = db.execute(
            select(ClassGroup, School)
            .join(School, School.id == ClassGroup.school_id)
            .order_by(School.name, ClassGroup.name)
        ).all()

        profiles = db.scalars(select(StudentProfile)).all()
        profile_map = {p.user_id: p for p in profiles}

        mentor_profiles = db.scalars(select(MentorProfile)).all()
        mentor_profile_map = {m.user_id: m for m in mentor_profiles}

        mentor_links = db.scalars(select(MentorClassLink)).all()
        mentor_class_map = {}
        for link in mentor_links:
            mentor_class_map.setdefault(link.mentor_profile_id, []).append(link.class_group_id)

    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {
            "page_title": "Пользователи",
            "user": user,
            "active_nav": "admin_users_new",
            "error": None,
            "success": None,
            "form": {"email": "", "role": "student"},
            "users": users,
            "class_groups": class_groups,
            "profile_map": profile_map,
            "mentor_profile_map": mentor_profile_map,
            "mentor_class_map": mentor_class_map,
        },
    )

@router.post("/users/{user_id}/class")
async def admin_user_set_class(request: Request, user_id: int):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    form = await request.form()
    class_group_id = (form.get("class_group_id") or "").strip()

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return RedirectResponse(url="/admin/users/new", status_code=303)

        profile = db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == user_id)
        )

        if not profile:
            profile = StudentProfile(user_id=user_id)
            db.add(profile)
            db.flush()

        if user.role == "student":
            if class_group_id:
                profile.class_group_id = int(class_group_id)
            else:
                profile.class_group_id = None

            db.commit()

    return RedirectResponse(url="/admin/users/new", status_code=303)

@router.post("/users/new", response_class=HTMLResponse)
async def admin_user_create(request: Request):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    password = (form.get("password") or "").strip()
    role = (form.get("role") or "student").strip()

    def render(error: str | None = None, success: str | None = None):
        with SessionLocal() as db:
            users = db.scalars(select(User).order_by(User.id.desc())).all()

            class_groups = db.execute(
                select(ClassGroup, School)
                .join(School, School.id == ClassGroup.school_id)
                .order_by(School.name, ClassGroup.name)
            ).all()

            profiles = db.scalars(select(StudentProfile)).all()
            profile_map = {p.user_id: p for p in profiles}

            mentor_profiles = db.scalars(select(MentorProfile)).all()
            mentor_profile_map = {m.user_id: m for m in mentor_profiles}

            mentor_links = db.scalars(select(MentorClassLink)).all()
            mentor_class_map = {}
            for link in mentor_links:
                mentor_class_map.setdefault(link.mentor_profile_id, []).append(link.class_group_id)

        return templates.TemplateResponse(
            request,
            "admin/users.html",
            {
                "page_title": "Пользователи",
                "user": user,
                "active_nav": "admin_users_new",
                "error": error,
                "success": success,
                "form": {"email": email, "role": role},
                "users": users,
                "class_groups": class_groups,
                "profile_map": profile_map,
                "mentor_profile_map": mentor_profile_map,
                "mentor_class_map": mentor_class_map,
            },
            status_code=400 if error else 200,
        )

    if not email or "@" not in email:
        return render(error="Укажи корректный email.")

    if role not in ("student", "admin", "mentor"):
        return render(error="Роль должна быть student, mentor или admin.")

    if len(password) < 6:
        return render(error="Пароль должен быть минимум 6 символов.")

    with SessionLocal() as db:
        exists = db.scalar(select(User).where(User.email == email))
        if exists:
            return render(error="Пользователь с таким email уже существует.")

        new_user = User(
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        db.add(new_user)
        db.commit()

    return render(success="Пользователь создан.")


@router.post("/users/{user_id}/role")
async def admin_user_set_role(request: Request, user_id: int):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    form = await request.form()
    role = (form.get("role") or "").strip()
    if role not in ("student", "admin", "mentor"):
        return RedirectResponse(url="/admin/users/new", status_code=303)

    with SessionLocal() as db:
        u = db.get(User, user_id)
        if u:
            u.role = role
            db.commit()

    return RedirectResponse(url="/admin/users/new", status_code=303)


@router.post("/users/{user_id}/password")
async def admin_user_set_password(request: Request, user_id: int):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    form = await request.form()
    password = form.get("password") or ""
    if len(password) < 6:
        return RedirectResponse(url="/admin/users/new", status_code=303)

    with SessionLocal() as db:
        u = db.get(User, user_id)
        if u:
            u.password_hash = hash_password(password)
            db.commit()

    return RedirectResponse(url="/admin/users/new", status_code=303)


@router.post("/users/{user_id}/delete")
def admin_user_delete(request: Request, user_id: int):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    current_email = user_or_redirect.get("email")

    with SessionLocal() as db:
        u = db.get(User, user_id)
        if u:
            # не даём удалить самого себя
            if u.email == current_email:
                return RedirectResponse(url="/admin/users/new", status_code=303)
            db.delete(u)
            db.commit()

    return RedirectResponse(url="/admin/users/new", status_code=303)

@router.get("/schools", response_class=HTMLResponse)
def admin_schools(request: Request):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect
    user = user_or_redirect

    with SessionLocal() as db:
        schools = db.scalars(
            select(School).order_by(School.name)
        ).all()

        classes = db.execute(
            select(ClassGroup, School)
            .join(School, School.id == ClassGroup.school_id)
            .order_by(School.name, ClassGroup.name)
        ).all()

    return templates.TemplateResponse(
        request,
        "admin/schools.html",
        {
            "page_title": "Школы и классы",
            "user": user,
            "active_nav": "admin_schools",
            "schools": schools,
            "classes": classes,
        },
    )

@router.post("/schools/new")
async def admin_create_school(request: Request):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    form = await request.form()
    name = (form.get("name") or "").strip()
    city = (form.get("city") or "").strip()

    if not name:
        return RedirectResponse("/admin/schools", status_code=303)

    with SessionLocal() as db:
        db.add(
            School(
                name=name,
                city=city,
            )
        )
        db.commit()

    return RedirectResponse("/admin/schools", status_code=303)

@router.post("/classes/new")
async def admin_create_class(request: Request):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    form = await request.form()

    name = (form.get("name") or "").strip()
    school_id = form.get("school_id")

    if not name or not school_id:
        return RedirectResponse("/admin/schools", status_code=303)

    with SessionLocal() as db:
        db.add(
            ClassGroup(
                name=name,
                school_id=int(school_id),
            )
        )
        db.commit()

    return RedirectResponse("/admin/schools", status_code=303)

@router.post("/users/{user_id}/mentor-classes")
async def admin_user_set_mentor_classes(request: Request, user_id: int):
    user_or_redirect = _require_admin(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    form = await request.form()
    class_group_ids = form.getlist("class_group_ids")

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return RedirectResponse(url="/admin/users/new", status_code=303)

        if user.role != "mentor":
            return RedirectResponse(url="/admin/users/new", status_code=303)

        mentor_profile = db.scalar(
            select(MentorProfile).where(MentorProfile.user_id == user_id)
        )

        if not mentor_profile:
            mentor_profile = MentorProfile(user_id=user_id, full_name="")
            db.add(mentor_profile)
            db.flush()

        old_links = db.scalars(
            select(MentorClassLink).where(MentorClassLink.mentor_profile_id == mentor_profile.id)
        ).all()

        for link in old_links:
            db.delete(link)

        for class_group_id in class_group_ids:
            db.add(
                MentorClassLink(
                    mentor_profile_id=mentor_profile.id,
                    class_group_id=int(class_group_id),
                )
            )

        db.commit()

    return RedirectResponse(url="/admin/users/new", status_code=303)

