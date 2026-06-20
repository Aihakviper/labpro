import argparse
import getpass

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the initial administrator account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    email = str(TypeAdapter(EmailStr).validate_python(args.email)).lower()
    password = getpass.getpass("Password: ")
    password_confirmation = getpass.getpass("Confirm password: ")

    if password != password_confirmation:
        raise SystemExit("Passwords do not match.")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)) is not None:
            raise SystemExit("A user with that email already exists.")

        user = User(
            email=email,
            full_name=args.name.strip(),
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
        )
        db.add(user)
        db.commit()

    print(f"Administrator created: {email}")


if __name__ == "__main__":
    main()

