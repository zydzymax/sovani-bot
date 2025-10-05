"""FastAPI application for Telegram Mini App backend."""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.logging import get_logger
from app.core.metrics import app_info, app_uptime_seconds
from app.web.middleware import PrometheusMiddleware

log = get_logger("sovani_bot.web")
from app.web.routers import (
    advice,
    bi_export,
    dashboard,
    dev,
    export,
    finance,
    healthcheck,
    inventory,
    ops,
    orgs,
    pricing,
    reviews,
    reviews_sla,
    supply,
)

# Application start time for uptime calculation
APP_START_TIME = time.time()

# Create FastAPI app
app = FastAPI(
    title="SoVAni API",
    version="0.11.0",
    description="Backend API for SoVAni Telegram Mini App - seller analytics platform",
)

# Add Prometheus middleware (Stage 11)
app.add_middleware(PrometheusMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to TMA_ORIGIN in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set app info metric
app_info.labels(version="0.11.0", environment="production").set(1)


# Global exception handler for unhandled errors (500)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with proper logging and response."""
    request_id = str(uuid.uuid4())

    log.error(
        "unhandled_exception",
        extra={
            "request_id": request_id,
            "path": str(request.url.path),
            "method": request.method,
            "error": str(exc),
            "error_type": type(exc).__name__,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "request_id": request_id,
            "hint": "Contact support with this request_id",
        },
    )

# Include routers
app.include_router(healthcheck.router, tags=["Monitoring"])
app.include_router(dev.router, prefix="/api/v1/dev", tags=["Development"])  # DEV mode only
app.include_router(orgs.router, tags=["Organizations"])  # Stage 19: Multi-tenant
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["Reviews"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["Inventory"])
app.include_router(advice.router, prefix="/api/v1/advice", tags=["Advice"])
app.include_router(supply.router, tags=["Supply"])
app.include_router(pricing.router, tags=["Pricing"])
app.include_router(export.router, prefix="/api/v1/export", tags=["Export"])
app.include_router(bi_export.router, prefix="/api/v1/export", tags=["BI Export"])
app.include_router(finance.router, tags=["Finance"])
app.include_router(ops.router, tags=["Operations"])
app.include_router(reviews_sla.router, tags=["Reviews SLA"])

# Mount static files for Telegram Mini App
app.mount("/app", StaticFiles(directory="static", html=True), name="static")


@app.get("/")
def root():
    """Redirect to TMA."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/app/")


@app.get("/health")
def health():
    """Basic health check for monitoring."""
    return {"status": "healthy"}


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    # Update uptime metric
    uptime = time.time() - APP_START_TIME
    app_uptime_seconds.set(uptime)

    # Generate Prometheus metrics
    metrics_data = generate_latest()
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
