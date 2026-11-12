"""
Create an admin account, or promote an existing user to admin.

Usage (from the project root):
    python create_admin.py <username>             create a new admin, or promote <username> if it exists
    python create_admin.py <username> --demote    turn an admin back into a student

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
    parser = argparse.ArgumentParser(description="Create or promote an admin user.")
    parser.add_argument("username")
    parser.add_argument("--demote", action="store_true", help="make the user a student again")
    args = parser.parse_args()

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
            user.role = RoleEnum.admin          # type: ignore
            db.commit()
            print(f"Existing user '{args.username}' promoted to admin. They must log in again.")
            return 0

        password = getpass.getpass("Password for the new admin: ")
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
            role=RoleEnum.admin,
            registered_date=utcnow(),
        ))
        db.commit()
        print(f"Admin '{valid.username}' created.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
