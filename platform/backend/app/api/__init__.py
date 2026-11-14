from fastapi import APIRouter

from . import projects, research, tasks, systems

api_router = APIRouter(prefix="/api")
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(research.router)
api_router.include_router(systems.router)
