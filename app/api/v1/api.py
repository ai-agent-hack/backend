from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, firebase_auth, vertex, spot, pre_info

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

# Include spot routes
api_router.include_router(spot.router, prefix="/spot", tags=["spot"])

# Include pre_info routes
api_router.include_router(pre_info.router, prefix="/pre_info", tags=["pre_info"])