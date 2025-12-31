"""
AeroStream FastAPI Application
==============================
Main entry point for the REST API.
"""

from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import runs, sessions, channels
from src.api.routes import demo


# Create FastAPI app
app = FastAPI(
    title="AeroStream API",
    description="Wind Tunnel Data Processing Platform for Motorsport Aerodynamics",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for D3.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(runs.router, prefix="/runs", tags=["Runs"])
app.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
app.include_router(channels.router, prefix="/channels", tags=["Channels"])
app.include_router(demo.router, prefix="/demo", tags=["Demo Requests"])


@app.get("/", tags=["Health"])
async def root():
    """API root - redirects to docs."""
    return {
        "message": "AeroStream API",
        "docs": "/docs",
        "version": "2.0.0"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
