from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.presentation.web.templates_env import templates
from app.infra.db import SessionLocal
from app.infra.models import (
    User,
    StudentProfile,
    MentorProfile,
    MentorClassLink,
    ClassGroup,
    School,
    TaskSubmission,
    Task,
    PointsLedger,
    SubmissionFile,
)


router = APIRouter(prefix="/mentor", tags=["mentor"])


def _get_user(request: Request) -> dict | None:
    role = request.cookies.get("mh_role")
    email = request.cookies.get("mh_email")
    if not role or not email:
        return None
    return {"role": role, "email": email}


def _require_mentor(request: Request):
    user = _get_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    if user["role"] != "mentor":
        return RedirectResponse(url="/", status_code=303)
    return user


@router.get("", response_class=HTMLResponse)
def mentor_dashboard(request: Request):
    user_or_redirect = _require_mentor(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    user = user_or_redirect

    with SessionLocal() as db:
        db_user = db.scalar(
            select(User).where(User.email == user["email"])
        )
        if not db_user:
            return RedirectResponse(url="/auth/login", status_code=303)

        mentor_profile = db.scalar(
            select(MentorProfile).where(MentorProfile.user_id == db_user.id)
        )
        if not mentor_profile:
            return templates.TemplateResponse(
                request,
                "mentor/dashboard.html",
                {
                    "page_title": "Кабинет наставника",
                    "user": user,
                    "active_nav": "mentor_dashboard",
                    "students": [],
                    "reviews": [],
                    "class_groups": [],
                },
            )

        mentor_links = db.scalars(
            select(MentorClassLink).where(
                MentorClassLink.mentor_profile_id == mentor_profile.id
            )
        ).all()

        class_group_ids = [link.class_group_id for link in mentor_links]

        class_groups = []
        if class_group_ids:
            class_groups = db.execute(
                select(ClassGroup, School)
                .join(School, School.id == ClassGroup.school_id)
                .where(ClassGroup.id.in_(class_group_ids))
                .order_by(School.name, ClassGroup.name)
            ).all()

        students = []
        student_user_ids = []

        if class_group_ids:
            student_profiles = db.scalars(
                select(StudentProfile).where(
                    StudentProfile.class_group_id.in_(class_group_ids)
                )
            ).all()

            student_user_ids = [p.user_id for p in student_profiles]

            users = []
            if student_user_ids:
                users = db.scalars(
                    select(User).where(User.id.in_(student_user_ids))
                ).all()

            user_map = {u.id: u for u in users}
            class_map = {cg.id: (cg, s) for cg, s in class_groups}

            for profile in student_profiles:
                u = user_map.get(profile.user_id)
                cg_school = class_map.get(profile.class_group_id)

                class_name = ""
                school_name = ""

                if cg_school:
                    cg, school = cg_school
                    class_name = cg.name
                    school_name = school.name

                students.append(
                    {
                        "user_id": profile.user_id,
                        "email": u.email if u else "",
                        "full_name": profile.full_name or (u.email if u else "Ученик"),
                        "class_name": class_name,
                        "school_name": school_name,
                        "points_balance": profile.points_balance,
                    }
                )

        reviews = []
        if student_user_ids:
            rows = db.execute(
                select(TaskSubmission, Task, User)
                .join(Task, Task.id == TaskSubmission.task_id)
                .join(User, User.id == TaskSubmission.user_id)
                .where(TaskSubmission.user_id.in_(student_user_ids))
                .order_by(TaskSubmission.created_at.desc())
            ).all()

            for sub, task, student in rows:
                reviews.append(
                    {
                        "id": sub.id,
                        "student": student.email,
                        "task_title": task.title,
                        "points": task.points,
                        "submitted_at": sub.created_at.strftime("%Y-%m-%d %H:%M") if sub.created_at else "",
                        "status": sub.status,
                    }
                )

    return templates.TemplateResponse(
        request,
        "mentor/dashboard.html",
        {
            "page_title": "Кабинет наставника",
            "user": user,
            "active_nav": "mentor_dashboard",
            "students": students,
            "reviews": reviews,
            "class_groups": class_groups,
        },
    )

@router.get("/reviews/{submission_id}", response_class=HTMLResponse)
def mentor_review_detail(request: Request, submission_id: int):
    user_or_redirect = _require_mentor(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    user = user_or_redirect

    with SessionLocal() as db:
        db_user = db.scalar(select(User).where(User.email == user["email"]))
        if not db_user:
            return RedirectResponse(url="/auth/login", status_code=303)

        mentor_profile = db.scalar(
            select(MentorProfile).where(MentorProfile.user_id == db_user.id)
        )
        if not mentor_profile:
            return RedirectResponse(url="/mentor", status_code=303)

        mentor_links = db.scalars(
            select(MentorClassLink).where(
                MentorClassLink.mentor_profile_id == mentor_profile.id
            )
        ).all()

        class_group_ids = [l.class_group_id for l in mentor_links]

        submission = db.scalar(
            select(TaskSubmission).where(TaskSubmission.id == submission_id)
        )
        if not submission:
            return RedirectResponse(url="/mentor", status_code=303)

        student_profile = db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == submission.user_id)
        )

        if not student_profile or student_profile.class_group_id not in class_group_ids:
            return RedirectResponse(url="/mentor", status_code=303)

        task = db.get(Task, submission.task_id)
        student = db.get(User, submission.user_id)

        files = db.scalars(
            select(SubmissionFile)
            .where(SubmissionFile.submission_id == submission.id)
            .order_by(SubmissionFile.id.desc())
        ).all()

    return templates.TemplateResponse(
        request,
        "mentor/review_detail.html",
        {
            "page_title": "Проверка задания",
            "user": user,
            "active_nav": "mentor_dashboard",
            "submission": submission,
            "task": task,
            "student": student,
            "profile": student_profile,
            "files": files,
        },
    )

@router.post("/reviews/{submission_id}")
async def mentor_review_action(request: Request, submission_id: int):
    user_or_redirect = _require_mentor(request)
    if not isinstance(user_or_redirect, dict):
        return user_or_redirect

    user = user_or_redirect
    form = await request.form()
    action = form.get("action")

    with SessionLocal() as db:
        db_user = db.scalar(select(User).where(User.email == user["email"]))
        mentor_profile = db.scalar(
            select(MentorProfile).where(MentorProfile.user_id == db_user.id)
        )

        mentor_links = db.scalars(
            select(MentorClassLink).where(
                MentorClassLink.mentor_profile_id == mentor_profile.id
            )
        ).all()

        class_group_ids = [l.class_group_id for l in mentor_links]

        submission = db.get(TaskSubmission, submission_id)
        if not submission:
            return RedirectResponse(url="/mentor", status_code=303)

        student_profile = db.scalar(
            select(StudentProfile).where(
                StudentProfile.user_id == submission.user_id
            )
        )

        if not student_profile or student_profile.class_group_id not in class_group_ids:
            return RedirectResponse(url="/mentor", status_code=303)

        task = db.get(Task, submission.task_id)

        if action == "approve":
            already_approved = submission.status == "approved"
            submission.status = "approved"

            if not already_approved:
                student_profile.points_balance += task.points

                db.add(
                    PointsLedger(
                        user_id=submission.user_id,
                        submission_id=submission.id,
                        points=task.points,
                        reason=f"Зачтено задание: {task.title}",
                        source_role="mentor",
                    )
                )

        elif action == "reject":
            submission.status = "rejected"

        db.commit()

    return RedirectResponse(url="/mentor", status_code=303)