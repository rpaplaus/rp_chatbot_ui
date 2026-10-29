import argparse
import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, or_, func
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User

async def create_user(username: str, email: str, password: str, role: str):
    async with AsyncSessionLocal() as db:
        stmt = select(User).where(
            or_(
                func.lower(User.username) == username.lower().strip(),
                func.lower(User.email) == email.lower().strip()
            )
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            print(f"❌ Erro: Usuário '{username}' ou e-mail '{email}' já existe (ID: {existing.id}).")
            return

        new_user = User(
            username=username.strip(),
            email=email.strip().lower(),
            hashed_password=hash_password(password),
            role=role.strip().lower(),
            is_active=True
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        print(f"✅ Usuário criado com sucesso na Whitelist:")
        print(f"   ID:       {new_user.id}")
        print(f"   Username: {new_user.username}")
        print(f"   Email:    {new_user.email}")
        print(f"   Role:     {new_user.role}")

async def list_users():
    async with AsyncSessionLocal() as db:
        stmt = select(User).order_by(User.created_at.asc())
        res = await db.execute(stmt)
        users = res.scalars().all()
        print("=" * 85)
        print(f"{'ID':<38} | {'USERNAME':<15} | {'EMAIL':<22} | {'ROLE':<7} | {'ACTIVE'}")
        print("-" * 85)
        for u in users:
            print(f"{str(u.id):<38} | {u.username:<15} | {u.email:<22} | {u.role:<7} | {u.is_active}")
        print("=" * 85)

async def toggle_status(username: str):
    async with AsyncSessionLocal() as db:
        stmt = select(User).where(func.lower(User.username) == username.lower().strip())
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            print(f"❌ Usuário '{username}' não encontrado.")
            return
        user.is_active = not user.is_active
        await db.commit()
        status_str = "ATIVO" if user.is_active else "DESATIVADO"
        print(f"✅ Status de '{user.username}' alterado para: {status_str}")

async def reset_password(username: str, password: str):
    async with AsyncSessionLocal() as db:
        stmt = select(User).where(func.lower(User.username) == username.lower().strip())
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            print(f"❌ Usuário '{username}' não encontrado.")
            return
        user.hashed_password = hash_password(password)
        await db.commit()
        print(f"✅ Senha de '{user.username}' redefinida com sucesso.")

async def delete_user(username: str):
    async with AsyncSessionLocal() as db:
        stmt = select(User).where(func.lower(User.username) == username.lower().strip())
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            print(f"❌ Usuário '{username}' não encontrado.")
            return
        await db.delete(user)
        await db.commit()
        print(f"✅ Usuário '{username}' e todas as suas sessões foram removidos.")

def main():
    parser = argparse.ArgumentParser(description="RP_ChatBot - Whitelist User Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create_p = subparsers.add_parser("create", help="Add a new authorized user to the Whitelist")
    create_p.add_argument("--username", required=True, help="Unique username")
    create_p.add_argument("--email", required=True, help="Unique email address")
    create_p.add_argument("--password", required=True, help="Plaintext password (will be hashed with Bcrypt)")
    create_p.add_argument("--role", default="user", choices=["admin", "user"], help="User role")

    # list
    subparsers.add_parser("list", help="List all registered users in the Whitelist")

    # toggle-status
    toggle_p = subparsers.add_parser("toggle-status", help="Activate or deactivate a user account")
    toggle_p.add_argument("--username", required=True, help="Username to toggle")

    # reset-password
    reset_p = subparsers.add_parser("reset-password", help="Reset a user's password")
    reset_p.add_argument("--username", required=True, help="Username")
    reset_p.add_argument("--password", required=True, help="New plaintext password")

    # delete
    del_p = subparsers.add_parser("delete", help="Delete a user and their sessions")
    del_p.add_argument("--username", required=True, help="Username to delete")

    args = parser.parse_args()

    if args.command == "create":
        asyncio.run(create_user(args.username, args.email, args.password, args.role))
    elif args.command == "list":
        asyncio.run(list_users())
    elif args.command == "toggle-status":
        asyncio.run(toggle_status(args.username))
    elif args.command == "reset-password":
        asyncio.run(reset_password(args.username, args.password))
    elif args.command == "delete":
        asyncio.run(delete_user(args.username))

if __name__ == "__main__":
    main()

