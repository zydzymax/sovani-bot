"""FastAPI application for Telegram Mini App backend."""

from __future__ import annotations

import time

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.metrics import app_info, app_uptime_seconds
from app.web.middleware import PrometheusMiddleware
from app.web.routers import advice, dashboard, export, healthcheck, inventory, reviews, supply

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

# Include routers
app.include_router(healthcheck.router, tags=["Monitoring"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["Reviews"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["Inventory"])
app.include_router(advice.router, prefix="/api/v1/advice", tags=["Advice"])
app.include_router(supply.router, tags=["Supply"])
app.include_router(export.router, prefix="/api/v1/export", tags=["Export"])


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "app": "SoVAni API", "version": "0.11.0"}


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
