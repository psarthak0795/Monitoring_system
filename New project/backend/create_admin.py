"""
One-off script to create the first Super Admin user — the root of the
role hierarchy (Super Admin -> Admin -> Manager -> TL -> User).
Run with:  python create_admin.py
"""
from getpass import getpass

from app import models
from app.database import SessionLocal, engine, migrate_security_schema
from app.auth import hash_password

migrate_security_schema()
models.Base.metadata.create_all(bind=engine)


def main():
    db = SessionLocal()
    name = input("Super Admin name: ").strip()
    email = input("Super Admin email: ").strip()
    password = getpass("Super Admin password: ")

    if db.query(models.User).filter(models.User.email == email).first():
        print("A user with that email already exists.")
        return

    superadmin = models.User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        role=models.UserRole.superadmin,
        parent_id=None,
    )
    db.add(superadmin)
    db.commit()
    print(f"Super Admin user '{email}' created.")


if __name__ == "__main__":
    main()
