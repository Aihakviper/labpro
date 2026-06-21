from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import Settings


def test_vercel_origin_is_allowed_by_cors() -> None:
    expected_origin = "https://labpro-seven.vercel.app"
    settings = Settings(
        database_url="postgresql://user:password@host/database",
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
        backend_cors_origins=[expected_origin],
    )
    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    with TestClient(test_app) as client:
        response = client.options(
            "/login",
            headers={
                "Origin": expected_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == expected_origin
