import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/eve"
)
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-real-life-use-a-long-random-string")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-webhook-secret")

# comma separated list, anyone signing up with these emails becomes an admin
ADMIN_EMAILS = [
    e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()
]
