from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict

from app.core.config import Settings


class MarketLensSettings(Settings):
    model_config = SettingsConfigDict(
        env_prefix="MARKETLENS_", env_file="../.env.marketlens.local", extra="ignore"
    )

    firebase_project_id: str = Field(default="demo-marketlens-local", max_length=30)

    @field_validator("firebase_project_id")
    @classmethod
    def marketlens_project(cls, value: str) -> str:
        if not value.startswith(("marketlens-", "demo-marketlens-")):
            raise ValueError("Use a dedicated MarketLens Firebase project ID")
        return value
