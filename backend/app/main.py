from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.companies import router as companies_router
from app.api.drone import router as drone_router
from app.api.materials import router as materials_router
from app.api.monitoring import router as monitoring_router
from app.api.router import router
from app.api.signals import router as signals_router
from app.api.workspace import router as workspace_router
from app.application import create_application
from app.core.config import Settings


def create_app(settings: Settings | None = None):
    return create_application(
        settings if settings is not None else Settings(),
        [
            router,
            auth_router,
            workspace_router,
            companies_router,
            drone_router,
            analysis_router,
            monitoring_router,
            materials_router,
            signals_router,
        ],
        title="SAQ QURYLYS API",
    )


app = create_app()
