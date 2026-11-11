from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.core.exceptions import HRAException
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api import api_router
from app.services.langfuse_observability import shutdown as shutdown_langfuse
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

    @app.exception_handler(HRAException)
    async def handle_hra_error(request: Request, exc: HRAException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        # Pydantic/FastAPI validation details can echo the submitted body,
        # including passwords and setup tokens. Never return those to callers.
        return JSONResponse(status_code=422, content={"detail": "Dữ liệu gửi đi không hợp lệ."})

    # Include API routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["Health Check"])
    async def health_check():
        """Liveness probe - returns immediately without checking downstream dependencies."""
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "environment": settings.APP_ENV
        }

    @app.get("/health/ready", tags=["Health Check"])
    async def readiness_check():
        """Readiness probe - verifies database connectivity."""
        from sqlalchemy import text
        from app.db.database import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception as exc:
            logger.error("Database readiness check failed", error_type=type(exc).__name__)
            return JSONResponse(status_code=503, content={"status": "unhealthy", "database": "unavailable"})
        finally:
            db.close()
        return {
            "status": "ready",
            "database": db_status,
            "app": settings.APP_NAME,
            "environment": settings.APP_ENV,
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
        shutdown_langfuse()

    return app


app = create_app()
