"""
One-time setup script to create the admin account.

Run this locally (pointed at your production DATABASE_URL) or from Render's
Shell tab, AFTER schema.sql has been run:

    python create_admin.py

It will prompt for an admin username, email, and password, hash the
password, and insert an approved admin user directly into the database.
"""
import os
import getpass
import psycopg2
from werkzeug.security import generate_password_hash

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/login_app"
)


def main():
    username = input("Admin username: ").strip()
    email = input("Admin email: ").strip()
    password = getpass.getpass("Admin password: ")

    hashed = generate_password_hash(password)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO users (username, email, password, role, status)
                   VALUES (%s, %s, %s, 'admin', 'approved')""",
                (username, email, hashed),
            )
            conn.commit()
        print(f"Admin user '{username}' created successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
