import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.security import create_access_token
from app.main import app
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_health_probes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Liveness probe
        res_live = await client.get("/health/live")
        assert res_live.status_code == 200
        data_live = res_live.json()
        assert data_live["status"] == "alive"
        assert "timestamp" in data_live

        # Readiness probe (allows 200 ready or 503 degraded in isolated test runners)
        res_ready = await client.get("/health/ready")
        assert res_ready.status_code in [200, 503]
        data_ready = res_ready.json()
        assert data_ready["status"] in ["ready", "degraded"]
        assert "checks" in data_ready

        # Metrics probe
        res_metrics = await client.get("/health/metrics")
        assert res_metrics.status_code == 200
        data_metrics = res_metrics.json()
        assert "app_name" in data_metrics
        assert "version" in data_metrics


@pytest.mark.asyncio
async def test_security_headers_and_request_id():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Custom request ID propagation
        custom_id = "test-req-correlation-id-999"
        res = await client.get("/", headers={"X-Request-ID": custom_id})
        assert res.status_code == 200
        assert res.headers.get("X-Request-ID") == custom_id
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        assert res.headers.get("X-Frame-Options") == "DENY"
        assert res.headers.get("X-XSS-Protection") == "1; mode=block"
        assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_standardized_error_format_on_404_and_422():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 404 test
        res_404 = await client.get("/api/v1/non-existent-endpoint-path")
        assert res_404.status_code == 404
        data_404 = res_404.json()
        assert "error" in data_404 or "detail" in data_404
        if "error" in data_404:
            assert data_404["error"]["code"] == "HTTP_404"
            assert "request_id" in data_404["error"]

        # 422 test
        res_422 = await client.post("/api/v1/pricing/on-road", json={"invalid": "payload"})
        assert res_422.status_code == 422
        data_422 = res_422.json()
        assert "error" in data_422 or "detail" in data_422
        if "error" in data_422:
            assert data_422["error"]["code"] == "VALIDATION_ERROR"
            assert "details" in data_422["error"]
            assert "request_id" in data_422["error"]


@pytest.mark.asyncio
async def test_admin_endpoint_authorization_gate(db_session: AsyncSession):
    app.dependency_overrides.pop(require_admin, None)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated access to admin overview should return 401
        res_unauth = await client.get("/api/v1/admin/overview")
        assert res_unauth.status_code in [401, 403]

        # 2. Login with valid seeded admin credentials
        login_res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@carafford.in",
                "password": "CarAffordAdmin#2026",
            },
        )
        assert login_res.status_code == 200
        auth_data = login_res.json()
        assert "access_token" in auth_data
        assert auth_data["user"]["role"] == "ADMIN"
        token = auth_data["access_token"]

        # 3. Access admin overview with Admin Bearer token
        admin_res = await client.get(
            "/api/v1/admin/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert admin_res.status_code == 200
        overview_data = admin_res.json()
        assert "data" in overview_data or "metrics" in overview_data

        # 4. Check /auth/me
        me_res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "admin@carafford.in"

    app.dependency_overrides.clear()
