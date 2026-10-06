"""Operational API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Stable liveness response contract."""

    status: Literal["ok"]
    service: str
    version: str
    environment: str
    timestamp: datetime

