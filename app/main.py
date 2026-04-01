from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.presentation.web.routes.auth_routes import router as auth_router
from app.presentation.web.routes.student_routes import router as student_router
from app.presentation.web.routes.admin_routes import router as admin_router
from app.presentation.web.routes.mentor_routes import router as mentor_router
from app.infra.db import Base, engine
from app.infra import models

Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.app_name)

app.mount(
    "/static",
    StaticFiles(directory="app/presentation/web/static"),
    name="static",
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth_router)
app.include_router(student_router)
app.include_router(admin_router)
app.include_router(mentor_router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}
