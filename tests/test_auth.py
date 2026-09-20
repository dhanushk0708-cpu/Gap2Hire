import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_register_and_login_and_me():
    unique_email = f"test-{uuid.uuid4()}@gap2hire.com"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        # Register
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "TestPassword123!",
                "full_name": "Test User",
                "organization_name": f"Test Company {uuid.uuid4()}",
            },
        )

        assert register_response.status_code == 201

        register_data = register_response.json()

        assert "access_token" in register_data
        assert register_data["token_type"] == "bearer"

        token = register_data["access_token"]

        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": unique_email,
                "password": "TestPassword123!",
            },
        )

        assert login_response.status_code == 200

        login_data = login_response.json()

        assert "access_token" in login_data
        assert login_data["token_type"] == "bearer"

        # Current user
        me_response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert me_response.status_code == 200

        me_data = me_response.json()

        assert me_data["email"] == unique_email
        assert me_data["full_name"] == "Test User"
        assert me_data["role"] == "COMPANY_ADMIN"
        assert me_data["is_active"] is True

        # Security check:
        assert "password_hash" not in me_data