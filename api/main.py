"""FastAPI application — OptionsLab API.

Local dev:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

Lambda:
    Served via Mangum adapter in api/handler.py.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from api.routers import auth, backtests, contracts, strategies
from api.routers import (
    alpaca_trading,
    backtests_lab,
    economic,
    etrade_oauth,
    etrade_trading,
    forecasting,
    research,
    risk,
    strategy_engine,
    sync,
    user_settings,
    volatility,
)
from config.settings import get_allowed_origins, get_app_env, get_app_version
from storage import create_all_tables, session_scope

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """App lifespan: ensure DB tables exist on startup."""
    create_all_tables()
    yield


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
_env = get_app_env()
_version = get_app_version()

app = FastAPI(
    title="OptionsLab API",
    description="Backtesting, forecasting, and trading dashboard API.",
    version=_version,
    lifespan=lifespan,
    # Hide /docs and /redoc in production
    docs_url=None if _env == "production" else "/docs",
    redoc_url=None if _env == "production" else "/redoc",
    openapi_url=None if _env == "production" else "/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS
# ALLOWED_ORIGINS is injected by CDK (comma-separated list or '*').
# auth is JWT Bearer — credentials=False is correct for '*' origins.
# ---------------------------------------------------------------------------
_origins = get_allowed_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,   # JWT Bearer tokens; not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request timing middleware (logs slow requests)
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_timing_header(request: Request, call_next) -> Response:
    start = time.monotonic()
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
    if elapsed_ms > 5000:
        logger.warning(
            "Slow request: %s %s took %.0f ms",
            request.method,
            request.url.path,
            elapsed_ms,
        )
    return response

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(user_settings.router)
app.include_router(backtests_lab.router)
app.include_router(sync.router)
app.include_router(alpaca_trading.router)
app.include_router(etrade_trading.router)
app.include_router(etrade_oauth.router)
app.include_router(strategies.router)
app.include_router(contracts.router)
app.include_router(backtests.router)
app.include_router(forecasting.router)
app.include_router(strategy_engine.router)
app.include_router(research.router)
app.include_router(economic.router)
app.include_router(volatility.router)
app.include_router(risk.router)

# ---------------------------------------------------------------------------
# Built-in routes
# ---------------------------------------------------------------------------
@app.get("/", tags=["meta"])
def root():
    return {
        "name": "OptionsLab API",
        "version": _version,
        "environment": _env,
        "docs": "/docs" if _env != "production" else "disabled",
    }


@app.get("/health", tags=["meta"])
def health():
    """Health check — used by load balancers and uptime monitors.

    Returns 200 when the API is running and the database is reachable.
    Returns 503 when the database cannot be reached.
    """
    from fastapi import HTTPException
    from sqlalchemy import text

    db_status = "ok"
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Health check DB error: %s", exc)
        db_status = "error"

    payload = {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": _version,
        "environment": _env,
        "checks": {"database": db_status},
    }

    if db_status != "ok":
        raise HTTPException(status_code=503, detail=payload)

    return payload
