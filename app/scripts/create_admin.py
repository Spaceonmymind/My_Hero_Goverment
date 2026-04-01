import os
from dotenv import load_dotenv
from app.infra.security import hash_password
from sqlalchemy import select

from pathlib import Path
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
from app.infra.db import SessionLocal, Base, engine
from app.infra.models import User

Base.metadata.create_all(bind=engine)

def main():
    email = os.getenv("ADMIN_EMAIL", "admin@demo")
    password = os.getenv("ADMIN_PASSWORD", "admin")
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > 72:
        password = pw_bytes[:72].decode("utf-8", errors="ignore")

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            print("Admin already exists:", email)
            return

        u = User(email=email, password_hash=hash_password(password), role="admin")
        db.add(u)
        db.commit()
        print("Created admin:", email, "password:", password)

if __name__ == "__main__":
    main()