from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, firebase_auth, vertex

api_router = APIRouter()

# Include authentication routes
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Include Firebase authentication routes
api_router.include_router(
    firebase_auth.router, prefix="/firebase-auth", tags=["firebase-authentication"]
)

# Include user management routes
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Include vertex routes
api_router.include_router(vertex.router, prefix="/vertex", tags=["vertex"])
