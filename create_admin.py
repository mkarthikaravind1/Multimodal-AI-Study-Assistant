"""
Create an admin account, promote an existing user, or make someone a teacher.

Usage (from the project root):
    python create_admin.py <username>             create a new admin, or promote <username> if it exists
    python create_admin.py <username> --teacher   make <username> a teacher (creates the account if needed)
    python create_admin.py <username> --demote    turn an admin or teacher back into a student

The password is typed at a hidden prompt — it never appears on screen
or in your shell history.
"""
import argparse
import getpass
import sys

from pydantic import ValidationError

from auth import hash_password
from database import SessionLocal, utcnow
from models import RoleEnum, User
from schemas import RegisterRequest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote an admin or teacher.")
    parser.add_argument("username")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--teacher", action="store_true", help="make the user a teacher instead of an admin")
    group.add_argument("--demote", action="store_true", help="make the user a student again")
    args = parser.parse_args()
    role = RoleEnum.teacher if args.teacher else RoleEnum.admin
    label = role.value

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.username).first()

        if args.demote:
            if not user:
                print(f"No user named '{args.username}'.")
                return 1
            user.role = RoleEnum.student        # type: ignore
            db.commit()
            print(f"'{args.username}' is now a student.")
            return 0

        if user:
            user.role = role                    # type: ignore
            db.commit()
            print(f"Existing user '{args.username}' is now a {label}. They must log in again.")
            return 0

        password = getpass.getpass(f"Password for the new {label}: ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords don't match.")
            return 1

        try:
            valid = RegisterRequest(username=args.username, password=password)   # same rules as /register
        except ValidationError as e:
            for err in e.errors():
                print(f"{err['loc'][-1]}: {err['msg']}")
            return 1

        db.add(User(
            username=valid.username,
            password_hash=hash_password(valid.password),
            role=role,
            registered_date=utcnow(),
        ))
        db.commit()
        print(f"{label.capitalize()} '{valid.username}' created.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
