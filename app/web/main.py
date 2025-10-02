"""FastAPI application for Telegram Mini App backend."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.web.routers import advice, dashboard, export, inventory, reviews

# Create FastAPI app
app = FastAPI(
    title="SoVAni API",
    version="0.9.0",
    description="Backend API for SoVAni Telegram Mini App - seller analytics platform",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to TMA_ORIGIN in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["Reviews"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["Inventory"])
app.include_router(advice.router, prefix="/api/v1/advice", tags=["Advice"])
app.include_router(export.router, prefix="/api/v1/export", tags=["Export"])


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "app": "SoVAni API", "version": "0.9.0"}


@app.get("/health")
def health():
    """Health check for monitoring."""
    return {"status": "healthy"}
