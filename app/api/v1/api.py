from fastapi import APIRouter

from app.api.v1.endpoints import firebase_auth, vertex, trip, pre_info

api_router = APIRouter()

# Include Firebase authentication routes
api_router.include_router(
    firebase_auth.router, prefix="/firebase-auth", tags=["firebase-authentication"]
)

# Include vertex routes
api_router.include_router(vertex.router, prefix="/vertex", tags=["vertex"])

# Include trip routes
api_router.include_router(trip.router, prefix="/trip", tags=["trip"])

# Include pre_info routes
api_router.include_router(pre_info.router, prefix="/pre_info", tags=["pre_info"])
