"""Lambda entrypoint for FastAPI via Mangum (ASGI)."""

from mangum import Mangum

from api.main import app
from storage import create_all_tables

# Ensure tables exist on cold start (idempotent).
create_all_tables()

handler = Mangum(app, lifespan="off")
