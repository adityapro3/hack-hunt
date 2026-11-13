from fastapi import FastAPI

from backend.api.routers.applications import router as applications_router
from backend.api.routers.auth import router as auth_router
from backend.api.routers.bookmarks import router as bookmarks_router
from backend.api.routers.coldemail import router as coldemail_router
from backend.api.routers.news import router as news_router
from backend.api.routers.opportunities import router as opportunities_router
from backend.api.routers.admin import router as scraper_router
from backend.api.routers.settings import router as settings_router

ALL_ROUTERS = (
    auth_router,
    opportunities_router,
    bookmarks_router,
    applications_router,
    news_router,
    coldemail_router,
    settings_router,
    scraper_router,
)


def register_routers(app: FastAPI) -> None:
    for router in ALL_ROUTERS:
        app.include_router(router)
