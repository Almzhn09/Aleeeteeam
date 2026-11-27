from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.application import create_application
from app.marketlens.api import router
from app.marketlens.settings import MarketLensSettings

health_router = APIRouter(prefix="/api/v1", tags=["health"])


@health_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "marketlens-api"}


def create_marketlens_app(settings: MarketLensSettings | None = None):
    return create_application(
        settings if settings is not None else MarketLensSettings(),
        [health_router, auth_router, router],
        title="MarketLens API",
    )
