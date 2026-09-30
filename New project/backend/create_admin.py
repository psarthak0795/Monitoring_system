"""Create the first Super Admin or explicitly reset an existing one."""
import argparse
from getpass import getpass

from app import models
from app.database import SessionLocal, engine, migrate_security_schema
from app.auth import hash_password

migrate_security_schema()
models.Base.metadata.create_all(bind=engine)


def confirmed_password(prompt):
    password = getpass(prompt)
    if not password:
        raise ValueError("Password cannot be empty.")
    if password != getpass("Confirm password: "):
        raise ValueError("Passwords did not match.")
    return password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset-password",
        metavar="EMAIL",
        help="reset the password of an existing Super Admin account",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset_password:
            user = db.query(models.User).filter(
                models.User.email == args.reset_password.strip()
            ).first()
            if user is None:
                print(f"No account found for '{args.reset_password}'.")
                return
            if user.role != models.UserRole.superadmin:
                print(f"'{user.email}' is not a Super Admin account; no changes made.")
                return

            user.hashed_password = hash_password(
                confirmed_password("New Super Admin password: ")
            )
            db.commit()
            print(f"Password reset for Super Admin '{user.email}'.")
            return

        name = input("Super Admin name: ").strip()
        email = input("Super Admin email: ").strip()
        if not name or not email:
            print("Name and email are required.")
            return

        if db.query(models.User).filter(models.User.email == email).first():
            print("A user with that email already exists. Use --reset-password EMAIL to reset a Super Admin password.")
            return

        superadmin = models.User(
            name=name,
            email=email,
            hashed_password=hash_password(
                confirmed_password("Super Admin password: ")
            ),
            role=models.UserRole.superadmin,
            parent_id=None,
        )
        db.add(superadmin)
        db.commit()
        print(f"Super Admin user '{email}' created.")
    except ValueError as error:
        print(error)
    finally:
        db.close()


if __name__ == "__main__":
    main()
