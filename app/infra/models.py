from sqlalchemy import String, DateTime, func, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="Общее")
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class TaskSubmission(Base):
    __tablename__ = "task_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    task_id = mapped_column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        index=True
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    class_name: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    school_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    birth_date: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    parent_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    parent_phone: Mapped[str] = mapped_column(String(50), nullable=False, default="")

    about: Mapped[str] = mapped_column(Text, nullable=False, default="")
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    points_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    class_group_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("class_groups.id"),
        nullable=True,
        index=True,
    )

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

class SubmissionFile(Base):
    __tablename__ = "submission_files"

    id: Mapped[int] = mapped_column(primary_key=True)

    submission_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("task_submissions.id"),
        nullable=False,
        index=True
    )

    original_name: Mapped[str] = mapped_column(String(255), nullable=False)

    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)

    content_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ClassGroup(Base):
    __tablename__ = "class_groups"

    id: Mapped[int] = mapped_column(primary_key=True)

    school_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("schools.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MentorProfile(Base):
    __tablename__ = "mentor_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    school_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("schools.id"),
        nullable=True,
        index=True,
    )

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MentorClassLink(Base):
    __tablename__ = "mentor_class_links"

    id: Mapped[int] = mapped_column(primary_key=True)

    mentor_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mentor_profiles.id"),
        nullable=False,
        index=True,
    )

    class_group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("class_groups.id"),
        nullable=False,
        index=True,
    )

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

class PointsLedger(Base):
    __tablename__ = "points_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    submission_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("task_submissions.id"),
        nullable=True,
        index=True,
    )

    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    source_role: Mapped[str] = mapped_column(String(20), nullable=False, default="system")

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )