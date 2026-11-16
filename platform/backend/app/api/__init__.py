from fastapi import APIRouter

from . import access, projects, research, tasks, systems, users

api_router = APIRouter(prefix="/api")
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(research.router)
api_router.include_router(systems.router)
api_router.include_router(access.router)
api_router.include_router(users.router)
