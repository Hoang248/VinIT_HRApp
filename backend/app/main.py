from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api import api_router
from app.workers.processor import worker

# Setup logging first
setup_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="VinUniversity AI-Native CV Matching & Ranking Platform API",
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["Health Check"])
    async def health_check():
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "environment": settings.APP_ENV
        }

    @app.on_event("startup")
    async def startup_event():
        logger.info(
            "Starting VinUni HRA Backend",
            environment=settings.APP_ENV,
            debug=settings.DEBUG
        )
        # Start background processing worker
        if settings.APP_ENV != "testing":
            worker.start()
            logger.info("Background processing worker started automatically")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down VinUni HRA Backend")
        worker.stop()

    return app


app = create_app()
