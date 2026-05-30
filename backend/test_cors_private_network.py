from fastapi.testclient import TestClient

from main import app


def test_netlify_origin_can_preflight_local_private_network_backend() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://hackersun-ai-video-platform.netlify.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
            "Access-Control-Request-Private-Network": "true",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://hackersun-ai-video-platform.netlify.app"
    assert response.headers["access-control-allow-private-network"] == "true"


def test_netlify_origin_gets_private_network_header_on_actual_response() -> None:
    client = TestClient(app)

    response = client.get(
        "/health",
        headers={
            "Origin": "https://hackersun-ai-video-platform.netlify.app",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://hackersun-ai-video-platform.netlify.app"
    assert response.headers["access-control-allow-private-network"] == "true"
