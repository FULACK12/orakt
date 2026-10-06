"""Public contracts for optional external-data credentials."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class IntegrationStatusView(BaseModel):
    """One provider's safe configuration state without exposing a secret."""

    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    status: Literal["ready", "credential_required"]
    credential_name: str | None
    configured: bool
    purpose_en: str
    purpose_zh: str
    documentation_url: str
    application_url: str


class IntegrationStatusResponse(BaseModel):
    """All credential-gated data providers prepared by the application."""

    model_config = ConfigDict(extra="forbid")

    integrations: list[IntegrationStatusView]
