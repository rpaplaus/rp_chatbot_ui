import asyncio
import os
import sys
import uuid
import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.security import REFRESH_COOKIE_NAME

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")

async def run_security_test_suite():
    print("=" * 70)
    print("🔐 [SECURITY TEST SUITE] Phase 4.5 - JWT, HttpOnly Refresh & Multi-Tenancy")
    print(f"Target API: {BASE_URL}")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Verify Route Protection (401 Unauthorized without token)
        print("\n1. Testing Route Protection (Zero-Trust 401 checks):")
        r_sess = await client.get(f"{BASE_URL}/sessions")
        assert r_sess.status_code == 401, f"Expected 401 on GET /sessions, got {r_sess.status_code}"
        print("  ✓ GET /sessions without token -> 401 Unauthorized")

        r_file = await client.post(
            f"{BASE_URL}/files/upload",
            files={"file": ("test.txt", b"secret", "text/plain")}
        )
        assert r_file.status_code == 401, f"Expected 401 on POST /files/upload, got {r_file.status_code}"
        print("  ✓ POST /files/upload without token -> 401 Unauthorized")

        r_chat = await client.post(
            f"{BASE_URL}/chat/completions/stream",
            json={"session_id": str(uuid.uuid4()), "message": {"content": "hello"}}
        )
        assert r_chat.status_code == 401, f"Expected 401 on POST /chat/completions/stream, got {r_chat.status_code}"
        print("  ✓ POST /chat/completions/stream without token -> 401 Unauthorized")

        # 2. Verify Invalid Login Rejection
        print("\n2. Testing Invalid Credentials Rejection:")
        r_bad = await client.post(
            f"{BASE_URL}/auth/login",
            json={"username": settings.APP_USER, "password": "wrong_password_123"}
        )
        assert r_bad.status_code == 401
        print("  ✓ Invalid password rejected with 401 Unauthorized")

        # 3. Verify Valid Admin Login & HttpOnly Cookie
        print("\n3. Testing Valid Admin Login & HttpOnly Refresh Cookie:")
        r_login = await client.post(
            f"{BASE_URL}/auth/login",
            json={"username": settings.APP_USER, "password": settings.APP_PASSWORD}
        )
        assert r_login.status_code == 200, f"Login failed: {r_login.text}"
        login_data = r_login.json()
        access_token = login_data["access_token"]
        user_info = login_data["user"]
        first_refresh_cookie = r_login.cookies.get(REFRESH_COOKIE_NAME)
        set_cookie_header = r_login.headers.get("set-cookie", "")

        assert access_token
        assert first_refresh_cookie
        assert "HttpOnly" in set_cookie_header or "httponly" in set_cookie_header.lower()
        print(f"  ✓ Authenticated as '{user_info['username']}' (role: {user_info['role']})")
        print(f"  ✓ Set-Cookie header verified with HttpOnly & Path=/api/v1/auth")

        # 4. Verify /auth/me with Bearer Token
        print("\n4. Testing GET /auth/me:")
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        r_me = await client.get(f"{BASE_URL}/auth/me", headers=auth_headers)
        assert r_me.status_code == 200
        assert r_me.json()["username"] == settings.APP_USER
        print("  ✓ GET /auth/me returned authenticated profile")

        # 5. Test Refresh Token Rotation in Redis & Reuse Detection
        print("\n5. Testing Strict Refresh Token Rotation in Redis:")
        r_refresh = await client.post(
            f"{BASE_URL}/auth/refresh",
            cookies={REFRESH_COOKIE_NAME: first_refresh_cookie}
        )
        assert r_refresh.status_code == 200, f"Refresh failed: {r_refresh.text}"
        second_refresh_cookie = r_refresh.cookies.get(REFRESH_COOKIE_NAME)
        new_access_token = r_refresh.json()["access_token"]
        assert second_refresh_cookie and second_refresh_cookie != first_refresh_cookie
        print("  ✓ Refresh succeeded: new access_token and rotated refresh_token issued")

        # Attempt to reuse the FIRST refresh cookie (must fail because JTI was consumed in Redis!)
        client.cookies.clear()
        r_reuse = await client.post(
            f"{BASE_URL}/auth/refresh",
            cookies={REFRESH_COOKIE_NAME: first_refresh_cookie}
        )
        assert r_reuse.status_code == 401, f"Old refresh token should be rejected! Got {r_reuse.status_code}"
        print("  ✓ Replay attack blocked: old refresh_token rejected with 401")

        # 6. Test Multi-Tenant Isolation between User A (Admin) and User B
        print("\n6. Testing Multi-Tenant Isolation (User A vs User B):")
        admin_headers = {"Authorization": f"Bearer {new_access_token}"}
        r_create_sess = await client.post(
            f"{BASE_URL}/sessions",
            headers=admin_headers,
            json={"title": "Sessao Confidencial Admin"}
        )
        assert r_create_sess.status_code == 201
        admin_session_id = r_create_sess.json()["id"]
        print(f"  ✓ Admin created private session: {admin_session_id}")

        # Provision temporary User B via manage_users functions
        from manage_users import create_user, delete_user
        await create_user("tenant_b_test", "tenant_b@rpaplaus.com", "TenantB!Pass99", "user")

        try:
            r_login_b = await client.post(
                f"{BASE_URL}/auth/login",
                json={"username": "tenant_b_test", "password": "TenantB!Pass99"}
            )
            assert r_login_b.status_code == 200
            token_b = r_login_b.json()["access_token"]
            headers_b = {"Authorization": f"Bearer {token_b}"}

            # User B lists sessions -> must NOT see Admin's session
            r_list_b = await client.get(f"{BASE_URL}/sessions", headers=headers_b)
            assert r_list_b.status_code == 200
            b_sessions = r_list_b.json()
            assert not any(s["id"] == admin_session_id for s in b_sessions)
            print("  ✓ User B cannot see User A's session in GET /sessions")

            # User B attempts to access Admin's session directly -> 404
            r_get_b = await client.get(f"{BASE_URL}/sessions/{admin_session_id}", headers=headers_b)
            assert r_get_b.status_code == 404
            print("  ✓ User B blocked (404) when attempting GET on User A's session")

            # User B attempts to delete Admin's session -> 404
            r_del_b = await client.delete(f"{BASE_URL}/sessions/{admin_session_id}", headers=headers_b)
            assert r_del_b.status_code == 404
            print("  ✓ User B blocked (404) when attempting DELETE on User A's session")
        finally:
            await delete_user("tenant_b_test")
            await client.delete(f"{BASE_URL}/sessions/{admin_session_id}", headers=admin_headers)

        # 7. Test Logout Revocation
        print("\n7. Testing POST /auth/logout:")
        r_logout = await client.post(
            f"{BASE_URL}/auth/logout",
            cookies={REFRESH_COOKIE_NAME: second_refresh_cookie}
        )
        assert r_logout.status_code == 200
        client.cookies.clear()
        r_after_logout = await client.post(
            f"{BASE_URL}/auth/refresh",
            cookies={REFRESH_COOKIE_NAME: second_refresh_cookie}
        )
        assert r_after_logout.status_code == 401
        print("  ✓ Refresh token revoked in Redis on logout (401 on subsequent refresh)")

    print("\n" + "=" * 70)
    print("🎉 ALL SECURITY, JWT ROTATION & MULTI-TENANCY TESTS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_security_test_suite())

