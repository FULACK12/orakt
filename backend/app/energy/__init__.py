"""EIA bulk-data ingestion and energy time-series analysis."""

from app.energy.bulk import (
    EIABulkDatasetResult,
    EIABulkSyncResult,
    sync_eia_bulk,
)

__all__ = ["EIABulkDatasetResult", "EIABulkSyncResult", "sync_eia_bulk"]
