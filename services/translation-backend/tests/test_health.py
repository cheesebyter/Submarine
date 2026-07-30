import pytest
from httpx import ASGITransport, AsyncClient

from submarine_backend.main import app


@pytest.mark.asyncio
async def test_health_endpoint_contains_no_runtime_or_content_data() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "service": "translation-backend",
        "version": "0.1.0",
        "model_status": "model_missing",
        "model_name": "Systran/faster-whisper-large-v3",
        "device": "cuda",
    }
