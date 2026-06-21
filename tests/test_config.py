from app.core.config import Settings


def make_settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
    )


def test_render_postgresql_url_uses_psycopg3_driver() -> None:
    settings = make_settings("postgresql://user:password@host/database")

    assert settings.database_url == (
        "postgresql+psycopg://user:password@host/database"
    )


def test_legacy_postgres_url_uses_psycopg3_driver() -> None:
    settings = make_settings("postgres://user:password@host/database")

    assert settings.database_url == (
        "postgresql+psycopg://user:password@host/database"
    )


def test_explicit_psycopg_url_is_unchanged() -> None:
    database_url = "postgresql+psycopg://user:password@host/database"

    assert make_settings(database_url).database_url == database_url


def test_cors_origins_do_not_include_trailing_slashes() -> None:
    settings = Settings(
        database_url="postgresql://user:password@host/database",
        jwt_secret_key="test-secret-key-with-at-least-32-characters",
        backend_cors_origins=[
            "https://labpro-seven.vercel.app",
            "http://localhost:8000/",
        ],
    )

    assert settings.cors_origins == [
        "https://labpro-seven.vercel.app",
        "http://localhost:8000",
    ]
