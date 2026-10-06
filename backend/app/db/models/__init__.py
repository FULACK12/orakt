"""Import all models so SQLAlchemy and Alembic receive complete metadata."""

from app.db.models.cluster_job import ClusterJob
from app.db.models.cluster_review_decision import ClusterReviewDecisionRecord
from app.db.models.company import (
    ChinaDisclosureSyncState,
    CompanyFiling,
    CompanyFinancialFact,
    CompanyInsiderFilingState,
    CompanyInsiderTransaction,
    CompanyInstitutionalHolding,
    CompanyProfile,
    CompanySupplyChainCoverage,
    CompanySupplyChainEdge,
    CompanySupplyChainSite,
    CompanySyncState,
    InstitutionalArchiveState,
)
from app.db.models.conflict import (
    ConflictAggregateObservation,
    ConflictAggregateSyncState,
    ConflictCountryIndicatorObservation,
)
from app.db.models.document import Document
from app.db.models.provenance import ProvenanceRecord
from app.db.models.document_analysis import DocumentAnalysis
from app.db.models.earnings_task import EarningsResearchTask
from app.db.models.economics import (
    CountryProfile,
    EconomicIndicator,
    EconomicObservation,
    EconomicSyncState,
)
from app.db.models.energy import EnergyObservation, EnergySeries, EnergySyncState
from app.db.models.entry_calibration import (
    EntryCalibrationRun,
    EntryHorizonForecast,
    EntryHorizonOutcome,
    EntryOutcomeEvaluation,
    EntryParameterCandidate,
    EntryParameterCandidateReview,
)
from app.db.models.event import Event, EventDocument
from app.db.models.factor_experiment import FactorExperiment, FactorExperimentOutcome
from app.db.models.feed import RSSFeed
from app.db.models.filing_timing import FilingTimingObservation
from app.db.models.gdelt_history import GdeltArchiveState, GdeltEventAggregate
from app.db.models.geography import (
    AdministrativeArea,
    EventRelationCandidate,
    RegionalIndicator,
    RegionalObservation,
)
from app.db.models.logic_chain import LogicChainHypothesis, LogicChainReviewSignal
from app.db.models.market import (
    MarketAssetIdentifier,
    MarketAssetLifecycle,
    MarketDailyBar,
    MarketDelistingEvidenceCandidate,
    MarketDelistingEvidenceState,
    MarketDelistingOutcome,
    MarketLifecycleResolution,
    MarketObservation,
    MarketPriceBackfillState,
    MarketSeries,
    MarketSyncState,
    MarketTerminalCashflow,
)
from app.db.models.research import (
    ResearchBatch,
    ResearchBatchItem,
    ResearchInquiry,
    ResearchReportAuditJob,
    ResearchReviewSignal,
)
from app.db.models.source import Source
from app.db.models.task_control import TaskControlRecord
from app.db.models.training_example import ExternalTrainingExample

__all__ = [
    "ProvenanceRecord",
    "FilingTimingObservation",
    "EarningsResearchTask",
    "AdministrativeArea",
    "ChinaDisclosureSyncState",
    "ClusterJob",
    "ClusterReviewDecisionRecord",
    "CompanyFiling",
    "CompanyFinancialFact",
    "CompanyInsiderFilingState",
    "CompanyInsiderTransaction",
    "CompanyInstitutionalHolding",
    "CompanyProfile",
    "CompanySupplyChainCoverage",
    "CompanySupplyChainEdge",
    "CompanySupplyChainSite",
    "CompanySyncState",
    "ConflictAggregateObservation",
    "ConflictAggregateSyncState",
    "ConflictCountryIndicatorObservation",
    "CountryProfile",
    "Document",
    "DocumentAnalysis",
    "EconomicIndicator",
    "EconomicObservation",
    "EconomicSyncState",
    "EnergyObservation",
    "EnergySeries",
    "EnergySyncState",
    "EntryCalibrationRun",
    "EntryHorizonForecast",
    "EntryHorizonOutcome",
    "EntryOutcomeEvaluation",
    "EntryParameterCandidate",
    "EntryParameterCandidateReview",
    "Event",
    "EventDocument",
    "EventRelationCandidate",
    "ExternalTrainingExample",
    "FactorExperiment",
    "FactorExperimentOutcome",
    "GdeltArchiveState",
    "GdeltEventAggregate",
    "InstitutionalArchiveState",
    "LogicChainHypothesis",
    "LogicChainReviewSignal",
    "MarketAssetIdentifier",
    "MarketAssetLifecycle",
    "MarketDailyBar",
    "MarketDelistingEvidenceCandidate",
    "MarketDelistingEvidenceState",
    "MarketDelistingOutcome",
    "MarketLifecycleResolution",
    "MarketObservation",
    "MarketPriceBackfillState",
    "MarketSeries",
    "MarketSyncState",
    "MarketTerminalCashflow",
    "RSSFeed",
    "RegionalIndicator",
    "RegionalObservation",
    "ResearchBatch",
    "ResearchBatchItem",
    "ResearchInquiry",
    "ResearchReportAuditJob",
    "ResearchReviewSignal",
    "Source",
    "TaskControlRecord",
]
