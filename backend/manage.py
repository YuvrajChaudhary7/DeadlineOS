"""Trusted local account provisioning commands. Never expose this as a public endpoint."""
import getpass
import re

from werkzeug.security import generate_password_hash

from app import app
from database import db
from models import User


def create_admin():
    email = input("Admin email: ").strip().lower()
    first = input("First name: ").strip()
    last = input("Last name: ").strip()
    password = getpass.getpass("Password (12+ characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email): raise SystemExit("Enter a valid email address.")
    if not first or not last or len(password) < 12 or password != confirm: raise SystemExit("Names, matching passwords, and at least 12 characters are required.")
    with app.app_context():
        if User.query.filter_by(email=email).first(): raise SystemExit("That email is already in use.")
        user = User(email=email, password_hash=generate_password_hash(password), role="admin", first_name=first, last_name=last)
        db.session.add(user); db.session.commit()
        print(f"Admin account created for {email}.")


if __name__ == "__main__":
    if len(__import__("sys").argv) != 2 or __import__("sys").argv[1] != "create-admin":
        raise SystemExit("Usage: python backend/manage.py create-admin")
    create_admin()
