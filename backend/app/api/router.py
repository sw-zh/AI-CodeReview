from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.api.routes.snapshots import router as snapshots_router
from app.api.routes.sources import router as sources_router
from app.api.routes.tasks import router as tasks_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(projects_router, tags=["projects"])
api_router.include_router(tasks_router, tags=["verification-tasks"])
api_router.include_router(sources_router, tags=["sources"])
api_router.include_router(snapshots_router, tags=["snapshots"])
