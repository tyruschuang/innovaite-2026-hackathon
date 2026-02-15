import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import eligibility, runway, evidence, packet, plan

# Show debug logs from our LLM client so we can diagnose CommonStack issues
logging.basicConfig(level=logging.INFO)
logging.getLogger("app.services.llm_client").setLevel(logging.DEBUG)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Remedy API",
        description="Money-in-hand fastest path generator for disaster-impacted small businesses and nonprofits.",
        version="0.1.0",
    )

    # CORS — use wildcard origin; frontend doesn't send credentials
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(eligibility.router, prefix="/eligibility", tags=["Eligibility"])
    app.include_router(runway.router, prefix="/runway", tags=["Runway"])
    app.include_router(evidence.router, prefix="/ai/evidence", tags=["Evidence AI"])
    app.include_router(packet.router, prefix="/packet", tags=["Packet"])
    app.include_router(plan.router, prefix="/plan", tags=["Plan"])

    # Health check
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Global exception handler — re-raise HTTPExceptions so FastAPI's
    # built-in handler (which respects CORS middleware) handles them.
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            raise exc
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(exc)}"},
        )

    return app


app = create_app()
