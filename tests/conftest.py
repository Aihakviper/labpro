import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-characters")
os.environ["APP_DEBUG"] = "false"
