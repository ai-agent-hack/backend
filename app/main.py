from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.exceptions import (
    DomainException,
    UserNotFoundError,
    UserAlreadyExistsError,
    InvalidCredentialsError,
    ValidationError,
    UnauthorizedError,
    ForbiddenError,
)
from app.core.model_loader import load_model, warmup

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"🚀 Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    print(f"🌍 Environment: {settings.ENVIRONMENT}")
    print(f"📚 API Documentation: {settings.API_V1_STR}/docs")
    
    # Sentence Transformerモデルのプリロード
    try:
        print("📦 Sentence Transformerモデルをプリロード中...")
        load_model()
        warmup()
        print("✅ モデルのプリロードとウォームアップが完了しました")
    except Exception as e:
        print(f"⚠️ モデルプリロード失敗（サービスは続行）: {str(e)}")
    
    yield
    
    # Shutdown
    print(f"👋 Shutting down {settings.PROJECT_NAME}")

# Create FastAPI application instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="A FastAPI backend built with SOLID principles and GCP Cloud SQL integration",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    max_age=settings.SESSION_MAX_AGE,
    same_site="none",  # allow cross-site requests (required for Cloud Run + separate frontend domain)
    https_only=True,  # ensures cookie is only sent over HTTPS
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=(
        ["*"]
        if settings.ENVIRONMENT == "development"
        else [
            "yourdomain.com",
            "*.run.app",  # Allow Cloud Run URLs
            "fastapi-backend-900145575342.asia-northeast1.run.app",
        ]
    ),
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


# Global exception handlers for domain exceptions
@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(request: Request, exc: UserNotFoundError):
    """Handle UserNotFoundError exceptions."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.message, "type": "user_not_found"},
    )


@app.exception_handler(UserAlreadyExistsError)
async def user_already_exists_handler(request: Request, exc: UserAlreadyExistsError):
    """Handle UserAlreadyExistsError exceptions."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": exc.message, "type": "user_already_exists"},
    )


@app.exception_handler(InvalidCredentialsError)
async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError):
    """Handle InvalidCredentialsError exceptions."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": exc.message, "type": "invalid_credentials"},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle ValidationError exceptions."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"message": exc.message, "type": "validation_error"},
    )


@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(request: Request, exc: UnauthorizedError):
    """Handle UnauthorizedError exceptions."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": exc.message, "type": "unauthorized"},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(ForbiddenError)
async def forbidden_handler(request: Request, exc: ForbiddenError):
    """Handle ForbiddenError exceptions."""
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"message": exc.message, "type": "forbidden"},
    )


@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    """Handle generic domain exceptions."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": exc.message, "type": "domain_error"},
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


# Root endpoint
@app.get("/")
async def read_root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs_url": f"{settings.API_V1_STR}/docs",
        "redoc_url": f"{settings.API_V1_STR}/redoc",
    }


# Legacy startup/shutdown events removed - using lifespan context manager instead
