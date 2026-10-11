"use client";
import useDisplayLanguage from "./useDisplayLanguage";
import useWorkspaceChrome from './useWorkspaceChrome';
import {reportForReading} from './report-reading.mjs';
import {ReadingText} from './ReadingReferences';
import useWatchlist from './useWatchlist';
import {isCompanyReport,reportHref} from './report-taxonomy.mjs';
import CompanyReportCoverage from './CompanyReportCoverage';
import {economicValue, metricCount, finiteNumber, reportFilterDate, reportDisplayDate} from "./metric-format.mjs";
import CompanyDossier from "./CompanyDossier";
import ReportEvidence from './ReportEvidence';
import PeerFactorStudy from "./PeerFactorStudy";
import ResearchCompletion from "./ResearchCompletion";
import FinancialPeriodLedger from "./FinancialPeriodLedger";
import ReportMarketCoverage from "./ReportMarketCoverage";
import DataLibrary from "./DataLibrary";
import MarketsWorkspace from "./MarketsWorkspace";
import MapChains from './MapChains';
import AppleMapInspector from './AppleMapInspector';
import useResearchData from './useResearchData';
import MacroEventReports from "./MacroEventReports";
import DisclosureReviews from "./DisclosureReviews";
import IntelligenceMarket from "./platform/intelligence/IntelligenceMarket";
import {localizeReport} from "./report-language.mjs";

import {
  Moon,
  Sun,
  Activity,
  Anchor,
  ArrowRight,
  BrainCircuit,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  Database,
  ExternalLink,
  FileSearch,
  Languages,
  Layers3,
  ListFilter,
  LoaderCircle,
  LockKeyhole,
  MapPin,
  Newspaper,
  Pause,
  Play,
  Factory,
  Radio,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import type { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import mapWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import Link from "next/link";
import OraktBrandIcon from "./OraktBrandIcon";
import MarketExpansion from "./MarketExpansion";
import ReleaseStatus from "./ReleaseStatus";
import ReportCatalogPreview from "./ReportCatalogPreview";
import {
  type ReactNode,
  type UIEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
  lazy,
  Suspense,
} from "react";
const SemiconductorComparisonPanel=lazy(()=>import('./SemiconductorComparisonPanel'));
const CompanyFinancialCharts=lazy(()=>import('./CompanyFinancialCharts'));
const EvidenceChains=lazy(()=>import('./EvidenceChains'));
const PortfolioLab=lazy(()=>import('./PortfolioLab'));
const AlphaLab=lazy(()=>import('./AlphaLab'));
const PersonalResearch=lazy(()=>import('./PersonalResearch'));
const AssetIntelligence=lazy(()=>import('./AssetIntelligence'));
const HormuzMapInspector=lazy(()=>import('./HormuzMapInspector'));

type Language = "zh" | "en";
type Tab = "map" | "evidence" | "sec" | "data" | "portfolio" | "intelligence" | "assets" | "markets" | "alpha" | "chains" | "personal";
type WindowKey = "7d" | "30d" | "90d" | "all";
type MobilePanel = "layers" | "events" | "detail" | null;
type AnalysisMode = "news_first" | "hypothesis_first";
type ReportMarket = "all" | "us" | "china" | "global";
type EvidenceView = "single" | "cross" | "entry" | "portfolio" | "crypto" | "operations";
type MapLibreModule = typeof import("maplibre-gl");
type MapLoadState = "idle" | "loading" | "ready" | "error";
type ClientLoadMetric = {
  status: "ready" | "error";
  durationMs: number;
  bytes?: number;
  records?: number;
  observedAt: string;
  detail?: string;
};
type EventItem = {
  id: string;
  title: string;
  location: string;
  summary: string;
  country: string;
  date: string;
  endDate?: string;
  severity: number;
  confidence: number;
  coordinates: [number, number];
  source: string;
  eventType: string;
  eventCount: number;
};
type EconomicObservation = {
  country: string;
  iso2: string;
  date: string;
  value: number;
  unit: string;
  indicator: string;
  coordinates: [number, number];
};
type SupplyChainSite = {
  siteId: number;
  contextTicker: string;
  contextTickers: string[];
  facilityRole: "company_facility" | "upstream_supplier_location";
  subjectTicker: string;
  relatedCompanyName: string;
  relatedTicker: string;
  siteKind: string;
  siteName: string;
  countryName: string;
  countryIso2: string;
  admin1Name: string;
  coordinates: [number, number];
  coordinatePrecision: string;
  verificationStatus: string;
  associationScope: string;
  sourceUrl: string;
  sourceExcerpt: string;
  availableAt: string;
  conflictEvents: number;
  conflictFatalities: number;
  disasterEventCount: number;
  powerSignalCount: number;
  nearestPort: { name?: string; distance_km?: number } | null;
  portRouteStatus: string;
  exposureAttentionScore: number;
  periodStart: string;
  periodEnd: string;
};
type SupplyChainSnapshot = {
  generatedAt: string;
  asOf: string;
  weeks: number;
  summaries: Array<{
    ticker: string;
    siteCount: number;
    returnedSiteCount: number;
    geocodedSiteCount: number;
    exactFacilityCount: number;
    companyFacilityCount: number;
    supplierLocationCount: number;
    conflictExposedCount: number;
    disasterExposedCount: number;
    powerSignalCount: number;
    truncated: boolean;
  }>;
  sites: SupplyChainSite[];
  methodology: string;
};
type MapListItem =
  | { kind: "event"; item: EventItem }
  | { kind: "supply"; item: SupplyChainSite };
type ChainStep = {
  title: string;
  claim: string;
  status: "verified" | "partial" | "missing";
  confidence: number;
  evidenceCount: number;
};
type EvidenceItem = {
  title: string;
  publisher: string;
  url: string;
  observedAt: string;
  claim: string;
  supports: "support" | "contradict" | "context";
  reliability: number | null;
};
type NewsReport = {
  headline: string;
  narrative: string;
  facts: string[];
  uncertainties: string[];
  documentsReviewed: number;
  fullContentReviewed: number;
  headlineOnlyExcluded: number;
};
type LocalReportAudit = {
  version: string;
  status: string;
  recommendation: string;
  openaiUsed: boolean;
  citedReferences: number;
  missingReferences: number;
  headlineOnlyReferences: number;
  futureDatedReferences: number;
  foreignSubjects: number;
  repairsApplied: number;
};
type DataReadiness = {
  version: string;
  score: number;
  status: string;
  directionalConclusionAllowed: boolean;
  confidenceCap: number;
  missingRequired: string[];
  policyZh: string;
  policyEn: string;
  components: Array<{
    key: string;
    labelZh: string;
    labelEn: string;
    weight: number;
    score: number;
    status: string;
    detailZh: string;
    detailEn: string;
  }>;
};
type ConfidenceDetail = {
  scoreKind: string;
  formula: string;
  rawChainScore: number;
  dataReadinessCap: number;
  dataReadinessScore: number | null;
  verifiedSteps: number;
  partiallySupportedSteps: number;
  unresolvedSteps: number;
  validatedAlphaSupported: boolean;
  blockersZh: string[];
  blockersEn: string[];
};
type DisclosureCoverage = {
  status: string;
  periodStart: string;
  periodEnd: string;
  periodicReports: number;
  shareholderDocuments: number;
  operatingDocuments: number;
  supplyChainDocuments: number;
  structuredStatus: string;
  financialMetrics: number;
  shareholderExcerpts: number;
  operatingExcerpts: number;
  supplyChainExcerpts: number;
};
type EntryWatchCandidate = {
  report: ReportIndexItem;
  ticker: string;
  company: string;
  marketRegion: "us" | "china";
  observedOn: string;
  currentPrice: number;
  zoneLower: number;
  zoneUpper: number;
  stopReference: number;
  targetReference: number;
  rewardRiskRatio: number;
  downsideFraction: number;
  upsideFraction: number;
  distanceToSupport: number;
  evidenceScore: number;
  rankingScore: number;
};
type TechnicalChartPoint = {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number | null;
  sma20: number | null;
  sma50: number | null;
};
type EntryHorizonValidation = {
  type: string;
  startDate: string | null;
  endDate: string | null;
  trainEndDate: string | null;
  trainObservations: number;
  testObservations: number;
  testSignals: number;
  transactionCostBps: number;
  meanStrategyReturn: number | null;
  meanBaselineReturn: number | null;
  excessMeanReturn: number | null;
  hitRate: number | null;
  evaluationStrideSessions: number;
  overlappingForwardWindows: boolean;
  status: string;
  leakageGuard: string;
  limitations: string[];
};
type EntryHorizonModel = {
  key: "ultra_short" | "swing" | "medium" | "long_value";
  labelZh: string;
  labelEn: string;
  horizonSessions: number;
  status: string;
  currentSignal: {
    triggered: boolean;
    score: number | null;
    components: Array<{ key: string; passed: boolean }>;
  };
  entryZone: { lower: number | null; upper: number | null };
  stopReference: number | null;
  targetReference: number | null;
  expectedMove: number | null;
  downsideFraction: number | null;
  upsideFraction: number | null;
  rewardRiskRatio: number | null;
  fundamentalGate: {
    required: boolean;
    passed: boolean;
    explanation: string;
  };
  parameters: Record<string, string | number | boolean>;
  validation: EntryHorizonValidation;
  reportReplay: {
    status: string;
    triggered: boolean;
    maturesAfterSessions?: number;
    availableFutureSessions?: number;
    entryDate?: string;
    exitDate?: string;
    entryClose?: number;
    exitClose?: number;
    netReturn?: number;
    targetTouchedByClose?: boolean;
    stopTouchedByClose?: boolean;
  };
};
type TradingScenario = {
  ticker: string;
  observedOn: string;
  entryPrice: number | null;
  stopReference: number | null;
  stopBasis: string;
  targetReference: number | null;
  targetBasis: string;
  downsideFraction: number | null;
  upsideFraction: number | null;
  rewardRiskRatio: number | null;
  barDataStatus: string;
  atr14: number | null;
  volumeRatio20: number | null;
  volumeStatus: string;
  support: { label: string; value: number | null };
  resistance: { label: string; value: number | null };
  oneWeekBand: {
    lower: number | null;
    upper: number | null;
    expectedMove: number | null;
  };
  twoWeekBand: {
    lower: number | null;
    upper: number | null;
    expectedMove: number | null;
  };
  averages: {
    sma20: number | null;
    sma50: number | null;
    sma200: number | null;
  };
  chart: TechnicalChartPoint[];
  institutional: {
    actualAverageCostAvailable: false;
    actualAverageCostStatus: string;
    reportPeriod: string;
    quarterEndValuePerShareProxy: number | null;
    proxyScope: string;
    topManagers: Array<{
      name: string;
      reportedShares: number | null;
      reportedShareChange: number | null;
      quarterEndValuePerShareProxy: number | null;
    }>;
    explanation: string;
  };
  horizonModels?: {
    version: string;
    parameterPolicy: string;
    pointInTimePolicy: string;
    models: EntryHorizonModel[];
  };
  methodNote: string;
};
type EntryBacktestStatus = {
  generatedAt: string;
  modelVersion: string;
  status: string;
  ledgerMode?: string;
  ledgerRunId?: number;
  lastSettlementAt?: string | null;
  forecastsTotal?: number;
  outcomesSettled?: number;
  pendingForecasts?: number;
  forecastsCreatedThisRun?: number;
  outcomesSettledThisRun?: number;
  evaluationsCreatedThisRun?: number;
  dailyCompanyUniverse?: number;
  dailyCompanySnapshotsCreated?: number;
  dailyCompanySnapshotsCovered?: number;
  dailyCompanyInsufficientHistory?: number;
  dailyCompanySnapshotGpuUsed?: boolean;
  evaluationVersion?: string;
  benchmarkPolicy?: {
    us?: string;
    china?: string;
    usSector?: string;
    chinaSector?: string;
  };
  archiveStatus?: string;
  productionModelChanged?: boolean;
  parameterUpgradePolicy: string;
  historicalReportsEvaluated: number;
  candidateReview?: Array<{
    horizonKey: string;
    status: string;
    candidateVersion?: string;
    sampleFingerprint?: string;
    maturedSamples: number;
    rawMaturedBaseSignals?: number;
    maturedBaseSignals: number;
    minimumSignals: number;
    progress: number;
    trainSamples?: number;
    testSamples?: number;
    chosenThreshold?: number;
    baseThreshold?: number;
    baseTest?: {
      rawSignals?: number;
      signals: number;
      meanNetReturn: number | null;
      meanNetReturnConfidenceInterval95?: [number | null, number | null];
      hitRate: number | null;
      hitRateConfidenceInterval95?: [number | null, number | null];
      worstNetReturn: number | null;
      meanExcessReturn: number | null;
      meanExcessReturnConfidenceInterval95?: [number | null, number | null];
      benchmarkOutperformanceRate: number | null;
      benchmarkCoverageRate: number;
      meanSectorExcessReturn?: number | null;
      meanSectorExcessConfidenceInterval95?: [number | null, number | null];
      sectorOutperformanceRate?: number | null;
      sectorBenchmarkCoverageRate?: number;
      worstAdverseExcursion: number | null;
      bestFavorableExcursion: number | null;
      forecastSequenceMaxDrawdown: number | null;
      regimes: Record<
        string,
        {
          signals: number;
          meanNetReturn: number | null;
          hitRate: number | null;
          meanExcessReturn: number | null;
        }
      >;
    };
    candidateTest?: {
      rawSignals?: number;
      signals: number;
      meanNetReturn: number | null;
      meanNetReturnConfidenceInterval95?: [number | null, number | null];
      hitRate: number | null;
      hitRateConfidenceInterval95?: [number | null, number | null];
      worstNetReturn: number | null;
      meanExcessReturn: number | null;
      meanExcessReturnConfidenceInterval95?: [number | null, number | null];
      benchmarkOutperformanceRate: number | null;
      benchmarkCoverageRate: number;
      meanSectorExcessReturn?: number | null;
      meanSectorExcessConfidenceInterval95?: [number | null, number | null];
      sectorOutperformanceRate?: number | null;
      sectorBenchmarkCoverageRate?: number;
      worstAdverseExcursion: number | null;
      bestFavorableExcursion: number | null;
      forecastSequenceMaxDrawdown: number | null;
      regimes: Record<
        string,
        {
          signals: number;
          meanNetReturn: number | null;
          hitRate: number | null;
          meanExcessReturn: number | null;
        }
      >;
    };
    humanReviewRequired?: boolean;
    productionModelChanged?: boolean;
  }>;
  horizons: Array<{
    key: string;
    labelZh: string;
    labelEn: string;
    reports: number;
    matured: number;
    pending: number;
    maturedSignals: number;
    rawMaturedSignals?: number;
    positiveSignals: number;
    hitRate: number | null;
    hitRateConfidenceInterval95?: [number | null, number | null];
    meanNetReturn: number | null;
    meanNetReturnConfidenceInterval95?: [number | null, number | null];
    benchmarkEvaluatedSignals?: number;
    benchmarkCoverageRate?: number | null;
    meanExcessReturn?: number | null;
    meanExcessReturnConfidenceInterval95?: [number | null, number | null];
    benchmarkOutperformanceRate?: number | null;
    sectorBenchmarkEvaluatedSignals?: number;
    sectorBenchmarkCoverageRate?: number | null;
    meanSectorExcessReturn?: number | null;
    meanSectorExcessConfidenceInterval95?: [number | null, number | null];
    sectorOutperformanceRate?: number | null;
    marketRegimes?: Record<string, number>;
    minimumSignalsForUpgradeReview: number;
    upgradeEligible: boolean;
    candidateStatus?: string;
    productionModelChanged?: boolean;
  }>;
  limitations: string[];
};
type CanslimCriterion = {
  code: string;
  labelZh: string;
  labelEn: string;
  weight: number;
  status: "pass" | "partial" | "fail" | "missing";
  score: number;
  observed: string;
  threshold: string;
  evidenceCount: number;
  limitations: string[];
};
type CanslimScorecard = {
  version: string;
  ticker: string;
  asOf: string;
  overallScore: number;
  coverageScore: number;
  decision: string;
  criteria: CanslimCriterion[];
  discipline: {
    status: string;
    pivotProxy: number | null;
    buyZoneLower: number | null;
    buyZoneUpper: number | null;
    currentPrice: number | null;
    currentPosition: string;
    stopLossRule: string;
    profitRule: string;
  };
  limitations: string[];
};
type CompetitorPeriodMetrics = {
  periodEnd: string;
  comparisonPeriodEnd: string;
  availableAt: string;
  revenueYoy: number | null;
  grossMargin: number | null;
  netMargin: number | null;
  researchIntensity: number | null;
  inventoryYoy: number | null;
  ranks: Record<string, number | null>;
  qualityFlags: string[];
};
type CompetitorOperatingComparison = {
  ticker: string;
  asOf: string;
  peerGroup: string[];
  rows: Array<{
    ticker: string;
    company: string;
    periodEnd: string;
    availableAt: string;
    revenueYoy: number | null;
    grossMargin: number | null;
    netMargin: number | null;
    researchIntensity: number | null;
    inventoryYoy: number | null;
    ranks: Record<string, number | null>;
    qualityFlags: string[];
    quarterly: CompetitorPeriodMetrics | null;
  }>;
  productDisclosures: Array<{
    ticker: string;
    metricType: string;
    metricName: string;
    product: string;
    reportedValues: string[];
    periodEnd: string;
    availableAt: string;
    filingForm: string;
    sourceExcerpt: string;
    sourceUrl: string;
  }>;
  comparableProductMetricTypes: string[];
  limitations: string[];
};
type EvidenceReport = {
  peerStudy?: any;
  dossier?: any;
  financialSupplement?: any;
  researchCompletion?: any;
  translations?: {en?:any};
  historical?: {asOf:string;periodEnd:string;reviewer:string;corrections:string[];eligibleForPredictiveBacktest:boolean};
  id: string;
  origin?: "local_ollama" | "remote_openai";
  localInquiryId?: number;
  marketRegion?: "us" | "china" | "global";
  ticker?: string;
  companyName?: string;
  sector?: string;
  analysisMode: AnalysisMode;
  question: string;
  thesis: string;
  questionEn?: string;
  verdict: string;
  confidence: number | null;
  confidenceDetail?: ConfidenceDetail | null;
  createdAt: string;
  updatedAt?: string;
  syncedAt?: string;
  model: string;
  dataCutoff?: string;
  audit?: LocalReportAudit;
  dataReadiness?: DataReadiness | null;
  disclosureCoverage?: DisclosureCoverage | null;
  newsReport: NewsReport;
  chain: ChainStep[];
  evidence: EvidenceItem[];
  alternatives: string[];
  limitations: string[];
  nextData: string[];
  scores: Array<{ label: string; score: number; weight: number }>;
  tradingScenario?: TradingScenario | null;
  canslim?: CanslimScorecard | null;
  competitorComparison?: CompetitorOperatingComparison | null;
};
type ReportIndexItem = Pick<
  EvidenceReport,
  | "id"
  | "localInquiryId"
  | "marketRegion"
  | "ticker"
  | "companyName"
  | "sector"
  | "analysisMode"
  | "question"
  | "questionEn"
  | "model"
  | "confidence"
  | "createdAt"
  | "updatedAt"
  | "historical"
  | "dataCutoff"
> & {
  audit?: Pick<
    LocalReportAudit,
    | "status"
    | "missingReferences"
    | "headlineOnlyReferences"
    | "futureDatedReferences"
    | "foreignSubjects"
  > | null;
  dataReadiness?: Pick<
    DataReadiness,
    "score" | "directionalConclusionAllowed"
  > | null;
  disclosureCoverage?: Pick<
    DisclosureCoverage,
    "status" | "financialMetrics"
  > | null;
  tradingScenario?: Pick<
    TradingScenario,
    | "ticker"
    | "observedOn"
    | "entryPrice"
    | "support"
    | "stopReference"
    | "targetReference"
    | "rewardRiskRatio"
    | "downsideFraction"
    | "upsideFraction"
    | "atr14"
    | "chart"
  > | null;
  hasCompetitorComparison: boolean;
};
type ResearchReportIndexSnapshot = {
  generatedAt: string;
  total: number;
  detailEndpoint: string;
  reports: ReportIndexItem[];
};
type EquityCatalogItem = {
  marketRegion: "us" | "china";
  ticker: string;
  companyName: string;
  sector: string | null;
  industry: string | null;
  dataStart: string | null;
  dataEnd: string | null;
  observationCount: number;
  leaderScore: number | null;
  scoreObservedOn: string | null;
  reportIds: string[];
};
type ReportGeneration = {
  targetCount: number;
  completedCount: number;
  failedCount: number;
  queuedCount: number;
  runningCount: number;
  triggeredTargets?: number;
  dailyPolicy?: {
    rotationBudget: number;
    eventBudget: number;
    gpuConcurrency: number;
    snapshotGpuUsed: boolean;
    triggerPolicy: string;
  };
  batches: Array<{
    id: number;
    name: string;
    status: string;
    targetCount: number;
    completedCount: number;
    failedCount: number;
    queuedCount: number;
    runningCount: number;
    runningTicker: string | null;
    progressPercent: number;
    progressStage: string | null;
    progressMessage: string | null;
    createdAt: string;
    completedAt: string | null;
    rotationBudget?: number;
    eventBudget?: number;
    triggeredTargets?: number;
    triggerReasons?: Record<
      string,
      Array<{
        kind: string;
        label: string;
        value?: number;
        asOf?: string;
        severity: number;
      }>
    >;
  }>;
};
type EquityReportCatalog = {
  generatedAt: string;
  universe: string;
  methodology: string;
  generation?: ReportGeneration;
  companies: EquityCatalogItem[];
};
type SnapshotManifest = {
  generatedAt: string;
  snapshotMode?: "published_static_snapshot";
  aiPipeline?: {
    clusterExtraction?: {
      jobId: number;
      status: string;
      totalDocuments: number;
      processedDocuments: number;
      progressPercent: number;
      localModelDocuments: number;
      directModelDocuments?: number;
      repairedDocuments?: number;
      fallbackDocuments: number;
      pendingDocuments: number;
      localModel: string | null;
      waitReason: string | null;
      fallbackRate: number;
      batchSize: number;
      startedAt: string | null;
      completedAt: string | null;
      updatedAt: string;
      scope: string;
    } | null;
    reportGeneration?: {
      completedReports: number;
      detailAssets: number;
      auditableOnSite: boolean;
      source: string;
    };
  };
  localTotals: {
    geolocatedEvents: number;
    acledAggregateRows: number;
    acledRepresentedEvents: number;
    rssDocuments: number;
    substantiveArticles: number;
    headlineOnlyDiscovery: number;
  };
  remoteSnapshot: {
    conflictRecords: number;
    ucdpRecords: number;
    newsIndexRecords: number;
    contentReadyArticles: number;
    secEvidenceCandidates: number;
    localResearchReports?: number;
    localResearchAuditVersion?: string;
    activeChinaSectorLeaders?: number;
    activeChinaSectors?: number;
    supplyChainSites?: number;
    supplyChainExactFacilities?: number;
    supplyChainTickers?: number;
    conflictStartsAt: string;
    conflictEndsAt: string;
    newsStartsAt: string;
    newsEndsAt: string;
  };
  sourceBoundaries: {
    localConflictStartsAt: string;
    localConflictEndsAt: string;
  };
  evidencePolicy: {
    headlineOnlyExcluded: number;
    minimumBodyCharacters: number;
    note: string;
  };
};
type SecEvidenceCandidate = {
  evidenceKey: string;
  assetKey: string;
  symbol: string;
  name: string;
  delistingDate: string;
  secCik: string | null;
  identityStatus: string;
  outcomeStatus: string;
  factorEligible: boolean;
  factorBlockReason: string | null;
  form: string;
  filedOn: string;
  sourceUrl: string;
  evidenceType: string;
  candidateValue: number | null;
  valueUnit: string | null;
  excerpt: string | null;
  confidence: number;
  reviewStatus: string;
  reviewNote: string | null;
  reviewedAt: string | null;
};
type SecEvidenceSnapshot = {
  generatedAt: string;
  source: string;
  metrics: {
    assetsSearched: number;
    candidateFilings: number;
    valueCandidates: number;
    pendingReview: number;
    lifecycleConflicts: number;
  };
  candidates: SecEvidenceCandidate[];
};
type SemiconductorCompany = {
  ticker: string;
  name: string;
  industry: string;
  dataCoverageScore: number;
  dataStatus: string;
  missing: string[];
  market: {
    historyStart: string;
    historyEnd: string;
    barCount: number;
    completeOhlcv: boolean;
    latestClose: number | null;
    return21d: number | null;
    return63d: number | null;
    return252d: number | null;
    annualizedVolatility63d: number | null;
    maximumDrawdown252d: number | null;
    sma20: number | null;
    sma50: number | null;
    sma200: number | null;
    volumeRatio20: number | null;
  };
  fundamentals: {
    periodEnd: string | null;
    revenue: number | null;
    netIncome: number | null;
    researchAndDevelopment: number | null;
    netMargin: number | null;
    researchIntensity: number | null;
    marketCapitalizationProxy: number | null;
    priceToSalesProxy: number | null;
    priceToEarningsProxy: number | null;
    debtToEquity: number | null;
    sourceUrl: string;
  };
  evidence: {
    filingCount: number;
    institutionalObservationCount: number;
    insiderTransactionCount: number;
    verifiedSupplyChainEdges: number;
    unnamedVerifiedSupplyChainEdges: number;
    candidateSupplyChainEdges: number;
  };
};
type SemiconductorComparison = {
  version: string;
  generatedAt: string;
  marketDataCutoff: string;
  titleZh: string;
  titleEn: string;
  verdictZh: string;
  verdictEn: string;
  openaiUsed: boolean;
  companies: SemiconductorCompany[];
  findings: Array<{
    key: string;
    ticker: string | null;
    labelZh: string;
    labelEn: string;
    value: number | null;
    caveatZh: string;
    caveatEn: string;
  }>;
  methodologyZh: string;
  methodologyEn: string;
};

const snapshotIso = "2026-08-14T20:13:25Z";
const fallbackStartIso = "2025-01-01T00:00:00Z";
const fallbackEndIso = "2026-06-30T00:00:00Z";
const dayMs = 86_400_000;
const fallbackEvents: EventItem[] = [
  {
    id: "u744",
    title: "Government of Israel — Hamas",
    location: "Gaza Strip",
    summary:
      "UCDP state-based conflict record; reported fatality estimate: 18.",
    country: "IL",
    date: "2026-06-30",
    severity: 57,
    confidence: 79,
    coordinates: [34.373398, 31.425074],
    source: "UCDP GED 26.1",
    eventType: "state_based_conflict",
    eventCount: 1,
  },
  {
    id: "u723",
    title: "Jalisco New Generation — Sinaloa",
    location: "Tijuana municipality",
    summary: "UCDP non-state conflict record; reported fatality estimate: 1.",
    country: "MX",
    date: "2026-06-30",
    severity: 33,
    confidence: 90,
    coordinates: [-116.97212, 32.50223],
    source: "UCDP GED 26.1",
    eventType: "non_state_conflict",
    eventCount: 1,
  },
  {
    id: "u676",
    title: "Government of Russia — Government of Ukraine",
    location: "Pokrovsk",
    summary: "UCDP state-based conflict record; reported fatality range: 2–38.",
    country: "UA",
    date: "2026-06-30",
    severity: 37,
    confidence: 94,
    coordinates: [37.177579, 48.279112],
    source: "UCDP GED 26.1",
    eventType: "state_based_conflict",
    eventCount: 1,
  },
];

const economicIndicators = [
  { code: "FP.CPI.TOTL.ZG", zh: "通胀率（CPI）", en: "Inflation (CPI)" },
  { code: "NY.GDP.MKTP.KD.ZG", zh: "GDP 实际增速", en: "Real GDP growth" },
  { code: "SL.UEM.TOTL.ZS", zh: "失业率", en: "Unemployment" },
  { code: "NY.GDP.MKTP.CD", zh: "GDP 总量", en: "GDP" },
  { code: "NV.IND.TOTL.ZS", zh: "工业增加值占比", en: "Industry value added" },
  {
    code: "NV.AGR.TOTL.ZS",
    zh: "农业增加值占比",
    en: "Agriculture value added",
  },
];

const defaultReport: EvidenceReport = {
  id: "sample-news-first-fomc",
  analysisMode: "news_first",
  question: "美联储偏鹰表态是否通过美债收益率影响科技股估值？",
  thesis:
    "先核对报道与原始公告，再检查市场传导。当前可验证政策表态、收益率与科技股价格在时间上同向变化，但市场预期变化只得到部分支持，因此不应把同期下跌完全归因于美联储。",
  verdict: "流程样例 · 修改后接受",
  confidence: 63,
  createdAt: snapshotIso,
  model: "新闻优先验证样例",
  newsReport: {
    headline: "政策报道与市场反应在时间上相邻，但中间预期机制仍需补证",
    narrative:
      "系统先阅读并对照 FOMC 原文、美国财政部收益率数据和 Nasdaq 结果数据，再把已报道事实与分析推断分开。只有完成这一新闻理解步骤后，才进入下方因果链。",
    facts: [
      "FOMC 发布了政策决定与会后沟通",
      "事件日前后美国国债收益率发生变化",
      "科技股指数同期出现价格反应",
    ],
    uncertainties: ["市场在决议前已计价多少", "同期企业财报和地缘风险的贡献"],
    documentsReviewed: 3,
    fullContentReviewed: 3,
    headlineOnlyExcluded: 0,
  },
  chain: [
    {
      title: "政策事件",
      claim: "FOMC 声明及发布会语气相对偏鹰",
      status: "verified",
      confidence: 88,
      evidenceCount: 2,
    },
    {
      title: "预期重定价",
      claim: "市场提高更长期维持高利率的概率",
      status: "partial",
      confidence: 54,
      evidenceCount: 1,
    },
    {
      title: "利率传导",
      claim: "2Y/10Y 美债收益率上升，提高折现率",
      status: "verified",
      confidence: 82,
      evidenceCount: 3,
    },
    {
      title: "估值反应",
      claim: "久期更长的科技股估值承压",
      status: "partial",
      confidence: 67,
      evidenceCount: 2,
    },
  ],
  evidence: [
    {
      title: "FOMC calendars and information",
      publisher: "Federal Reserve",
      url: "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
      observedAt: "事件日",
      claim: "核对政策决定、声明与发布会原文",
      supports: "support",
      reliability: 96,
    },
    {
      title: "Daily Treasury par yield curve rates",
      publisher: "U.S. Treasury",
      url: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates",
      observedAt: "事件日前后",
      claim: "核对 2 年期和 10 年期收益率变化",
      supports: "support",
      reliability: 95,
    },
    {
      title: "NASDAQ Composite",
      publisher: "FRED",
      url: "https://fred.stlouisfed.org/series/NASDAQCOM",
      observedAt: "事件日前后",
      claim: "核对科技股指数价格结果",
      supports: "context",
      reliability: 91,
    },
  ],
  alternatives: [
    "企业财报与盈利预期变化",
    "大型科技公司监管或行业消息",
    "地缘政治导致的风险偏好变化",
  ],
  limitations: [
    "缺少可公开复核的利率期货概率变化",
    "尚未完成行业和个股层面的横截面对照",
    "时间相关性不能单独证明因果关系",
  ],
  nextData: [
    "事件前后 30 分钟的 2Y/10Y 收益率",
    "利率期货隐含路径",
    "Nasdaq 与非科技行业的相对表现",
  ],
  scores: [
    { label: "时间一致性", score: 82, weight: 20 },
    { label: "机制完整度", score: 58, weight: 25 },
    { label: "证据覆盖率", score: 66, weight: 25 },
    { label: "替代解释检验", score: 41, weight: 20 },
    { label: "历史相似度", score: 64, weight: 10 },
  ],
};
void defaultReport;

const copy = {
  zh: {
    beta: "ORAKT 研究平台",
    snapshot: "数据版本日期",
    tabs: {
      map: "事件地图",
      evidence: "AI 证据报告",
      sec: "SEC 审核",
      data: "数据状态",
    },
    search: "搜索国家、地点或事件",
    filters: "观察窗口",
    windows: { "7d": "7天", "30d": "30天", "90d": "90天", all: "全部" },
    conflict: "战争与冲突",
    layers: "地图指标",
    events: "事件",
    detail: "详情",
    showConflict: "战争与冲突点位",
    colorSeverity: "按冲突严重度着色",
    economy: "国家经济指标",
    economyHelp: "来自 World Bank 的最新可用年度值；点位为国家首都参考位置。",
    loadingEconomy: "正在读取经济数据…",
    supplyChain: "供应链设施",
    showSupplyChain: "供应商工厂与制造区域",
    supplyHelp:
      "默认关闭。精确工厂与省州/城市参考点分开显示；邻近冲突或港口不等于已经发生供应中断。",
    loadingSupply: "正在读取已发布供应链数据…",
    exactFacility: "精确工厂",
    regionalReference: "区域参考点",
    facilityRole: "地点角色",
    companyFacility: "公司自有设施",
    upstreamSupplierLocation: "上游供应商地点",
    supplier: "关联供应商",
    exposureWindow: "风险观察窗口",
    nearbyConflict: "邻近冲突",
    nearbyDisaster: "邻近灾害",
    powerSignals: "电力信号",
    nearestPort: "最近港口参考",
    layerHelp:
      "指标只有开启后才显示，并受回放日期和观察窗口控制。缩小时自动聚合，避免手机卡顿。",
    close: "关闭面板",
    eventCount: "个可见记录",
    selected: "事件核对",
    severity: "严重度",
    confidence: "来源置信度",
    source: "来源",
    noEvents: "当前回放时间内没有事件或设施",
    replay: "事件回放",
    play: "开始回放",
    pause: "暂停回放",
    loadingData: "正在载入已发布冲突数据…",
    showing: "列表显示前 200 条，地图显示全部筛选结果",
    readonly: "已发布数据，非实时更新；仅标题新闻不会被当作直接证据。",
    finalConfidence: "综合置信度",
    researchPlaceholder: "输入需要分析的经济、市场或国际事件问题",
    researchAction: "生成并核验报告",
    researching: "AI 正在阅读全文、生成报告并核验证据…",
    executive: "执行摘要",
    chainTitle: "因果传导图",
    evidenceLedger: "证据登记表",
    scoreTitle: "置信度组成",
    alternatives: "替代解释",
    limitations: "限制与反证",
    nextData: "建议补充数据",
    verified: "已验证",
    partial: "部分支持",
    missing: "证据不足",
    reviewer: "人工审核",
    reviewerHelp: "反馈会作为后续提示词、规则与已验证逻辑链的改进信号保存。",
    commentPlaceholder: "补充证据、指出错误步骤或写出修改后的因果关系…",
    saveFeedback: "保存审核反馈",
    saved: "反馈已保存",
    reportError: "报告生成失败，请稍后重试。",
    decisions: {
      accept: "接受",
      revise: "修改后接受",
      hold: "暂缓",
      reject: "驳回",
    },
    newsMode: "新闻优先",
    newsModeHelp: "打开原始来源阅读全文 → 形成新闻理解报告 → 再生成证据链",
    hypothesisMode: "假设优先",
    hypothesisModeHelp: "保留原流程：提出问题 → 搜索证据 → 核验因果假设",
    newsUnderstanding: "新闻理解报告",
    reportedFacts: "已确认报道事实",
    openQuestions: "仍待核对",
    documentsRead: "已检查来源",
    contentRead: "已取得正文",
    headlineExcluded: "仅标题已排除",
    secTitle: "SEC 退市与并购证据审核",
    secSubtitle:
      "核对已发布的 SEC 原文、提取数值和身份安全门。本站只读展示审核记录，因子入库仍须通过本地验证。",
    secAssets: "已检索资产",
    secFilings: "候选申报",
    secValues: "数值候选",
    secPending: "待审核",
    secConflicts: "身份冲突",
    secSource: "SEC 原文",
    secIdentity: "身份门",
    secFactor: "因子池",
    secFactorReady: "安全门已通过",
    secFactorBlocked: "安全门阻止写入",
    secReviewNote: "写明接受、驳回或需要补证据的理由…",
    secSave: "保存审核",
    secSaved: "手机审核已保存，等待本地同步",
    secFailed: "审核保存失败",
    secAccept: "接受",
    secHold: "待补证据",
    secReject: "驳回",
    secNoData: "尚未加载已发布 SEC 证据",
    secFinalCash: "最终现金对价",
    secHistorical: "历史/谈判报价",
    secImplied: "换股隐含价值",
    secRatio: "换股比例",
    secIdentityConflict: "身份或生命周期存在冲突，不能写入因子池。",
    secPricePending: "历史价格序列未就绪。",
    secAlreadyVerified: "终值已进入因子池。",
    secRemoteBoundary: "本站展示已发布的审核记录，不会绕过身份与价格安全门，也不会直接修改因子池。",
    dataTitle: "数据与模型运行状态",
    dataSubtitle: "本地数据库与已发布数据的实际覆盖",
    metricLabels: [
      "本地坐标事件",
      "已发布冲突记录",
      "新闻索引",
      "正文可用",
      "仅标题排除",
      "本地 ACLED 代表事件",
    ],
    health: "数据边界已标注",
    model: "本地研究模型",
    prompt: "本地审计流程",
    training: "增强训练",
    trainingState: "审核反馈进入可审计改进队列",
    coverageTitle: "远程同步范围",
    coverage: "已发布冲突记录 2025–2026；完整本地历史从 1989 开始",
    disclaimer: "研究工具 · 非投资建议",
  },
  en: {
    beta: "ORAKT research platform",
    snapshot: "Data version date",
    tabs: {
      map: "Event map",
      evidence: "AI evidence report",
      sec: "SEC review",
      data: "Data status",
    },
    search: "Search country, location or event",
    filters: "Observation window",
    windows: { "7d": "7 days", "30d": "30 days", "90d": "90 days", all: "All" },
    conflict: "War & conflict",
    layers: "Map indicators",
    events: "Events",
    detail: "Details",
    showConflict: "War and conflict locations",
    colorSeverity: "Color by conflict severity",
    economy: "Country economic indicator",
    economyHelp:
      "Latest annual values from the World Bank; markers use capital reference locations.",
    loadingEconomy: "Loading economic data…",
    supplyChain: "Supply-chain facilities",
    showSupplyChain: "Supplier facilities & manufacturing regions",
    supplyHelp:
      "Off by default. Exact facilities and regional reference points are distinct; nearby conflict or port proximity does not prove disruption.",
    loadingSupply: "Loading published supply-chain data…",
    exactFacility: "Exact facility",
    regionalReference: "Regional reference",
    facilityRole: "Site role",
    companyFacility: "Company facility",
    upstreamSupplierLocation: "Upstream supplier location",
    supplier: "Related supplier",
    exposureWindow: "Risk window",
    nearbyConflict: "Nearby conflict",
    nearbyDisaster: "Nearby disaster",
    powerSignals: "Power signals",
    nearestPort: "Nearest port reference",
    layerHelp:
      "Layers appear only when enabled and follow the replay window. Points cluster when zoomed out for mobile performance.",
    close: "Close panel",
    eventCount: "visible records",
    selected: "Event check",
    severity: "Severity",
    confidence: "Source confidence",
    source: "Source",
    noEvents: "No events or facilities at this replay time",
    replay: "Event replay",
    play: "Play replay",
    pause: "Pause replay",
    loadingData: "Loading published conflict data…",
    showing: "The list shows 200; the map shows all filtered records",
    readonly:
      "Published data, not a live feed; headline-only news cannot independently verify a claim.",
    finalConfidence: "Combined confidence",
    researchPlaceholder:
      "Ask an economic, market or international-event question",
    researchAction: "Generate & verify report",
    researching:
      "AI is reading sources, drafting a report and verifying evidence…",
    executive: "Executive summary",
    chainTitle: "Causal transmission",
    evidenceLedger: "Evidence ledger",
    scoreTitle: "Confidence composition",
    alternatives: "Alternative explanations",
    limitations: "Limits & counterevidence",
    nextData: "Recommended data",
    verified: "Verified",
    partial: "Partial",
    missing: "Insufficient",
    reviewer: "Human review",
    reviewerHelp:
      "Feedback is stored as an auditable signal for prompt, rule and verified-chain improvement.",
    commentPlaceholder:
      "Add evidence, identify a bad step, or write the revised causal link…",
    saveFeedback: "Save review",
    saved: "Feedback saved",
    reportError: "Report generation failed. Try again later.",
    decisions: {
      accept: "Accept",
      revise: "Revise & accept",
      hold: "Hold",
      reject: "Reject",
    },
    newsMode: "News first",
    newsModeHelp:
      "Open original sources → produce a news-understanding report → build the evidence chain",
    hypothesisMode: "Hypothesis first",
    hypothesisModeHelp:
      "Keep the existing flow: ask → retrieve evidence → validate the causal hypothesis",
    newsUnderstanding: "News-understanding report",
    reportedFacts: "Reported facts verified",
    openQuestions: "Still unresolved",
    documentsRead: "Sources checked",
    contentRead: "Full text obtained",
    headlineExcluded: "Headline-only excluded",
    secTitle: "SEC delisting and transaction evidence review",
    secSubtitle:
      "Inspect published SEC filings, extracted values and identity safety gates. This is a read-only review record; factor admission still requires local validation.",
    secAssets: "Assets searched",
    secFilings: "Candidate filings",
    secValues: "Value candidates",
    secPending: "Pending review",
    secConflicts: "Identity conflicts",
    secSource: "SEC filing",
    secIdentity: "Identity gate",
    secFactor: "Factor pool",
    secFactorReady: "Safety gates passed",
    secFactorBlocked: "Factor admission blocked",
    secReviewNote:
      "Explain why this should be accepted, rejected or supplemented…",
    secSave: "Save review",
    secSaved: "Mobile review saved; awaiting local synchronization",
    secFailed: "Could not save review",
    secAccept: "Accept",
    secHold: "Needs evidence",
    secReject: "Reject",
    secNoData: "Published SEC evidence is not loaded",
    secFinalCash: "Final cash consideration",
    secHistorical: "Historical / negotiated offer",
    secImplied: "Implied stock value",
    secRatio: "Share exchange ratio",
    secIdentityConflict:
      "Identity or lifecycle conflict blocks factor admission.",
    secPricePending: "Historical price series is not ready.",
    secAlreadyVerified: "Terminal value is already in the factor pool.",
    secRemoteBoundary:
      "Published review records do not bypass identity or price safety gates and do not directly modify the factor pool.",
    dataTitle: "Data and model status",
    dataSubtitle: "Measured local database and published data coverage",
    metricLabels: [
      "Local geolocated events",
      "Published conflict records",
      "News index",
      "Content ready",
      "Headline-only excluded",
      "Local ACLED represented events",
    ],
    health: "Data boundaries disclosed",
    model: "Local research model",
    prompt: "Local audit workflow",
    training: "Enhanced training",
    trainingState: "Reviewer feedback enters the auditable improvement queue",
    coverageTitle: "Remote synchronization",
    coverage: "Published conflict records 2025–2026; full local history begins in 1989",
    disclaimer: "Research tool · Not investment advice",
  },
};

function severityColor(score: number) {
  if (score >= 55) return "#ff4d4f";
  if (score >= 36) return "#ff9f43";
  return "#f6c85f";
}
function formatEconomic(value: number, unit: string) {
  return economicValue(value, unit);
}
function formatCount(value: number | undefined) {
  return metricCount(value);
}
function formatBytes(value: number | undefined) {
  if (value === undefined) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(2)} MB`;
}
async function readJsonWithSize<T>(response: Response) {
  if (!response.ok) throw new Error(response.status===403?"需要对应会员授权，或账号权限已失效。请前往账号中心查看。 / Access required or expired. See your account.":`HTTP ${response.status}`);
  const text = await response.text();
  return {
    payload: JSON.parse(text) as T,
    bytes: new TextEncoder().encode(text).byteLength,
  };
}
function formatPrice(value: number | null) {
  return !finiteNumber(value) ? "—" : `$${value!.toFixed(2)}`;
}
function formatMarketPrice(
  value: number | null,
  marketRegion: "us" | "china",
) {
  return !finiteNumber(value)
    ? "—"
    : `${marketRegion === "china" ? "¥" : "$"}${value!.toFixed(2)}`;
}
function formatMove(value: number | null | undefined) {
  return !finiteNumber(value)
    ? "—"
    : `${value! >= 0 ? "+" : ""}${(value! * 100).toFixed(1)}%`;
}
function formatInterval(
  interval: [number | null, number | null] | undefined,
) {
  if (!interval || interval[0] == null || interval[1] == null) return "—";
  return `${formatMove(interval[0])} ～ ${formatMove(interval[1])}`;
}
function formatRatio(value: number | null) {
  return value == null ? "—" : `${value.toFixed(1)}×`;
}
function formatLargeMoney(value: number | null) {
  if (value == null) return "—";
  const absolute = Math.abs(value);
  return absolute >= 1e12
    ? `$${(value / 1e12).toFixed(2)}T`
    : absolute >= 1e9
      ? `$${(value / 1e9).toFixed(1)}B`
      : `$${(value / 1e6).toFixed(1)}M`;
}

function DataReadinessPanel({
  readiness,
  language,
}: {
  readiness: DataReadiness;
  language: Language;
}) {
  const ready = readiness.directionalConclusionAllowed;
  return (
    <section className={`data-readiness-panel ${ready ? "ready" : "bounded"}`}>
      <header>
        <div>
          <span>
            <ShieldCheck size={15} />
            {language === "zh"
              ? "公司研究数据门控"
              : "Issuer research data gate"}
          </span>
          <h2>
            {ready
              ? language === "zh"
                ? "完整研究条件已达到"
                : "Full research threshold met"
              : language === "zh"
                ? "仅允许生成证据缺口报告"
                : "Evidence-gap report only"}
          </h2>
          <p>{language === "zh" ? readiness.policyZh : readiness.policyEn}</p>
        </div>
        <strong>
          {readiness.score}%
          <small>{language === "zh" ? "数据完整度" : "data readiness"}</small>
        </strong>
      </header>
      <div className="readiness-components">
        {readiness.components.map((item) => (
          <article className={item.status} key={item.key}>
            <div>
              <b>{language === "zh" ? item.labelZh : item.labelEn}</b>
              <span>{item.weight}% weight</span>
            </div>
            <strong>{item.score}%</strong>
            <i>
              <span style={{ width: `${item.score}%` }} />
            </i>
            <p>{language === "zh" ? item.detailZh : item.detailEn}</p>
          </article>
        ))}
      </div>
      {!ready && (
        <footer>
          <CircleAlert size={15} />
          <span>
            {language === "zh" ? "尚缺必需数据" : "Required gaps"}:{" "}
            {readiness.missingRequired.join(" · ") || "—"}
          </span>
          <b>
            {language === "zh"
              ? `方向置信度上限 ${readiness.confidenceCap}%`
              : `Directional-confidence cap ${readiness.confidenceCap}%`}
          </b>
        </footer>
      )}
    </section>
  );
}

function DisclosureCoveragePanel({
  coverage,
  language,
}: {
  coverage: DisclosureCoverage;
  language: Language;
}) {
  const structured = coverage.financialMetrics > 0;
  const metrics = [
    {
      label: language === "zh" ? "财务指标候选" : "Financial candidates",
      value: coverage.financialMetrics,
    },
    {
      label: language === "zh" ? "股东原文片段" : "Shareholder excerpts",
      value: coverage.shareholderExcerpts,
    },
    {
      label: language === "zh" ? "经营原文片段" : "Operating excerpts",
      value: coverage.operatingExcerpts,
    },
    {
      label: language === "zh" ? "供应链原文片段" : "Supply-chain excerpts",
      value: coverage.supplyChainExcerpts,
    },
  ];
  return (
    <section
      className={`disclosure-coverage-panel ${structured ? "structured" : "bounded"}`}
    >
      <header>
        <div>
          <span>
            <FileSearch size={15} />
            {language === "zh"
              ? "A 股官方公告证据"
              : "Official A-share disclosure evidence"}
          </span>
          <h2>
            {structured
              ? language === "zh"
                ? "公告原文已结构化为可核对候选"
                : "Disclosure text structured into reviewable candidates"
              : language === "zh"
                ? "公告全文可用，结构化字段仍不足"
                : "Full filings available; structured fields remain limited"}
          </h2>
          <p>
            {language === "zh"
              ? "保留原文片段、附近数值、报告期和发布时间。PDF 表格列尚未完成交叉校对的数值不会被当作审计事实。"
              : "Exact excerpts, nearby values, period and publication time are retained. Values without reconciled PDF columns are not promoted to audited facts."}
          </p>
        </div>
        <b>
          {coverage.periodStart || "—"} — {coverage.periodEnd || "—"}
          <small>{language === "zh" ? "公告覆盖时间" : "coverage window"}</small>
        </b>
      </header>
      <div className="disclosure-coverage-grid">
        {metrics.map((item) => (
          <article key={item.label}>
            <strong>{item.value}</strong>
            <span>{item.label}</span>
          </article>
        ))}
      </div>
      <footer>
        <span>
          {language === "zh" ? "官方公告" : "Official filings"}: {" "}
          {language === "zh" ? "定期" : "periodic"} {coverage.periodicReports} · {" "}
          {language === "zh" ? "股东" : "shareholder"} {coverage.shareholderDocuments} · {" "}
          {language === "zh" ? "经营" : "operating"} {coverage.operatingDocuments} · {" "}
          {language === "zh" ? "供应链" : "supply-chain"} {coverage.supplyChainDocuments}
        </span>
        <em>{coverage.structuredStatus || coverage.status || "—"}</em>
      </footer>
    </section>
  );
}

function CanslimPanel({
  scorecard,
  language,
}: {
  scorecard: CanslimScorecard;
  language: Language;
}) {
  const statusLabel = (value: CanslimCriterion["status"]) =>
    ({
      pass: language === "zh" ? "通过" : "Pass",
      partial: language === "zh" ? "部分" : "Partial",
      fail: language === "zh" ? "未通过" : "Fail",
      missing: language === "zh" ? "缺数据" : "Missing",
    })[value];
  const decision =
    scorecard.decision === "criteria_supported"
      ? language === "zh"
        ? "筛选条件得到支持"
        : "Screen supported"
      : scorecard.decision === "insufficient_evidence"
        ? language === "zh"
          ? "证据不足"
          : "Insufficient evidence"
        : language === "zh"
          ? "条件混合，尚未确认"
          : "Mixed / not confirmed";
  return (
    <section className="canslim-panel">
      <header>
        <div>
          <span>
            <Activity size={15} />
            CAN SLIM · {scorecard.version}
          </span>
          <h2>
            {language === "zh"
              ? "七项成长筛选与交易纪律审计"
              : "Seven-factor growth screen & discipline audit"}
          </h2>
          <p>
            {language === "zh"
              ? "使用点时 SEC、OHLCV、标普 500 与 13F 数据；图片中的 941% 宣传结果不作为证据。"
              : "Uses point-in-time SEC, OHLCV, S&P 500 and 13F data. The advertised 941% result is not treated as evidence."}
          </p>
        </div>
        <strong>
          {scorecard.overallScore.toFixed(0)}
          <small>/ 100 · {decision}</small>
          <em>
            {language === "zh"
              ? `覆盖 ${scorecard.coverageScore.toFixed(0)}%`
              : `${scorecard.coverageScore.toFixed(0)}% covered`}
          </em>
        </strong>
      </header>
      <div className="canslim-grid">
        {scorecard.criteria.map((item) => (
          <article className={item.status} key={item.code}>
            <header>
              <b>{item.code}</b>
              <div>
                <strong>
                  {language === "zh" ? item.labelZh : item.labelEn}
                </strong>
                <small>
                  {item.weight}% weight · {statusLabel(item.status)}
                </small>
              </div>
              <em>{item.score.toFixed(0)}</em>
            </header>
            <p>{item.observed}</p>
            <footer>
              <span>
                {language === "zh" ? "门槛" : "Threshold"}: {item.threshold}
              </span>
              <small>
                {item.evidenceCount}{" "}
                {language === "zh" ? "条证据引用" : "evidence refs"}
              </small>
            </footer>
          </article>
        ))}
      </div>
      <div className="canslim-discipline">
        <div>
          <span>
            {language === "zh" ? "机械突破位代理" : "Mechanical pivot proxy"}
          </span>
          <strong>{formatPrice(scorecard.discipline.pivotProxy)}</strong>
          <small>
            {language === "zh"
              ? "52周最高收盘，不是人工确认形态"
              : "52-week closing high; not a manually validated base"}
          </small>
        </div>
        <div>
          <span>
            {language === "zh"
              ? "传统买入区间代理"
              : "Traditional buy-zone proxy"}
          </span>
          <strong>
            {formatPrice(scorecard.discipline.buyZoneLower)} —{" "}
            {formatPrice(scorecard.discipline.buyZoneUpper)}
          </strong>
          <small>{scorecard.discipline.currentPosition || "—"}</small>
        </div>
        <div>
          <span>{language === "zh" ? "风控纪律" : "Risk discipline"}</span>
          <strong>-7% / -8% · +20% / +25%</strong>
          <small>
            {language === "zh"
              ? "历史规则情景，不自动生成订单"
              : "Historical rule scenario; no automatic order"}
          </small>
        </div>
      </div>
      <footer>
        <CircleAlert size={14} />
        <span>
          {language === "zh"
            ? "通过筛选不等于未来盈利或合适买点；必须继续进行样本外检验。"
            : "Passing a screen does not prove future profit or an appropriate entry; out-of-sample testing is still required."}
        </span>
      </footer>
    </section>
  );
}

function CompetitorOperatingPanel({
  comparison,
  language,
}: {
  comparison: CompetitorOperatingComparison;
  language: Language;
}) {
  const subject = comparison.ticker;
  const metric = (value: number | null) => formatMove(value);
  const flagged = comparison.rows.filter(
    (row) => (row.quarterly?.qualityFlags.length || 0) > 0,
  );
  const qualityLabel = (flag: string) =>
    ({
      extreme_revenue_change_review_corporate_actions:
        language === "zh"
          ? "收入变化极端，需核对并购/重述"
          : "Extreme revenue move: review corporate actions",
      gross_margin_unavailable_in_standard_taxonomy:
        language === "zh"
          ? "标准分类缺少毛利"
          : "Gross margin unavailable in standard taxonomy",
      gross_margin_outside_expected_accounting_range:
        language === "zh"
          ? "毛利率超出常见会计区间"
          : "Gross margin outside expected accounting range",
      extreme_net_margin_review_one_offs:
        language === "zh"
          ? "净利率极端，需核对一次性损益"
          : "Extreme net margin: review one-off gains/losses",
      research_intensity_unavailable_in_standard_taxonomy:
        language === "zh"
          ? "标准分类缺少研发费用"
          : "R&D intensity unavailable in standard taxonomy",
    })[flag] || flag;
  return (
    <section className="competitor-operating-panel">
      <header>
        <div>
          <span>
            <Database size={15} />
            {language === "zh"
              ? "同口径竞争比较"
              : "Like-for-like competitor comparison"}
          </span>
          <h2>
            {subject} · {comparison.peerGroup.join(" / ")}
          </h2>
          <p>
            {language === "zh"
              ? "10‑Q 单季度与年度 SEC 指标分别同口径比较；财季日期单列，不把累计季度或不同产品名称强行混排。"
              : "Single-quarter 10-Q and annual SEC metrics are compared separately. Quarter dates stay visible; YTD contexts and unlike product labels are not mixed."}
          </p>
        </div>
        <b>
          {comparison.asOf}
          <small>
            {language === "zh" ? "点时截止" : "point-in-time cutoff"}
          </small>
        </b>
      </header>
      <div className="competitor-table-scroll">
        <table>
          <thead>
            <tr>
              <th>{language === "zh" ? "公司" : "Company"}</th>
              <th>10‑Q {language === "zh" ? "收入同比" : "revenue YoY"}</th>
              <th>10‑Q {language === "zh" ? "毛利率" : "gross margin"}</th>
              <th>10‑Q {language === "zh" ? "净利率" : "net margin"}</th>
              <th>
                {language === "zh" ? "财季/可得日" : "Quarter / available"}
              </th>
              <th>
                {language === "zh" ? "年度收入同比" : "Annual revenue YoY"}
              </th>
              <th>
                {language === "zh" ? "年度毛利率" : "Annual gross margin"}
              </th>
              <th>{language === "zh" ? "年度净利率" : "Annual net margin"}</th>
              <th>
                {language === "zh" ? "年度研发强度" : "Annual R&D / revenue"}
              </th>
              <th>
                {language === "zh"
                  ? "财年/可得日"
                  : "Fiscal period / available"}
              </th>
            </tr>
          </thead>
          <tbody>
            {comparison.rows.map((row) => (
              <tr
                className={row.ticker === subject ? "subject" : ""}
                key={row.ticker}
              >
                <td>
                  <b>{row.ticker}</b>
                  <small>{row.company}</small>
                </td>
                <td>{metric(row.quarterly?.revenueYoy ?? null)}</td>
                <td>{metric(row.quarterly?.grossMargin ?? null)}</td>
                <td>{metric(row.quarterly?.netMargin ?? null)}</td>
                <td>
                  <span>{row.quarterly?.periodEnd || "—"}</span>
                  <small>{row.quarterly?.availableAt || "—"}</small>
                </td>
                <td>{metric(row.revenueYoy)}</td>
                <td>{metric(row.grossMargin)}</td>
                <td>{metric(row.netMargin)}</td>
                <td>{metric(row.researchIntensity)}</td>
                <td>
                  <span>{row.periodEnd || "—"}</span>
                  <small>{row.availableAt || "—"}</small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {flagged.length > 0 && (
        <div className="competitor-quality-notes">
          <CircleAlert size={15} />
          <div>
            <strong>
              {language === "zh" ? "10‑Q 异常值复核" : "10-Q anomaly review"}
            </strong>
            {flagged.map((row) => (
              <p key={row.ticker}>
                <b>{row.ticker}</b> ·{" "}
                {row.quarterly!.qualityFlags.map(qualityLabel).join("；")}
              </p>
            ))}
          </div>
        </div>
      )}
      {comparison.productDisclosures.length > 0 && (
        <details>
          <summary>
            {language === "zh"
              ? "查看 10‑Q / 10‑K 产品经营原文"
              : "Inspect 10-Q / 10-K product disclosures"}{" "}
            · {comparison.productDisclosures.length}
          </summary>
          <div className="product-disclosure-grid">
            {comparison.productDisclosures.map((item, index) => (
              <article key={`${item.ticker}-${item.metricType}-${index}`}>
                <header>
                  <b>
                    {item.ticker} · {item.product}
                  </b>
                  <span>
                    {item.filingForm} · {item.periodEnd}
                  </span>
                </header>
                <strong>{item.metricName}</strong>
                <p>{item.sourceExcerpt}</p>
                <footer>
                  <span>
                    {item.reportedValues.join(" · ") || "qualitative"}
                  </span>
                  {item.sourceUrl && (
                    <a href={item.sourceUrl} target="_blank" rel="noreferrer">
                      SEC
                      <ExternalLink size={11} />
                    </a>
                  )}
                </footer>
              </article>
            ))}
          </div>
        </details>
      )}
      <footer>
        <ShieldCheck size={14} />
        <span>
          {language === "zh"
            ? "只有相同 metric_type 才进入产品同类对照；所有排名都是描述性比较，不是收益预测。"
            : "Only matching metric_type values enter product comparisons. Rankings are descriptive, not return forecasts."}
        </span>
      </footer>
    </section>
  );
}

function TradingScenarioPanel({
  scenario,
  language,
}: {
  scenario: TradingScenario;
  language: Language;
}) {
  const formatPrice = (value:number|null) => formatMarketPrice(value, /^\d{6}$/.test(scenario.ticker) ? "china" : "us");
  const horizonOptions = scenario.horizonModels?.models ?? [];
  const [horizonKey, setHorizonKey] = useState(
    horizonOptions[1]?.key ?? horizonOptions[0]?.key ?? "swing",
  );
  const activeHorizon =
    horizonOptions.find((item) => item.key === horizonKey) ?? horizonOptions[0];
  const displayStop = activeHorizon?.stopReference ?? scenario.stopReference;
  const displayTarget = activeHorizon?.targetReference ?? scenario.targetReference;
  const displayDownside =
    activeHorizon?.downsideFraction ?? scenario.downsideFraction;
  const displayUpside = activeHorizon?.upsideFraction ?? scenario.upsideFraction;
  const displayRewardRisk =
    activeHorizon?.rewardRiskRatio ?? scenario.rewardRiskRatio;
  const points = scenario.chart.filter((item) => Number.isFinite(item.close));
  const hasOhlcv =
    scenario.barDataStatus === "complete_ohlcv" &&
    points.every(
      (item) => item.open != null && item.high != null && item.low != null,
    );
  const width = 840,
    height = hasOhlcv ? 330 : 270,
    padX = 42,
    padY = 24,
    priceBottom = hasOhlcv ? 245 : height - padY;
  const plotted = [
    ...points.flatMap((item) =>
      [item.low, item.high, item.close, item.sma20, item.sma50].filter(
        (value): value is number => value != null && Number.isFinite(value),
      ),
    ),
    displayStop,
    displayTarget,
  ].filter((value): value is number => value != null && Number.isFinite(value));
  const rawMin = plotted.length ? Math.min(...plotted) : 0,
    rawMax = plotted.length ? Math.max(...plotted) : 1;
  const padding = Math.max((rawMax - rawMin) * 0.1, 1);
  const minY = rawMin - padding,
    maxY = rawMax + padding;
  const x = (index: number) =>
    padX +
    (points.length <= 1
      ? 0
      : (index * (width - padX * 2)) / (points.length - 1));
  const y = (value: number) =>
    priceBottom - ((value - minY) * (priceBottom - padY)) / (maxY - minY || 1);
  const path = (key: "close" | "sma20" | "sma50") =>
    points
      .map((item, index) =>
        item[key] == null
          ? null
          : `${x(index).toFixed(1)},${y(item[key] as number).toFixed(1)}`,
      )
      .filter(Boolean)
      .join(" ");
  const chartStart = points[0]?.date ?? scenario.observedOn,
    chartEnd = points.at(-1)?.date ?? scenario.observedOn;
  const above = (value: number | null) =>
    scenario.entryPrice != null && value != null
      ? scenario.entryPrice >= value
        ? language === "zh"
          ? "价格在其上方"
          : "price above"
        : language === "zh"
          ? "价格在其下方"
          : "price below"
      : "—";
  const candleWidth = Math.max(
    2.2,
    Math.min(6, ((width - padX * 2) / Math.max(points.length, 1)) * 0.62),
  );
  const maxVolume = Math.max(1, ...points.map((item) => item.volume ?? 0));
  const volumeTop = 266,
    volumeBottom = 316;
  return (
    <section className="trading-scenario-panel">
      <header>
        <div>
          <span>POINT-IN-TIME SCENARIO · {scenario.ticker}</span>
          <h2>
            {language === "zh"
              ? "当前价风险收益与技术结构图"
              : "Current-price risk/reward & technical structure"}
          </h2>
          <p>
            {language === "zh"
              ? `数据截止 ${scenario.observedOn}；所有价位为研究参考，不是下单指令。`
              : `Data cutoff ${scenario.observedOn}; all levels are research references, not order instructions.`}
          </p>
        </div>
        <b>
          {displayRewardRisk == null
            ? "—"
            : `1 : ${displayRewardRisk.toFixed(2)}`}
          <small>
            {language === "zh" ? "风险 : 潜在收益" : "risk : potential reward"}
          </small>
        </b>
      </header>
      {horizonOptions.length > 0 && (
        <>
          <nav className="horizon-tabs" aria-label="Entry horizon">
            {horizonOptions.map((item) => (
              <button
                type="button"
                className={item.key === activeHorizon?.key ? "active" : ""}
                key={item.key}
                onClick={() => setHorizonKey(item.key)}
              >
                <b>{language === "zh" ? item.labelZh : item.labelEn}</b>
                <small>{item.horizonSessions} sessions</small>
              </button>
            ))}
          </nav>
          {activeHorizon && (
            <section className="horizon-backtest">
              <div className="horizon-signal">
                <span>{language === "zh" ? "当前点时信号" : "Point-in-time signal"}</span>
                <b>
                  {activeHorizon.status === "research_signal"
                    ? language === "zh"
                      ? "研究信号成立"
                      : "Research signal"
                    : activeHorizon.status === "requires_point_in_time_fundamentals"
                      ? language === "zh"
                        ? "等待财报门槛"
                        : "Fundamental gate pending"
                      : activeHorizon.status === "insufficient_history"
                        ? language === "zh"
                          ? "历史数据不足"
                          : "Insufficient history"
                        : language === "zh"
                          ? "观察，不触发入场"
                          : "Watch only"}
                </b>
                <small>
                  {language === "zh" ? "规则得分" : "Rule score"} ·{" "}
                  {activeHorizon.currentSignal.score == null
                    ? "—"
                    : `${(activeHorizon.currentSignal.score * 100).toFixed(0)}%`}
                </small>
              </div>
              <div>
                <span>{language === "zh" ? "样本外回测" : "Out-of-sample backtest"}</span>
                <b>
                  {activeHorizon.validation.testSignals} /{" "}
                  {activeHorizon.validation.testObservations}{" "}
                  {language === "zh" ? "次信号/观察" : "signals/tests"}
                </b>
                <small>
                  {language === "zh" ? "胜率" : "Hit rate"} {" "}
                  {activeHorizon.validation.hitRate == null
                    ? "—"
                    : `${(activeHorizon.validation.hitRate * 100).toFixed(1)}%`}{" "}
                  · {language === "zh" ? "平均净收益" : "mean net return"}{" "}
                  {formatMove(activeHorizon.validation.meanStrategyReturn)}
                </small>
              </div>
              <div>
                <span>{language === "zh" ? "历史报告到期复盘" : "Historical-report replay"}</span>
                <b>
                  {activeHorizon.reportReplay.status === "pending"
                    ? language === "zh"
                      ? `待到期 · 已有 ${activeHorizon.reportReplay.availableFutureSessions ?? 0} 日`
                      : `Pending · ${activeHorizon.reportReplay.availableFutureSessions ?? 0} sessions`
                    : activeHorizon.reportReplay.status === "matured_signal"
                      ? language === "zh"
                        ? "信号已到期"
                        : "Matured signal"
                      : language === "zh"
                        ? "已到期但未触发"
                        : "Matured, no signal"}
                </b>
                <small>
                  {activeHorizon.reportReplay.netReturn == null
                    ? language === "zh"
                      ? "结果未用于倒改原报告"
                      : "Outcome never rewrites the report"
                    : `${activeHorizon.reportReplay.entryDate} → ${activeHorizon.reportReplay.exitDate} · ${formatMove(activeHorizon.reportReplay.netReturn)}`}
                </small>
              </div>
              <details>
                <summary>
                  {language === "zh"
                    ? "查看可回测参数与防未来函数规则"
                    : "Backtest parameters & leakage guard"}
                </summary>
                <div className="horizon-parameters">
                  {Object.entries(activeHorizon.parameters).map(([key, value]) => (
                    <span key={key}>
                      <b>{key.replaceAll("_", " ")}</b>
                      {String(value)}
                    </span>
                  ))}
                </div>
                <p>{activeHorizon.validation.leakageGuard}</p>
                {activeHorizon.fundamentalGate.required && (
                  <p>
                    {activeHorizon.fundamentalGate.passed ? "✓" : "!"}{" "}
                    {activeHorizon.fundamentalGate.explanation}
                  </p>
                )}
              </details>
            </section>
          )}
        </>
      )}
      <div className="scenario-metrics">
        <article>
          <span>{language === "zh" ? "入场观察区间" : "Entry watch zone"}</span>
          <strong>
            {activeHorizon
              ? `${formatPrice(activeHorizon.entryZone.lower)} — ${formatPrice(activeHorizon.entryZone.upper)}`
              : formatPrice(scenario.entryPrice)}
          </strong>
          <small>{scenario.observedOn} · {formatPrice(scenario.entryPrice)}</small>
        </article>
        <article className="risk">
          <span>
            {language === "zh"
              ? "失效/止损参考"
              : "Invalidation / stop reference"}
          </span>
          <strong>{formatPrice(displayStop)}</strong>
          <small>
            {formatMove(
              displayDownside == null
                ? null
                : -displayDownside,
            )}{" "}
            · {activeHorizon ? `${activeHorizon.horizonSessions} sessions` : scenario.stopBasis}
          </small>
        </article>
        <article className="reward">
          <span>
            {language === "zh"
              ? "目标/止盈参考"
              : "Target / take-profit reference"}
          </span>
          <strong>{formatPrice(displayTarget)}</strong>
          <small>
            {formatMove(displayUpside)} · {activeHorizon ? `${activeHorizon.horizonSessions} sessions` : scenario.targetBasis}
          </small>
        </article>
        <article>
          <span>
            {language === "zh"
              ? "一周历史波动区间"
              : "1-week historical-vol band"}
          </span>
          <strong>
            {formatPrice(scenario.oneWeekBand.lower)} —{" "}
            {formatPrice(scenario.oneWeekBand.upper)}
          </strong>
          <small>
            ±{" "}
            {scenario.oneWeekBand.expectedMove == null
              ? "—"
              : `${(Math.abs(scenario.oneWeekBand.expectedMove) * 100).toFixed(1)}%`}
          </small>
        </article>
        <article>
          <span>
            {language === "zh"
              ? "两周历史波动区间"
              : "2-week historical-vol band"}
          </span>
          <strong>
            {formatPrice(scenario.twoWeekBand.lower)} —{" "}
            {formatPrice(scenario.twoWeekBand.upper)}
          </strong>
          <small>
            ±{" "}
            {scenario.twoWeekBand.expectedMove == null
              ? "—"
              : `${(Math.abs(scenario.twoWeekBand.expectedMove) * 100).toFixed(1)}%`}
          </small>
        </article>
        <article>
          <span>
            {language === "zh"
              ? "最近支撑 / 阻力"
              : "Nearest support / resistance"}
          </span>
          <strong>
            {formatPrice(scenario.support.value)} /{" "}
            {formatPrice(scenario.resistance.value)}
          </strong>
          <small>
            {scenario.support.label || "—"} · {scenario.resistance.label || "—"}
          </small>
        </article>
        <article>
          <span>ATR14</span>
          <strong>{formatPrice(scenario.atr14)}</strong>
          <small>
            {language === "zh" ? "真实波动区间均值" : "average true range"}
          </small>
        </article>
        <article>
          <span>
            {language === "zh" ? "最新量 / 20日均量" : "Latest / 20-day volume"}
          </span>
          <strong>
            {scenario.volumeRatio20 == null
              ? "—"
              : `${scenario.volumeRatio20.toFixed(2)}×`}
          </strong>
          <small>{scenario.volumeStatus || "—"}</small>
        </article>
      </div>
      {points.length > 1 && (
        <div className="technical-chart">
          <div className="chart-heading">
            <div>
              <b>
                {language === "zh"
                  ? hasOhlcv
                    ? "90 日K线、成交量、均线与波段结构"
                    : "90 日收盘、均线回踩与顶底结构"
                  : hasOhlcv
                    ? "90-day candlesticks, volume, averages & swing structure"
                    : "90-day close, moving-average pullbacks & structure"}
              </b>
              <span>
                {chartStart} — {chartEnd}
              </span>
            </div>
            <div className="chart-legend">
              <i className="close" />
              {hasOhlcv ? "OHLCV" : language === "zh" ? "收盘" : "Close"}
              <i className="ma20" />
              SMA20
              <i className="ma50" />
              SMA50
              <i className="stop" />
              {language === "zh" ? "失效" : "Stop"}
              <i className="target" />
              {language === "zh" ? "目标" : "Target"}
            </div>
          </div>
          <svg
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label={
              language === "zh"
                ? "K线、成交量与移动平均线技术图"
                : "Candlestick, volume and moving-average chart"
            }
          >
            {[0, 0.25, 0.5, 0.75, 1].map((part) => {
              const price = maxY - (maxY - minY) * part;
              const chartY = padY + (priceBottom - padY) * part;
              return (
                <g key={part}>
                  <line
                    x1={padX}
                    x2={width - padX}
                    y1={chartY}
                    y2={chartY}
                    className="grid"
                  />
                  <text x={4} y={chartY + 4}>
                    {price.toFixed(0)}
                  </text>
                </g>
              );
            })}
            {hasOhlcv &&
              points.map((item, index) => {
                const up = item.close >= (item.open as number);
                const center = x(index);
                const bodyTop = y(Math.max(item.open as number, item.close));
                const bodyBottom = y(Math.min(item.open as number, item.close));
                const volumeHeight =
                  ((item.volume ?? 0) / maxVolume) * (volumeBottom - volumeTop);
                return (
                  <g className={`candle ${up ? "up" : "down"}`} key={item.date}>
                    <line
                      x1={center}
                      x2={center}
                      y1={y(item.high as number)}
                      y2={y(item.low as number)}
                    />
                    <rect
                      x={center - candleWidth / 2}
                      y={bodyTop}
                      width={candleWidth}
                      height={Math.max(1.4, bodyBottom - bodyTop)}
                    />
                    <rect
                      className="volume"
                      x={center - candleWidth / 2}
                      y={volumeBottom - volumeHeight}
                      width={candleWidth}
                      height={volumeHeight}
                    />
                  </g>
                );
              })}
            {hasOhlcv && (
              <>
                <text x={4} y={volumeTop + 9}>
                  VOL
                </text>
                <line
                  x1={padX}
                  x2={width - padX}
                  y1={volumeBottom}
                  y2={volumeBottom}
                  className="grid"
                />
              </>
            )}
            {displayStop != null && (
              <line
                x1={padX}
                x2={width - padX}
                y1={y(displayStop)}
                y2={y(displayStop)}
                className="level stop"
              />
            )}
            {displayTarget != null && (
              <line
                x1={padX}
                x2={width - padX}
                y1={y(displayTarget)}
                y2={y(displayTarget)}
                className="level target"
              />
            )}
            <polyline points={path("sma50")} className="series sma50" />
            <polyline points={path("sma20")} className="series sma20" />
            {!hasOhlcv && (
              <polyline points={path("close")} className="series close" />
            )}
          </svg>
          <div className="ma-state">
            <span>
              SMA20 {formatPrice(scenario.averages.sma20)} ·{" "}
              {above(scenario.averages.sma20)}
            </span>
            <span>
              SMA50 {formatPrice(scenario.averages.sma50)} ·{" "}
              {above(scenario.averages.sma50)}
            </span>
            <span>
              SMA200 {formatPrice(scenario.averages.sma200)} ·{" "}
              {above(scenario.averages.sma200)}
            </span>
          </div>
          <p>
            {language === "zh"
              ? hasOhlcv
                ? "K线使用拆股调整日线；真实波段高低点用于支撑阻力，ATR14用于止损缓冲。成交量不能识别机构。"
                : "缺少完整OHLC与成交量时，不宣称完整K线形态。"
              : hasOhlcv
                ? "Candlesticks use split-adjusted daily bars. Swing highs/lows set structure and ATR14 sets the stop buffer; volume does not identify institutions."
                : "No full candlestick claim is made without OHLC and volume."}
          </p>
        </div>
      )}
      <div className="institutional-cost">
        <div>
          <span>
            {language === "zh"
              ? "大户/机构平均成本"
              : "Large-holder / institutional average cost"}
          </span>
          <strong>
            {language === "zh" ? "真实成本不可得" : "Actual cost unavailable"}
          </strong>
          <p>
            {language === "zh"
              ? "13F 不披露买入价格或成本基础。下方仅显示季度末申报价值÷股数代理，不能当作机构买入均价。"
              : scenario.institutional.explanation}
          </p>
        </div>
        <aside>
          <span>
            {language === "zh"
              ? "13F 期末价值代理"
              : "13F quarter-end value proxy"}
          </span>
          <b>
            {formatPrice(scenario.institutional.quarterEndValuePerShareProxy)}
          </b>
          <small>
            {scenario.institutional.reportPeriod || "—"} ·{" "}
            {scenario.institutional.proxyScope || "top reported managers"}
          </small>
        </aside>
      </div>
      {scenario.institutional.topManagers.length > 0 && (
        <div className="institutional-managers">
          {scenario.institutional.topManagers.map((item) => (
            <div key={item.name}>
              <b>{item.name}</b>
              <span>{formatPrice(item.quarterEndValuePerShareProxy)}</span>
              <small>
                {language === "zh"
                  ? "期末价值代理，不是成本"
                  : "quarter-end value proxy, not cost"}
              </small>
            </div>
          ))}
        </div>
      )}
      <footer>{scenario.methodNote}</footer>
    </section>
  );
}

function VirtualList<T>({
  items,
  itemHeight,
  className,
  getKey,
  renderItem,
}: {
  items: T[];
  itemHeight: number;
  className: string;
  getKey: (item: T) => string;
  renderItem: (item: T) => ReactNode;
}) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(520);
  const overscan = 5;
  const start = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
  const end = Math.min(
    items.length,
    Math.ceil((scrollTop + viewportHeight) / itemHeight) + overscan,
  );

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const observer = new ResizeObserver(([entry]) => {
      setViewportHeight(Math.max(itemHeight, entry.contentRect.height));
    });
    observer.observe(viewport);
    return () => observer.disconnect();
  }, [itemHeight]);

  function handleScroll(event: UIEvent<HTMLDivElement>) {
    setScrollTop(event.currentTarget.scrollTop);
  }

  return (
    <div
      ref={viewportRef}
      className={`${className} virtual-list-viewport`}
      onScroll={handleScroll}
      role="list"
      aria-label={`Virtualized list, ${items.length} items`}
    >
      <div
        className="virtual-list-spacer"
        style={{ height: `${items.length * itemHeight}px` }}
      >
        <div
          className="virtual-list-window"
          style={{ transform: `translateY(${start * itemHeight}px)` }}
        >
          {items.slice(start, end).map((item) => (
            <div
              className="virtual-list-row"
              style={{ height: `${itemHeight}px` }}
              key={getKey(item)}
              role="listitem"
            >
              {renderItem(item)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FullResearchBody({report,language}:{report:EvidenceReport;language:Language}) {
  const t=copy[language],accessRights={reports:true};
  return <>
              {language==="en"&&!report.translations?.en&&!report.dossier&&<p role="status" className="orakt-boundary">The English body for this archived report is not available yet. The Chinese original is shown; changing the interface language does not constitute a translation.</p>}
              {report.researchCompletion&&<ResearchCompletion data={report.researchCompletion} language={language}/>}
              {report.peerStudy&&<PeerFactorStudy data={report.peerStudy} language={language}/>}
              {report.ticker && accessRights?.reports && <Suspense fallback={<p role="status">{language==='zh'?'加载财务图表…':'Loading financial charts…'}</p>}><CompanyFinancialCharts key={report.id} ticker={report.ticker} asOf={report.historical?.asOf||report.createdAt?.slice(0,10)} periodEnd={report.historical?.periodEnd} language={language}/></Suspense>}
              {report.dossier&&<CompanyDossier dossier={report.dossier} language={language}/>}
              {!report.dossier&&report.financialSupplement&&<FinancialPeriodLedger ledger={report.financialSupplement.financialLedger} language={language}/>}
              {report.financialSupplement?.marketCoverage&&<ReportMarketCoverage items={report.financialSupplement.marketCoverage} language={language}/>}
              {report.dataReadiness && (
                <DataReadinessPanel
                  readiness={report.dataReadiness}
                  language={language}
                />
              )}
              {report.disclosureCoverage && (
                <DisclosureCoveragePanel
                  coverage={report.disclosureCoverage}
                  language={language}
                />
              )}
              {report.analysisMode === "news_first" && (
                <section className="news-understanding">
                  <header>
                    <span>
                      <Newspaper size={15} />
                      {report.historical ? (language==="zh"?"历史财报审阅":"Historical filing review") : t.newsUnderstanding}
                    </span>
                    <div>
                      <b>{report.newsReport.documentsReviewed}</b>{" "}
                      {t.documentsRead} ·{" "}
                      <b>{report.newsReport.fullContentReviewed}</b>{" "}
                      {t.contentRead} ·{" "}
                      <b>{report.newsReport.headlineOnlyExcluded}</b>{" "}
                      {t.headlineExcluded}
                    </div>
                  </header>
                  <h2>{report.newsReport.headline}</h2>
                  <p>{report.newsReport.narrative}</p>
                  <div className="news-fact-grid">
                    <div>
                      <b>{t.reportedFacts}</b>
                      <ul>
                        {report.newsReport.facts.map((item) => (
                          <li key={item}>
                            <Check size={13} />
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <b>{t.openQuestions}</b>
                      <ul>
                        {report.newsReport.uncertainties.map((item) => (
                          <li key={item}>
                            <CircleAlert size={13} />
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </section>
              )}
              <section className="executive-summary">
                <span>{t.executive}</span>
                <h2>{report.verdict}</h2>
                <p><ReadingText text={report.thesis}/></p>
              </section>
              {report.tradingScenario && (
                <TradingScenarioPanel
                  scenario={report.tradingScenario}
                  language={language}
                />
              )}
              {report.canslim && (
                <CanslimPanel scorecard={report.canslim} language={language} />
              )}
              <ReportEvidence report={report} language={language}/>
  </>;
}

export default function PilotDashboard({
  initialTab = "map",
}: {
  initialTab?: Tab;
}) {
  const [language, setLanguage] = useDisplayLanguage();
  const workspaceRef=useWorkspaceChrome();
  const {tickers: watchedTickers}=useWatchlist();
  const [accessRights,setAccessRights]=useState<{reports:boolean;research:boolean}|null>(null);
  const [accessError,setAccessError]=useState(false);
  useEffect(()=>{const c=new AbortController();fetch("/api/account/overview",{cache:"no-store",signal:c.signal}).then(async r=>{if(!r.ok)throw Error();return r.json();}).then(d=>setAccessRights(d.account.membership.permissions)).catch(()=>{if(!c.signal.aborted)setAccessError(true);});return()=>c.abort();},[]);
  const [tab, setTab] = useState<Tab>(initialTab);
  const [windowKey, setWindowKey] = useState<WindowKey>("90d");
  const [query, setQuery] = useState("");
  const [events, setEvents] = useState<EventItem[]>(fallbackEvents);
  const [manifest, setManifest] = useState<SnapshotManifest | null>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(fallbackEvents[0].id);
  const [secEvidence, setSecEvidence] = useState<SecEvidenceSnapshot | null>(
    null,
  );
  const [conflictEnabled, setConflictEnabled] = useState(true);
  const [warEventsEnabled,setWarEventsEnabled]=useState(true);
  const [thermalEventsEnabled,setThermalEventsEnabled]=useState(false);
  const [severityEnabled, setSeverityEnabled] = useState(true);
  const [economyEnabled, setEconomyEnabled] = useState(false);
  const [chainEnabled,setChainEnabled]=useState(false);
  const [mapChainSelection,setMapChainSelection]=useState<string[]>([]);
  const [mapChainView,setMapChainView]=useState<any>({logistics:true,risks:true,query:'',active:null});
  const mapChainLinkLoaded=useRef(false);
  const {data:mapChainData,error:mapChainError}=useResearchData(tab==='map'?'/api/map-chains':null);
  useEffect(()=>{const requested=new URLSearchParams(window.location.search).get('chain');if(!mapChainLinkLoaded.current&&mapChainData?.limit&&mapChainData.chains?.some((c:any)=>c.id===requested)){mapChainLinkLoaded.current=true;setMapChainSelection([requested!]);}},[mapChainData]);
  useEffect(()=>{if(chainEnabled&&mapChainData?.chains?.length){setMapChainSelection([mapChainData.chains.find((c:any)=>c.id==='hormuz-helium')?.id||mapChainData.chains[0].id]);setChainEnabled(false);}},[chainEnabled,mapChainData]);
  const [economicError,setEconomicError]=useState('');
  const [economicRetry,setEconomicRetry]=useState(0);
  const [economicIndicator, setEconomicIndicator] = useState("FP.CPI.TOTL.ZG");
  const [economicData, setEconomicData] = useState<EconomicObservation[]>([]);
  const [economicLoading, setEconomicLoading] = useState(false);
  const [economicSelected, setEconomicSelected] =
    useState<EconomicObservation | null>(null);
  const [supplyEnabled, setSupplyEnabled] = useState(false);
  const [supplySnapshot, setSupplySnapshot] =
    useState<SupplyChainSnapshot | null>(null);
  const [supplyLoading, setSupplyLoading] = useState(false);
  const [supplyError, setSupplyError] = useState("");
  const [supplySelected, setSupplySelected] = useState<SupplyChainSite | null>(
    null,
  );
  const [timelineDay, setTimelineDay] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>(null);
  const [mapReady, setMapReady] = useState(0);
  const [mapLoadState, setMapLoadState] =
    useState<MapLoadState>("idle");
  const [mapLoadError, setMapLoadError] = useState("");
  const [mapBootNonce, setMapBootNonce] = useState(0);
  const [clientLoadMetrics, setClientLoadMetrics] = useState<
    Record<string, ClientLoadMetric>
  >({});
  const [selectedReport, setReport] = useState<EvidenceReport | null>(null);
  const [allLocalReports, setAllLocalReports] = useState<ReportIndexItem[]>([]);
  const [localReportsLoading, setLocalReportsLoading] = useState(true);
  const [localReportsError, setLocalReportsError] = useState("");
  const [reportDetailLoading, setReportDetailLoading] = useState(false);
  const [reportDetailError, setReportDetailError] = useState("");
  const [equityCatalog, setEquityCatalog] =
    useState<EquityReportCatalog | null>(null);
  const [evidenceView, setEvidenceView] = useState<EvidenceView>("single");
  const [reportTheme, setReportTheme] = useState<"light" | "dark">("light");
  const [entryMarket, setEntryMarket] = useState<"all" | "china" | "us">("all");
  const [dateBasis, setDateBasis] = useState("evidence");
  const [appliedDateBasis, setAppliedDateBasis] = useState("evidence");
  const deepLinkLoaded = useRef(false);
  useEffect(() => {
    try { const saved = localStorage.getItem("orakt-report-theme"); if (saved === "dark" || saved === "light") setReportTheme(saved); } catch { /* Device preferences are optional. */ }
  }, []);
  function chooseReportTheme(value: "light" | "dark") {
    setReportTheme(value);
    try { localStorage.setItem("orakt-report-theme", value); } catch { /* Private browsing may reject storage. */ }
  }
  const [reportMarket, setReportMarket] = useState<ReportMarket>("all");
  const [reportCompany, setReportCompany] = useState("all");
  const [reportFrom, setReportFrom] = useState("");
  const [reportTo, setReportTo] = useState("");
  const [reportVersion, setReportVersion] = useState("");
  const [appliedReportMarket, setAppliedReportMarket] =
    useState<ReportMarket>("all");
  const [appliedReportCompany, setAppliedReportCompany] = useState("all");
  const [appliedReportFrom, setAppliedReportFrom] = useState("");
  const [appliedReportTo, setAppliedReportTo] = useState("");
  const [reportFilterNotice, setReportFilterNotice] = useState("");
  const [comparisonMode, setComparisonMode] = useState<"macro"|"peers">("macro");
  const [comparisonReportId, setComparisonReportId] = useState("");
  const [comparisonDetail, setComparisonDetail] =
    useState<EvidenceReport | null>(null);
  const [comparisonDetailLoading, setComparisonDetailLoading] = useState(false);
  const [comparisonDetailError, setComparisonDetailError] = useState("");
  const [semiconductorComparison, setSemiconductorComparison] =
    useState<SemiconductorComparison | null>(null);
  const [entryBacktestStatus, setEntryBacktestStatus] =
    useState<EntryBacktestStatus | null>(null);
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const maplibreRef = useRef<MapLibreModule | null>(null);
  const economicMarkersRef = useRef<Marker[]>([]);
  const eventsByIdRef = useRef<Map<string, EventItem>>(new Map());
  const supplyByIdRef = useRef<Map<number, SupplyChainSite>>(new Map());
  const reportLoadSequenceRef = useRef(0);
  const comparisonLoadSequenceRef = useRef(0);
  const reportAbortRef = useRef<AbortController | null>(null);
  const comparisonAbortRef = useRef<AbortController | null>(null);
  const t = copy[language];
  const timelineStartIso = `${manifest?.remoteSnapshot.conflictStartsAt ?? fallbackStartIso.slice(0, 10)}T00:00:00Z`;
  const timelineEndIso = `${manifest?.remoteSnapshot.conflictEndsAt ?? fallbackEndIso.slice(0, 10)}T00:00:00Z`;
  const timelineMaxDay = useMemo(
    () =>
      Math.max(
        0,
        Math.round(
          (new Date(timelineEndIso).getTime() -
            new Date(timelineStartIso).getTime()) /
            dayMs,
        ),
      ),
    [timelineEndIso, timelineStartIso],
  );
  const cursorDate = useMemo(
    () =>
      new Date(
        new Date(timelineStartIso).getTime() +
          Math.min(timelineDay, timelineMaxDay) * dayMs,
      ),
    [timelineDay, timelineMaxDay, timelineStartIso],
  );
  const cursorDateLabel = cursorDate.toISOString().slice(0, 10);
  const visibleEvents = useMemo(() => {
    const maxDays = { "7d": 7, "30d": 30, "90d": 90, all: Infinity }[windowKey];
    const normalized = query.trim().toLowerCase();
    return events.filter((item) => {
      const age =
        (cursorDate.getTime() - new Date(`${item.date}T00:00:00Z`).getTime()) /
        dayMs;
      const haystack =
        `${item.title} ${item.location} ${item.country} ${item.eventType}`.toLowerCase();
      return (
        (item.eventType==='thermal_anomaly'?thermalEventsEnabled:warEventsEnabled)&&
        age >= 0 &&
        age <= maxDays &&
        (!normalized || haystack.includes(normalized))
      );
    });
  }, [cursorDate, events, query, windowKey,warEventsEnabled,thermalEventsEnabled]);
  const selected =
    events.find((item) => item.id === selectedId) ??
    events[0] ??
    fallbackEvents[0];
  const visibleSupplySites = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return (supplySnapshot?.sites ?? []).filter(
      (item) =>
        !normalized ||
        `${item.siteName} ${item.relatedCompanyName} ${item.relatedTicker} ${item.contextTicker} ${item.contextTickers.join(" ")} ${item.facilityRole} ${item.countryName} ${item.admin1Name}`
          .toLowerCase()
          .includes(normalized),
    );
  }, [query, supplySnapshot]);
  const mapListItems = useMemo<MapListItem[]>(
    () => [
      ...(conflictEnabled
        ? visibleEvents.map((item) => ({ kind: "event" as const, item }))
        : []),
      ...(supplyEnabled
        ? visibleSupplySites.map((item) => ({ kind: "supply" as const, item }))
        : []),
    ],
    [conflictEnabled, supplyEnabled, visibleEvents, visibleSupplySites],
  );
  const companyOptions = useMemo(() => {
    const rows = new Map<
      string,
      { key: string; label: string; market: string }
    >();
    for (const item of equityCatalog?.companies ?? []) {
      if (reportMarket !== "all" && item.marketRegion !== reportMarket)
        continue;
      const key = `${item.marketRegion}:${item.ticker}`;
      const pending =
        item.reportIds.length === 0
          ? language === "zh"
            ? " · 尚无已发布报告"
            : " · no published report"
          : "";
      rows.set(key, {
        key,
        label: `${item.ticker} · ${item.companyName}${pending}`,
        market: item.marketRegion,
      });
    }
    for (const item of allLocalReports) {
      const market = item.marketRegion ?? "global";
      if (reportMarket !== "all" && market !== reportMarket) continue;
      const ticker = item.ticker || item.tradingScenario?.ticker || "";
      const name = item.companyName || ticker;
      if (!ticker) continue;
      const key = `${market}:${ticker}`;
      rows.set(key, { key, label: `${ticker} · ${name}`, market });
    }
    return [...rows.values()].sort((left, right) =>
      Number(watchedTickers.includes(right.key.split(':')[1]))-Number(watchedTickers.includes(left.key.split(':')[1])) || left.label.localeCompare(right.label, language === "zh" ? "zh-CN" : "en"),
    );
  }, [allLocalReports, equityCatalog, language, reportMarket, watchedTickers]);
  const reportVersionOptions = useMemo(
    () =>
      allLocalReports
        .filter((item) => {
          const market = item.marketRegion ?? "global";
          const ticker = item.ticker || item.tradingScenario?.ticker || "";
          const reportDate = reportFilterDate(item, dateBasis);
          if ((reportFrom || reportTo) && !reportDate) return false;
          return (isCompanyReport(item)&&
            (reportMarket === "all" || market === reportMarket) &&
            (reportCompany === "all" ||
              `${market}:${ticker}` === reportCompany) &&
            (!reportFrom || reportDate >= reportFrom) &&
            (!reportTo || reportDate <= reportTo)
          );
        })
        .sort((left, right) => right.createdAt.localeCompare(left.createdAt)),
    [allLocalReports, reportCompany, reportFrom, reportMarket, reportTo, dateBasis],
  );
  const filteredReports = useMemo(
    () =>
      allLocalReports.filter((item) => {
        const market = item.marketRegion ?? "global";
        const ticker = item.ticker || item.tradingScenario?.ticker || "";
        const reportDate = reportFilterDate(item, appliedDateBasis);
        if ((appliedReportFrom || appliedReportTo) && !reportDate) return false;
        return (isCompanyReport(item)&&
          (appliedReportMarket === "all" || market === appliedReportMarket) &&
          (appliedReportCompany === "all" ||
            `${market}:${ticker}` === appliedReportCompany) &&
          (!appliedReportFrom || reportDate >= appliedReportFrom) &&
          (!appliedReportTo || reportDate <= appliedReportTo)
        );
      }),
    [
      allLocalReports,
      appliedReportCompany,
      appliedReportFrom,
      appliedReportMarket,
      appliedReportTo,
      appliedDateBasis,
    ],
  );
  const localReports = useMemo(()=>[...filteredReports].sort((a,b)=>Number(watchedTickers.includes(b.ticker||''))-Number(watchedTickers.includes(a.ticker||''))),[filteredReports,watchedTickers]);
  useEffect(()=>{
    // The chain page owns its report query. Redirecting it to itself reloads forever.
    if(tab !== 'evidence')return;
    if(deepLinkLoaded.current || !accessRights?.reports || !allLocalReports.length)return;
    const params=new URLSearchParams(window.location.search);
    if(params.get("view")==="operations")setEvidenceView("operations");
    const requested=params.get("report");
    if(!requested)return;
    deepLinkLoaded.current=true;
    const match=allLocalReports.find(r=>r.id===requested);
    if(match&&!isCompanyReport(match)){window.location.replace(reportHref(match));return;}
    if(match){setEvidenceView("single");setReportVersion(match.id);void loadLocalReport(match);}
    else setReportFilterNotice(language==="zh"?"这个报告版本未发布或无权查看。":"Report revision is unavailable or access is required.");
  },[allLocalReports,accessRights,tab]);
  const listedLocalReports = useMemo(
    () => localReports.slice(0, 60),
    [localReports],
  );
  const comparisonReports = useMemo(() => {
    const latest = new Map<string, ReportIndexItem>();
    const ordered = allLocalReports
      .filter((item) => item.hasCompetitorComparison)
      .sort((left, right) => right.createdAt.localeCompare(left.createdAt));
    for (const item of ordered) {
      const key = `${item.marketRegion}:${item.ticker || item.tradingScenario?.ticker || item.id}`;
      if (!latest.has(key)) latest.set(key, item);
    }
    return [...latest.values()];
  }, [allLocalReports]);
  const comparisonReport =
    comparisonReports.find((item) => item.id === comparisonReportId) ??
    comparisonReports[0] ??
    null;
  const entryCandidates = useMemo<EntryWatchCandidate[]>(() => {
    const latest = new Map<string, ReportIndexItem>();
    const ordered = allLocalReports.filter(item => entryMarket === "all" || item.marketRegion === entryMarket).sort((left, right) =>
      right.createdAt.localeCompare(left.createdAt),
    );
    for (const item of ordered) {
      const market = item.marketRegion;
      const ticker = item.ticker || item.tradingScenario?.ticker;
      if ((market !== "us" && market !== "china") || !ticker) continue;
      const key = `${market}:${ticker}`;
      if (!latest.has(key)) latest.set(key, item);
    }
    const newestMarketDate = [...latest.values()]
      .map((item) => item.tradingScenario?.observedOn || "")
      .sort()
      .at(-1);
    const freshnessFloor = newestMarketDate
      ? new Date(`${newestMarketDate}T00:00:00Z`).getTime() - 7 * dayMs
      : 0;
    const candidates: EntryWatchCandidate[] = [];
    for (const item of latest.values()) {
      const scenario = item.tradingScenario;
      const market = item.marketRegion;
      if (!scenario || (market !== "us" && market !== "china")) continue;
      const currentPrice = scenario.entryPrice;
      const support = scenario.support.value;
      const stop = scenario.stopReference;
      const target = scenario.targetReference;
      const rewardRisk = scenario.rewardRiskRatio;
      const downside = scenario.downsideFraction;
      const upside = scenario.upsideFraction;
      if (
        currentPrice == null ||
        support == null ||
        stop == null ||
        target == null ||
        rewardRisk == null ||
        downside == null ||
        upside == null
      )
        continue;
      const audit = item.audit;
      const auditReady = Boolean(
        audit &&
          audit.status !== "data_quality_blocked" &&
          audit.missingReferences === 0 &&
          audit.headlineOnlyReferences === 0 &&
          audit.futureDatedReferences === 0 &&
          audit.foreignSubjects === 0,
      );
      const chinaEvidence = item.disclosureCoverage;
      const evidenceReady =
        item.dataReadiness?.directionalConclusionAllowed === true ||
        (market === "china" &&
          (chinaEvidence?.financialMetrics ?? 0) >= 5 &&
          chinaEvidence?.status === "completed");
      const observedAt = new Date(`${scenario.observedOn}T00:00:00Z`).getTime();
      const distanceToSupport = currentPrice / support - 1;
      if (
        !auditReady ||
        !evidenceReady ||
        !Number.isFinite(observedAt) ||
        observedAt < freshnessFloor ||
        rewardRisk < 2 ||
        downside < 0.02 ||
        downside > 0.085 ||
        upside < 0.06 ||
        distanceToSupport < -0.02 ||
        distanceToSupport > 0.035
      )
        continue;
      const zoneWidth = scenario.atr14
        ? Math.min(scenario.atr14 * 0.5, support * 0.03)
        : support * 0.025;
      const evidenceScore = item.dataReadiness
        ? item.dataReadiness.score
        : Math.min(100, (chinaEvidence?.financialMetrics ?? 0) * 2);
      const rankingScore = Math.round(
        Math.min(40, (rewardRisk / 4) * 40) +
          Math.min(20, (upside / 0.15) * 20) +
          evidenceScore * 0.25 +
          (item.confidence / 75) * 15,
      );
      candidates.push({
        report: item,
        ticker: item.ticker || scenario.ticker,
        company: item.companyName || item.ticker || scenario.ticker,
        marketRegion: market,
        observedOn: scenario.observedOn,
        currentPrice,
        zoneLower: support,
        zoneUpper: support + zoneWidth,
        stopReference: stop,
        targetReference: target,
        rewardRiskRatio: rewardRisk,
        downsideFraction: downside,
        upsideFraction: upside,
        distanceToSupport,
        evidenceScore,
        rankingScore,
      });
    }
    return candidates
      .sort(
        (left, right) =>
          right.rankingScore - left.rankingScore ||
          right.rewardRiskRatio - left.rewardRiskRatio,
      )
      .slice(0, 12);
  }, [allLocalReports, entryMarket]);
  const report = useMemo(()=>reportForReading(localizeReport(
    selectedReport &&
    (selectedReport.origin === "remote_openai" ||
      filteredReports.some((item) => item.id === selectedReport.id))
      ? selectedReport
      : null, language),language),[selectedReport,filteredReports,language]);
  const visibleReportVersion = reportVersionOptions.some(
    (item) => item.id === reportVersion,
  )
    ? reportVersion
    : (reportVersionOptions[0]?.id ?? "");

  useEffect(() => {
    if (!["map","data"].includes(tab) || manifest) return;
    const controller = new AbortController();
    fetch("/api/snapshot", { signal: controller.signal })
      .then((response) =>
        response.ok
          ? response.json()
          : Promise.reject(new Error("manifest")),
      )
      .then((nextManifest: SnapshotManifest) => {
        setManifest(nextManifest);
        const start = new Date(
          `${nextManifest.remoteSnapshot.conflictStartsAt}T00:00:00Z`,
        ).getTime();
        const end = new Date(
          `${nextManifest.remoteSnapshot.conflictEndsAt}T00:00:00Z`,
        ).getTime();
        setTimelineDay(Math.round((end - start) / dayMs));
      })
      .catch((error) => {
        if (error.name !== "AbortError")
          setTimelineDay(
            Math.round(
              (new Date(fallbackEndIso).getTime() -
                new Date(fallbackStartIso).getTime()) /
              dayMs,
            ),
          );
      });
    return () => controller.abort();
  }, [manifest, tab]);
  useEffect(() => {
    if (tab !== "data" || !accessRights?.research || entryBacktestStatus) return;
    const controller = new AbortController();
    fetch("/api/entry-backtest-status", { signal: controller.signal })
      .then((response) =>
        response.ok
          ? response.json()
          : Promise.reject(new Error("entry backtest status")),
      )
      .then((payload: EntryBacktestStatus) => setEntryBacktestStatus(payload))
      .catch((error: Error) => {
        if (error.name !== "AbortError") setEntryBacktestStatus(null);
      });
    return () => controller.abort();
  }, [entryBacktestStatus, tab, accessRights]);
  useEffect(() => {
    if (tab !== "map" || mapLoadState !== "ready") return;
    const controller = new AbortController();
    const days = windowKey === "all" ? "all" : windowKey.replace("d", "");
    const startedAt = performance.now();
    fetch(`/api/conflicts?days=${days}`, { signal: controller.signal })
      .then((response) => readJsonWithSize<EventItem[]>(response))
      .then(({ payload: conflicts, bytes }) => {
        setEvents(conflicts);
        setClientLoadMetrics((current) => ({
          ...current,
          conflicts: {
            status: "ready",
            durationMs: Math.round(performance.now() - startedAt),
            bytes,
            records: conflicts.length,
            observedAt: new Date().toISOString(),
            detail: windowKey,
          },
        }));
        setSelectedId((current) =>
          conflicts.some((item) => item.id === current)
            ? current
            : (conflicts[0]?.id ?? fallbackEvents[0].id),
        );
      })
      .catch((error: Error) => {
        if (error.name !== "AbortError") {
          setEvents(fallbackEvents);
          setClientLoadMetrics((current) => ({
            ...current,
            conflicts: {
              status: "error",
              durationMs: Math.round(performance.now() - startedAt),
              observedAt: new Date().toISOString(),
              detail: error.message,
            },
          }));
        }
      })
      .finally(() => setDataLoading(false));
    return () => controller.abort();
  }, [mapLoadState, tab, windowKey]);
  useEffect(() => {
    if (tab !== "sec" || !accessRights?.reports || secEvidence) return;
    const controller = new AbortController();
    fetch("/api/sec-evidence", { signal: controller.signal })
      .then((response) =>
        response.ok
          ? response.json()
          : Promise.reject(new Error("sec evidence")),
      )
      .then((payload: SecEvidenceSnapshot) => setSecEvidence(payload))
      .catch((error: Error) => {
        if (error.name !== "AbortError") setSecEvidence(null);
      });
    return () => controller.abort();
  }, [secEvidence, tab, accessRights]);
  useEffect(() => {
    if (!["evidence","chains"].includes(tab) || !accessRights?.reports || allLocalReports.length > 0) return;
    const controller = new AbortController();
    const startedAt = performance.now();
    fetch("/api/research-report-index", {
      signal: controller.signal,
      credentials: "same-origin",
    })
      .then((response) =>
        readJsonWithSize<ResearchReportIndexSnapshot>(response),
      )
      .then(({ payload, bytes }) => {
        const reports = payload.reports ?? [];
        setAllLocalReports(reports);
        setClientLoadMetrics((current) => ({
          ...current,
          reportIndex: {
            status: "ready",
            durationMs: Math.round(performance.now() - startedAt),
            bytes,
            records: reports.length,
            observedAt: new Date().toISOString(),
          },
        }));
        setLocalReportsError("");
        setReportVersion((current) => current || reports[0]?.id || "");
      })
      .catch((error: Error) => {
        if (error.name !== "AbortError") {
          setLocalReportsError(
            "已发布报告暂时不可用 / Published reports unavailable",
          );
          setClientLoadMetrics((current) => ({
            ...current,
            reportIndex: {
              status: "error",
              durationMs: Math.round(performance.now() - startedAt),
              observedAt: new Date().toISOString(),
              detail: error.message,
            },
          }));
        }
      })
      .finally(() => setLocalReportsLoading(false));
    return () => controller.abort();
  }, [allLocalReports.length, tab, accessRights]);
  useEffect(() => {
    if (tab !== "evidence" || equityCatalog) return;
    const controller = new AbortController();
    fetch("/api/equity-report-catalog", { signal: controller.signal })
      .then((response) =>
        response.ok
          ? response.json()
          : Promise.reject(new Error("equity catalog")),
      )
      .then((payload: EquityReportCatalog) => setEquityCatalog(payload))
      .catch((error: Error) => {
        if (error.name !== "AbortError") setEquityCatalog(null);
      });
    return () => controller.abort();
  }, [equityCatalog, tab]);
  useEffect(() => {
    if (
      tab !== "evidence" ||
      evidenceView !== "cross" ||
      !accessRights?.research ||
      semiconductorComparison
    )
      return;
    const controller = new AbortController();
    fetch("/api/semiconductor-comparison", { signal: controller.signal })
      .then((response) =>
        response.ok
          ? response.json()
          : Promise.reject(new Error("semiconductor comparison")),
      )
      .then((payload: SemiconductorComparison) =>
        setSemiconductorComparison(payload),
      )
      .catch((error: Error) => {
        if (error.name !== "AbortError") setSemiconductorComparison(null);
      });
    return () => controller.abort();
  }, [evidenceView, semiconductorComparison, tab, accessRights]);
  useEffect(() => {
    if (!supplyEnabled || supplySnapshot || supplyError) return;
    if(!accessRights)return;
    if(!accessRights.research){setSupplyError(language==="zh"?"供应链图层需要 Research 授权，请查看账号中心。":"Supply-chain layers require Research access. See your account.");setSupplyLoading(false);return;}
    setSupplyLoading(true);
    const controller = new AbortController();
    const startedAt = performance.now();
    fetch("/api/supply-chain-sites", { signal: controller.signal })
      .then((response) => readJsonWithSize<SupplyChainSnapshot>(response))
      .then(({ payload, bytes }) => {
        setSupplySnapshot(payload);
        setClientLoadMetrics((current) => ({
          ...current,
          supplyChain: {
            status: "ready",
            durationMs: Math.round(performance.now() - startedAt),
            bytes,
            records: payload.sites.length,
            observedAt: new Date().toISOString(),
          },
        }));
      })
      .catch((error: Error) => {
        if (error.name !== "AbortError") {
          setSupplyError(
            language === "zh"
              ? "已发布供应链数据暂时不可用"
              : "Published supply-chain data unavailable",
          );
          setClientLoadMetrics((current) => ({
            ...current,
            supplyChain: {
              status: "error",
              durationMs: Math.round(performance.now() - startedAt),
              observedAt: new Date().toISOString(),
              detail: error.message,
            },
          }));
        }
      })
      .finally(() => setSupplyLoading(false));
    return () => controller.abort();
  }, [language, supplyEnabled, supplyError, supplySnapshot, accessRights]);
  useEffect(() => {
    eventsByIdRef.current = new Map(events.map((item) => [item.id, item]));
  }, [events]);
  useEffect(() => {
    supplyByIdRef.current = new Map(
      (supplySnapshot?.sites ?? []).map((item) => [item.siteId, item]),
    );
  }, [supplySnapshot]);
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(
      () =>
        setTimelineDay((day) => {
          if (day >= timelineMaxDay) {
            setPlaying(false);
            return day;
          }
          return day + 1;
        }),
      700,
    );
    return () => window.clearInterval(timer);
  }, [playing, timelineMaxDay]);
  useEffect(() => {
    if (!economyEnabled) return;
    const controller = new AbortController();
    let active=true;setEconomicLoading(true);setEconomicError('');setEconomicData([]);setEconomicSelected(null);
    const timeout=window.setTimeout(()=>controller.abort(),15000);
    fetch(`/api/economics?indicator=${encodeURIComponent(economicIndicator)}&year=${cursorDate.getUTCFullYear()}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("economic request failed");
        return response.json();
      })
      .then((payload: { observations: EconomicObservation[]; delivery?:string; retrievedAt?:string }) => {
        if(active){setEconomicData(payload.observations ?? []);if(!payload.observations?.length)setEconomicError('此指标/年份暂无有效观测 · No observations for this indicator/year');else if(payload.delivery==='cached')setEconomicError(`World Bank 缓存 / cached · ${payload.retrievedAt?.slice(0,10)} · 非实时 / not live`);}
      })
      .catch((error: Error) => {
        if(active){setEconomicData([]);setEconomicError(error.name==='AbortError'?'数据源超时，请重试 · Provider timed out; retry':'数据源暂不可用，请重试 · Provider unavailable; retry');}
      })
      .finally(() => {clearTimeout(timeout);if(active)setEconomicLoading(false)});
    return () => {active=false;clearTimeout(timeout);controller.abort()};
  }, [economicIndicator, economyEnabled, economicRetry, cursorDate.getUTCFullYear()]);
  useEffect(() => {
    if (tab !== "map" || !mapContainer.current) return;
    let disposed = false;
    let activeMap: MapLibreMap | null = null;
    const bootTimer = window.setTimeout(() => {
      if (disposed) return;
      setMapLoadState("loading");
      setMapLoadError("");
      const startedAt = performance.now();
      void import("maplibre-gl")
        .then((maplibregl) => {
          if (disposed || !mapContainer.current) return;
    maplibreRef.current = maplibregl;
    // v6 requires an explicit bundled worker; raster tiles alone do not test it.
    maplibregl.setWorkerUrl(mapWorkerUrl);
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources: {
          "osm-de": {
            type: "raster",
            tiles: ["https://tile.openstreetmap.de/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [
          {
            id: "orakt-basemap",
            type: "raster",
            source: "osm-de",
            paint: {
              "raster-saturation": -0.82,
              "raster-brightness-min": 0.04,
              "raster-brightness-max": 0.46,
              "raster-contrast": 0.2,
            },
          },
        ],
      },
      center: [19, 30],
      zoom: 1.55,
      minZoom: 1,
      maxZoom: 9,
      renderWorldCopies: false,
      attributionControl: false,
    });
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "bottom-right",
    );
    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-left",
    );
    activeMap = map;
    map.on("load", () => {
      if (disposed) return;
      map.addSource("conflicts", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
        cluster: true,
        clusterRadius: 38,
        clusterMaxZoom: 6,
        clusterProperties: { severityMax: ["max", ["get", "severity"]] },
      });
      map.addLayer({
        id: "conflict-clusters",
        type: "circle",
        source: "conflicts",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": [
            "step",
            ["get", "severityMax"],
            "#f6c85f",
            36,
            "#ff9f43",
            55,
            "#ff4d4f",
          ],
          "circle-radius": [
            "step",
            ["get", "point_count"],
            15,
            20,
            20,
            100,
            27,
            500,
            34,
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#09080f",
          "circle-opacity": 0.82,
        },
      });
      map.addLayer({
        id: "conflict-cluster-count",
        type: "symbol",
        source: "conflicts",
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["get", "point_count_abbreviated"],
          "text-font": ["Noto Sans Regular"],
          "text-size": 10,
        },
        paint: {
          "text-color": "#09080f",
          "text-halo-color": "rgba(243, 245, 239, 0.42)",
          "text-halo-width": 0.6,
        },
      });
      map.addLayer({
        id: "conflict-points",
        type: "circle",
        source: "conflicts",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": [
            "step",
            ["get", "severity"],
            "#f6c85f",
            36,
            "#ff9f43",
            55,
            "#ff4d4f",
          ],
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 3, 7, 7],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#09080f",
          "circle-opacity": 0.86,
        },
      });
      map.addSource("supply-chain", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
        cluster: true,
        clusterRadius: 44,
        clusterMaxZoom: 7,
        clusterProperties: {
          attentionMax: ["max", ["get", "attention"]],
          exactCount: [
            "+",
            ["case", ["==", ["get", "precision"], "exact_facility"], 1, 0],
          ],
        },
      });
      map.addLayer({
        id: "supply-clusters",
        type: "circle",
        source: "supply-chain",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": [
            "step",
            ["get", "attentionMax"],
            "#5c7cfa",
            1,
            "#7651c9",
            20,
            "#b83280",
          ],
          "circle-radius": [
            "step",
            ["get", "point_count"],
            15,
            20,
            20,
            80,
            25,
            250,
            31,
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#09080f",
          "circle-opacity": 0.86,
        },
      });
      map.addLayer({
        id: "supply-cluster-count",
        type: "symbol",
        source: "supply-chain",
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["get", "point_count_abbreviated"],
          "text-size": 10,
          "text-font": ["Noto Sans Regular"],
        },
        paint: {
          "text-color": "#09080f",
          "text-halo-color": "rgba(243, 245, 239, 0.42)",
          "text-halo-width": 0.6,
        },
      });
      map.addLayer({
        id: "supply-regions",
        type: "circle",
        source: "supply-chain",
        filter: [
          "all",
          ["!", ["has", "point_count"]],
          ["!=", ["get", "precision"], "exact_facility"],
        ],
        paint: {
          "circle-color": "#7257c7",
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 3.5, 7, 7],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#09080f",
          "circle-opacity": 0.75,
        },
      });
      map.addLayer({
        id: "supply-facilities",
        type: "circle",
        source: "supply-chain",
        filter: [
          "all",
          ["!", ["has", "point_count"]],
          ["==", ["get", "precision"], "exact_facility"],
        ],
        paint: {
          "circle-color": "#087ea4",
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 5, 8, 9],
          "circle-stroke-width": 2.5,
          "circle-stroke-color": "#09080f",
          "circle-opacity": 0.95,
        },
      });
      map.on("click", "conflict-clusters", async (event) => {
        const feature = event.features?.[0];
        const clusterId = Number(feature?.properties?.cluster_id);
        const source = map.getSource("conflicts") as GeoJSONSource;
        const zoom = await source.getClusterExpansionZoom(clusterId);
        const coordinates = (feature?.geometry as GeoJSON.Point)
          .coordinates as [number, number];
        map.easeTo({ center: coordinates, zoom });
      });
      map.on("click", "supply-clusters", async (event) => {
        const feature = event.features?.[0];
        const clusterId = Number(feature?.properties?.cluster_id);
        const source = map.getSource("supply-chain") as GeoJSONSource;
        const zoom = await source.getClusterExpansionZoom(clusterId);
        const coordinates = (feature?.geometry as GeoJSON.Point)
          .coordinates as [number, number];
        map.easeTo({ center: coordinates, zoom });
      });
      map.on("click", "conflict-points", (event) => {
        const id = String(event.features?.[0]?.properties?.id ?? "");
        if (!eventsByIdRef.current.has(id)) return;
        setSupplySelected(null);
        setEconomicSelected(null);
        setSelectedId(id);
        if (window.matchMedia("(max-width: 900px)").matches)
          setMobilePanel("detail");
      });
      for (const layer of ["supply-regions", "supply-facilities"]) {
        map.on("click", layer, (event) => {
          const id = Number(event.features?.[0]?.properties?.id);
          const site = supplyByIdRef.current.get(id);
          if (!site) return;
          setEconomicSelected(null);
          setSupplySelected(site);
          if (window.matchMedia("(max-width: 900px)").matches)
            setMobilePanel("detail");
        });
      }
      for (const layer of [
        "conflict-clusters",
        "conflict-points",
        "supply-clusters",
        "supply-regions",
        "supply-facilities",
      ]) {
        map.on("mouseenter", layer, () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", layer, () => {
          map.getCanvas().style.cursor = "";
        });
      }
      setMapLoadState("ready");
      setClientLoadMetrics((current) => ({
        ...current,
        mapEngine: {
          status: "ready",
          durationMs: Math.round(performance.now() - startedAt),
          observedAt: new Date().toISOString(),
          detail: "MapLibre + base style",
        },
      }));
      setMapReady((value) => value + 1);
    });
    mapRef.current = map;
        })
        .catch((error: Error) => {
          if (disposed) return;
          setMapLoadState("error");
          setMapLoadError(error.message || "Map engine failed to load");
          setClientLoadMetrics((current) => ({
            ...current,
            mapEngine: {
              status: "error",
              durationMs: Math.round(performance.now() - startedAt),
              observedAt: new Date().toISOString(),
              detail: error.message || "Map engine failed to load",
            },
          }));
        });
    }, 120);
    return () => {
      disposed = true;
      window.clearTimeout(bootTimer);
      economicMarkersRef.current.forEach((marker) => marker.remove());
      economicMarkersRef.current = [];
      activeMap?.remove();
      if (mapRef.current === activeMap) mapRef.current = null;
    };
  }, [mapBootNonce, tab]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const source = map.getSource("conflicts") as GeoJSONSource | undefined;
    if (!source) return;
    source.setData({
      type: "FeatureCollection",
      features: visibleEvents.map((item) => ({
        type: "Feature",
        id: item.id,
        geometry: { type: "Point", coordinates: item.coordinates },
        properties: { id: item.id, severity: item.severity, title: item.title },
      })),
    });
    for (const layer of [
      "conflict-clusters",
      "conflict-cluster-count",
      "conflict-points",
    ]) {
      if (map.getLayer(layer))
        map.setLayoutProperty(
          layer,
          "visibility",
          conflictEnabled ? "visible" : "none",
        );
    }
    if (map.getLayer("conflict-points"))
      map.setPaintProperty(
        "conflict-points",
        "circle-color",
        severityEnabled
          ? [
              "step",
              ["get", "severity"],
              "#f6c85f",
              36,
              "#ff9f43",
              55,
              "#ff4d4f",
            ]
          : "#19735c",
      );
    if (map.getLayer("conflict-clusters"))
      map.setPaintProperty(
        "conflict-clusters",
        "circle-color",
        severityEnabled
          ? [
              "step",
              ["get", "severityMax"],
              "#f6c85f",
              36,
              "#ff9f43",
              55,
              "#ff4d4f",
            ]
          : "#19735c",
      );
  }, [conflictEnabled, mapReady, severityEnabled, visibleEvents]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const source = map.getSource("supply-chain") as GeoJSONSource | undefined;
    if (!source) return;
    source.setData({
      type: "FeatureCollection",
      features: visibleSupplySites.map((item) => ({
        type: "Feature",
        id: item.siteId,
        geometry: { type: "Point", coordinates: item.coordinates },
        properties: {
          id: item.siteId,
          precision: item.coordinatePrecision,
          attention: item.exposureAttentionScore,
          name: item.siteName,
          ticker: item.relatedTicker,
        },
      })),
    });
    for (const layer of [
      "supply-clusters",
      "supply-cluster-count",
      "supply-regions",
      "supply-facilities",
    ]) {
      if (map.getLayer(layer))
        map.setLayoutProperty(
          layer,
          "visibility",
          supplyEnabled ? "visible" : "none",
        );
    }
  }, [mapReady, supplyEnabled, visibleSupplySites]);
  useEffect(() => {
    const map = mapRef.current;
    const maplibregl = maplibreRef.current;
    if (!map || !maplibregl) return;
    economicMarkersRef.current.forEach((marker) => marker.remove());
    economicMarkersRef.current = [];
    if (!economyEnabled) return;
    economicMarkersRef.current = economicData.map((item) => {
      const element = document.createElement("button");
      element.className = "economic-marker";
      element.textContent = `${formatEconomic(item.value, item.unit)} · ${item.date}`;
      element.setAttribute(
        "aria-label",
        `${item.country} ${formatEconomic(item.value, item.unit)}`,
      );
      element.addEventListener("click", () => {
        setSupplySelected(null);
        setEconomicSelected(item);
        if (window.matchMedia("(max-width: 900px)").matches)
          setMobilePanel("detail");
      });
      return new maplibregl.Marker({ element, anchor: "bottom" })
        .setLngLat(item.coordinates)
        .addTo(map);
    });
  }, [economicData, economyEnabled, mapReady, tab]);
  useEffect(() => {
    const resize = () => mapRef.current?.resize();
    const container=workspaceRef.current?.querySelector('.map-stage');
    const observer=container?new ResizeObserver(resize):null;
    if(container)observer?.observe(container);
    window.addEventListener("resize", resize);
    const timer = window.setTimeout(resize, 180);
    return () => {
      window.removeEventListener("resize", resize);
      window.clearTimeout(timer);
      observer?.disconnect();
    };
  }, [mobilePanel, tab]);

  function focusEvent(item: EventItem) {
    setSupplySelected(null);
    setEconomicSelected(null);
    setSelectedId(item.id);
    mapRef.current?.flyTo({
      center: item.coordinates,
      zoom: 5.2,
      duration: 900,
    });
    if (window.matchMedia("(max-width: 900px)").matches)
      setMobilePanel("detail");
  }
  function changeTab(nextTab: Tab) {
    if (nextTab !== "map") {
      setMapLoadState("idle");
      setMapLoadError("");
    }
    if (nextTab !== "evidence") {
      reportLoadSequenceRef.current += 1;
      comparisonLoadSequenceRef.current += 1;
      reportAbortRef.current?.abort();
      comparisonAbortRef.current?.abort();
      setReport(null);
      setComparisonDetail(null);
      setReportDetailLoading(false);
      setComparisonDetailLoading(false);
    }
    setTab(nextTab);
  }
  function focusSupplySite(item: SupplyChainSite) {
    setEconomicSelected(null);
    setSupplySelected(item);
    mapRef.current?.flyTo({
      center: item.coordinates,
      zoom: item.coordinatePrecision === "exact_facility" ? 8 : 5.4,
      duration: 900,
    });
    if (window.matchMedia("(max-width: 900px)").matches)
      setMobilePanel("detail");
  }
  function selectLocalReport(item: EvidenceReport) {
    setReport(item);
    setReportVersion(item.id);
  }
  function stageLocalReport(reportId: string) {
    reportLoadSequenceRef.current += 1;
    reportAbortRef.current?.abort();
    setReportVersion(reportId);
    setReport(null);
    setReportDetailLoading(false);
    setReportDetailError("");
    setReportFilterNotice(
      language === "zh"
        ? "已选择报告；点击“确定并查看”后才会载入正文。"
        : "Report selected; its body will load only after Apply and view.",
    );
  }
  async function loadLocalReport(item: ReportIndexItem) {
    const sequence = ++reportLoadSequenceRef.current;
    reportAbortRef.current?.abort();
    const controller = new AbortController();
    reportAbortRef.current = controller;
    setReportVersion(item.id);
    setReport(null);
    setReportDetailLoading(true);
    setReportDetailError("");
    const startedAt = performance.now();
    try {
      const response = await fetch(
        `/api/research-report?id=${encodeURIComponent(item.id)}`,
        { credentials: "same-origin", signal: controller.signal },
      );
      const { payload, bytes } = await readJsonWithSize<{
        report?: EvidenceReport;
      }>(response);
      if (!payload.report) throw new Error("report detail missing");
      if (sequence !== reportLoadSequenceRef.current) return;
      selectLocalReport(payload.report);
      setClientLoadMetrics((current) => ({
        ...current,
        reportDetail: {
          status: "ready",
          durationMs: Math.round(performance.now() - startedAt),
          bytes,
          records: 1,
          observedAt: new Date().toISOString(),
          detail: payload.report?.ticker || payload.report?.companyName,
        },
      }));
      setReportFilterNotice(
        language === "zh"
          ? `已载入 ${payload.report.ticker || payload.report.companyName || "所选"} 的报告。`
          : `Loaded the selected ${payload.report.ticker || payload.report.companyName || "company"} report.`,
      );
    } catch (error) {
      if (sequence !== reportLoadSequenceRef.current) return;
      if (error instanceof DOMException && error.name === "AbortError") return;
      setClientLoadMetrics((current) => ({
        ...current,
        reportDetail: {
          status: "error",
          durationMs: Math.round(performance.now() - startedAt),
          observedAt: new Date().toISOString(),
          detail: error instanceof Error ? error.message : "report detail",
        },
      }));
      setReportDetailError(
        error instanceof Error && error.message.includes("Access required")
          ? error.message
          : language === "zh"
          ? "报告正文加载失败。请确认仍处于登录状态，然后点击重试。"
          : "The report body failed to load. Confirm you are still signed in, then retry.",
      );
    } finally {
      if (sequence === reportLoadSequenceRef.current)
        setReportDetailLoading(false);
    }
  }
  async function loadComparisonReport(item: ReportIndexItem) {
    const sequence = ++comparisonLoadSequenceRef.current;
    comparisonAbortRef.current?.abort();
    const controller = new AbortController();
    comparisonAbortRef.current = controller;
    setComparisonReportId(item.id);
    setComparisonDetailLoading(true);
    setComparisonDetailError("");
    try {
      const response = await fetch(
        `/api/research-report?id=${encodeURIComponent(item.id)}`,
        { credentials: "same-origin", signal: controller.signal },
      );
      if (!response.ok) throw new Error(`comparison detail ${response.status}`);
      const payload = (await response.json()) as { report?: EvidenceReport };
      if (!payload.report?.competitorComparison)
        throw new Error("comparison detail missing");
      if (sequence !== comparisonLoadSequenceRef.current) return;
      setComparisonDetail(payload.report);
    } catch (error) {
      if (sequence !== comparisonLoadSequenceRef.current) return;
      if (error instanceof DOMException && error.name === "AbortError") return;
      setComparisonDetailError(
        language === "zh"
          ? "横向报告加载失败，请点击重试。"
          : "The comparison failed to load. Tap retry.",
      );
    } finally {
      if (sequence === comparisonLoadSequenceRef.current)
        setComparisonDetailLoading(false);
    }
  }
  function setReportWindow(days: number | null) {
    setReportFilterNotice("");
    if (days == null) {
      setReportFrom("");
      setReportTo("");
      return;
    }
    const end = new Date();
    const start = new Date(end.getTime() - days * dayMs);
    setReportFrom(start.toISOString().slice(0, 10));
    setReportTo(end.toISOString().slice(0, 10));
  }
  function applyReportFilters() {
    if (reportFrom && reportTo && reportFrom > reportTo) {
      setReportFilterNotice(
        language === "zh"
          ? "起始日期不能晚于结束日期。"
          : "The start date cannot be later than the end date.",
      );
      return;
    }
    setAppliedDateBasis(dateBasis);
    setAppliedReportMarket(reportMarket);
    setAppliedReportCompany(reportCompany);
    setAppliedReportFrom(reportFrom);
    setAppliedReportTo(reportTo);
    const nextReport =
      reportVersionOptions.find((item) => item.id === reportVersion) ??
      reportVersionOptions[0];
    if (nextReport) {
      setReportFilterNotice(
        language === "zh"
          ? "正在载入所选报告正文…"
          : "Loading the selected report body…",
      );
      void loadLocalReport(nextReport);
    } else {
      setReportFilterNotice(
        language === "zh"
          ? "所选条件内没有已完成报告，请调整时间或公司。"
          : "No completed report matches these filters. Adjust the date or company.",
      );
    }
  }
  const statusLabel = (status: ChainStep["status"]) =>
    status === "verified"
      ? t.verified
      : status === "partial"
        ? t.partial
        : t.missing;
  const secTypeLabel = (type: string) =>
    type === "cash_consideration_per_share"
      ? t.secFinalCash
      : type === "historical_offer_per_share"
        ? t.secHistorical
        : type === "implied_stock_consideration_per_share"
          ? t.secImplied
          : type === "share_exchange_ratio"
            ? t.secRatio
            : type;
  const secFactorMessage = (candidate: SecEvidenceCandidate) =>
    candidate.factorEligible
      ? t.secFactorReady
      : candidate.factorBlockReason === "terminal_outcome_already_verified"
        ? t.secAlreadyVerified
        : candidate.factorBlockReason === "price_series_not_ready"
          ? t.secPricePending
          : t.secIdentityConflict;
  const metricValues = [
    formatCount(manifest?.localTotals.geolocatedEvents),
    formatCount(manifest?.remoteSnapshot.conflictRecords),
    formatCount(manifest?.remoteSnapshot.newsIndexRecords),
    formatCount(manifest?.remoteSnapshot.contentReadyArticles),
    formatCount(manifest?.localTotals.headlineOnlyDiscovery),
    formatCount(manifest?.localTotals.acledRepresentedEvents),
  ];
  const clientMetricRows = [
    {
      key: "mapEngine",
      zh: "地图引擎与底图",
      en: "Map engine and base style",
    },
    {
      key: "conflicts",
      zh: "当前时间范围事件",
      en: "Current conflict window",
    },
    {
      key: "supplyChain",
      zh: "供应链点位",
      en: "Supply-chain sites",
    },
    {
      key: "reportIndex",
      zh: "报告轻量索引",
      en: "Lightweight report index",
    },
    {
      key: "reportDetail",
      zh: "最近选择的报告正文",
      en: "Last selected report body",
    },
  ].map((definition) => ({
    ...definition,
    metric: clientLoadMetrics[definition.key],
  }));

  function renderMapRow(row: MapListItem) {
    if (row.kind === "event") {
      const item = row.item;
      return (
        <button
          className={`event-card ${selectedId === item.id && !economicSelected && !supplySelected ? "selected" : ""}`}
          onClick={() => focusEvent(item)}
        >
          <span className="event-card-top">
            <b>{item.location}</b>
            <time>{item.date}</time>
          </span>
          <span className="event-title">{item.title}</span>
          <span className="event-meta">
            <i style={{ background: severityColor(item.severity) }} /> {item.country} ·{" "}
            {item.confidence}%
          </span>
          <ChevronRight size={16} />
        </button>
      );
    }
    const item = row.item;
    return (
      <button
        className={`event-card supply-card ${supplySelected?.siteId === item.siteId ? "selected" : ""}`}
        onClick={() => focusSupplySite(item)}
      >
        <span className="event-card-top">
          <b>{item.siteName}</b>
          <time>{item.relatedTicker || item.subjectTicker}</time>
        </span>
        <span className="event-title">{item.relatedCompanyName}</span>
        <span className="event-meta">
          <i
            className={
              item.coordinatePrecision === "exact_facility" ? "exact" : "region"
            }
          />{" "}
          {item.countryIso2} ·{" "}
          {item.coordinatePrecision === "exact_facility"
            ? t.exactFacility
            : t.regionalReference}
        </span>
        <ChevronRight size={16} />
      </button>
    );
  }
  const eventList =
    mapListItems.length > 0 ? (
      <VirtualList
        items={mapListItems}
        itemHeight={101}
        className="virtual-map-list"
        getKey={(row) =>
          row.kind === "event" ? `e:${row.item.id}` : `s:${row.item.siteId}`
        }
        renderItem={renderMapRow}
      />
    ) : (
      <div className="empty-state">
        <CircleAlert size={22} />
        {dataLoading || supplyLoading ? t.loadingData : t.noEvents}
      </div>
    );
  const layerControls = (
    <div className="layer-controls">
      <p>{t.layerHelp}</p>
      <MapChains map={mapRef.current} ready={mapReady} language={language} data={mapChainData} error={mapChainError} selected={mapChainSelection} setSelected={setMapChainSelection} view={mapChainView} setView={setMapChainView}/>
      <label className="toggle-row">
        <span>
          <i className="layer-dot" />
          {language==='zh'?'事件图层总开关':'Event layers'}
        </span>
        <input
          type="checkbox"
          checked={conflictEnabled}
          onChange={(event) => setConflictEnabled(event.target.checked)}
        />
      </label>
      <label className="toggle-row"><span>{language==='zh'?'战争与冲突':'War & conflict'}</span><input type="checkbox" disabled={!conflictEnabled} checked={warEventsEnabled} onChange={e=>setWarEventsEnabled(e.target.checked)}/></label>
      <label className="toggle-row"><span>{language==='zh'?'NASA 热异常（不是战争证据）':'NASA thermal anomalies (not conflict evidence)'}</span><input type="checkbox" disabled={!conflictEnabled} checked={thermalEventsEnabled} onChange={e=>setThermalEventsEnabled(e.target.checked)}/></label>
      <label className={`toggle-row ${!conflictEnabled ? "disabled" : ""}`}>
        <span>
          <i className="severity-swatch" />
          {t.colorSeverity}
        </span>
        <input
          type="checkbox"
          checked={severityEnabled}
          disabled={!conflictEnabled}
          onChange={(event) => setSeverityEnabled(event.target.checked)}
        />
      </label>
      <label className="toggle-row">
        <span>
          <i className="supply-swatch" />
          {t.showSupplyChain}
        </span>
        <input
          type="checkbox"
          checked={supplyEnabled}
          onChange={(event) => {
            const checked = event.target.checked;
            setSupplyEnabled(checked);
            if (checked) setSupplyError("");
          }}
        />
      </label>
      <div
        className={`layer-inline-status ${!supplyEnabled ? "disabled" : ""}`}
      >
        <small>
          {supplyLoading
            ? t.loadingSupply
            : supplyError ||
              `${formatCount(visibleSupplySites.length)} ${t.supplyChain} · ${formatCount(supplySnapshot?.summaries.reduce((total, item) => total + item.exactFacilityCount, 0))} ${t.exactFacility}`}
        </small>
        <p>{t.supplyHelp}</p>
      </div>
      <label className="toggle-row">
        <span>
          <i className="economy-swatch" />
          {t.economy}
        </span>
        <input
          type="checkbox"
          checked={economyEnabled}
          onChange={(event) => {
            setEconomyEnabled(event.target.checked);
            if (event.target.checked) setEconomicLoading(true);
          }}
        />
      </label>
      <div className={`indicator-picker ${!economyEnabled ? "disabled" : ""}`}>
        <select
          aria-label={t.economy}
          value={economicIndicator}
          disabled={!economyEnabled}
          onChange={(event) => {
            setEconomicLoading(true);
            setEconomicIndicator(event.target.value);
          }}
        >
          {economicIndicators.map((item) => (
            <option value={item.code} key={item.code}>
              {language === "zh" ? item.zh : item.en}
            </option>
          ))}
        </select>
        <small>{economicLoading ? t.loadingEconomy : economicError || t.economyHelp}</small>
        {economyEnabled&&<><p>{language==='zh'?`显示截至 ${cursorDate.getUTCFullYear()} 年的最近年度观测；不是周度数据或当时发布版本。各标记含观测年份。`:`Latest annual observations through ${cursorDate.getUTCFullYear()}, not weekly data or historical publication vintages. Each marker shows its year.`}</p><small>{economicData.length} {language==='zh'?'个国家有值；无值不代表零':'countries with values; missing is not zero'}</small><button type="button" onClick={()=>setEconomicRetry(x=>x+1)} disabled={economicLoading}>{language==='zh'?'重试加载指标':'Retry indicator'}</button></>}
      </div>
      <div className="mobile-time-control">
        <span>{t.filters}</span>
        <div className="window-switcher">
          {(Object.keys(t.windows) as WindowKey[]).map((key) => (
            <button
              key={key}
              onClick={() => setWindowKey(key)}
              className={windowKey === key ? "active" : ""}
            >
              {t.windows[key]}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
  const selectedDetails = supplySelected ? (
    <div className="selected-details supply-detail">
      <div className="eyebrow">
        <Factory size={14} />
        {t.supplyChain}
      </div>
      <div
        className={`precision-badge ${supplySelected.coordinatePrecision === "exact_facility" ? "exact" : "regional"}`}
      >
        {supplySelected.coordinatePrecision === "exact_facility"
          ? t.exactFacility
          : t.regionalReference}
      </div>
      <h1>{supplySelected.siteName}</h1>
      <p className="detail-title">
        {supplySelected.relatedCompanyName}
        {supplySelected.relatedTicker
          ? ` · ${supplySelected.relatedTicker}`
          : ""}
      </p>
      <p className="detail-summary">{supplySelected.sourceExcerpt}</p>
      <div className="supply-risk-grid">
        <div>
          <span>{t.nearbyConflict}</span>
          <b>{formatCount(supplySelected.conflictEvents)}</b>
        </div>
        <div>
          <span>{t.nearbyDisaster}</span>
          <b>{formatCount(supplySelected.disasterEventCount)}</b>
        </div>
        <div>
          <span>{t.powerSignals}</span>
          <b>{formatCount(supplySelected.powerSignalCount)}</b>
        </div>
      </div>
      <dl className="event-facts">
        <div>
          <dt>{t.facilityRole}</dt>
          <dd>
            {supplySelected.facilityRole === "company_facility"
              ? `${supplySelected.relatedTicker || supplySelected.contextTicker} · ${t.companyFacility}`
              : `${supplySelected.subjectTicker} → ${supplySelected.relatedTicker || "—"} · ${t.upstreamSupplierLocation}`}
          </dd>
        </div>
        <div>
          <dt>Location</dt>
          <dd>
            {supplySelected.admin1Name || supplySelected.countryName} ·{" "}
            {supplySelected.coordinates[1].toFixed(3)},{" "}
            {supplySelected.coordinates[0].toFixed(3)}
          </dd>
        </div>
        <div>
          <dt>{t.exposureWindow}</dt>
          <dd>
            {supplySelected.periodStart} — {supplySelected.periodEnd}
          </dd>
        </div>
        {supplySelected.nearestPort?.name && (
          <div>
            <dt>{t.nearestPort}</dt>
            <dd>
              <Anchor size={11} />
              {supplySelected.nearestPort.name} ·{" "}
              {Number(supplySelected.nearestPort.distance_km ?? 0).toFixed(1)}{" "}
              km
            </dd>
          </div>
        )}
        <div>
          <dt>{t.source}</dt>
          <dd>
            {supplySelected.sourceUrl ? (
              <a
                href={supplySelected.sourceUrl}
                target="_blank"
                rel="noreferrer"
              >
                {language === "zh" ? "打开原始来源" : "Open source"}
                <ExternalLink size={11} />
              </a>
            ) : (
              "—"
            )}
          </dd>
        </div>
      </dl>
      <div className="source-note">
        <CircleAlert size={15} />
        {supplySelected.facilityRole === "company_facility"
          ? language === "zh"
            ? "该设施已由公司官方资料确认；尚未证明该地点承担特定客户的产能。"
            : "Company sources confirm this facility; customer-specific production is not yet proven."
          : supplySelected.associationScope ===
              "supplier_facility_not_customer_linked"
            ? language === "zh"
              ? "该地点已被供应商官方确认，但尚未证明它专门向所选客户供货。"
              : "The supplier confirms this facility, but customer-specific production is not yet proven."
            : t.supplyHelp}
      </div>
    </div>
  ) : economicSelected ? (
    <div className="selected-details economic-detail">
      <div className="eyebrow">
        <Activity size={14} />
        {t.economy}
      </div>
      <h1>{economicSelected.country}</h1>
      <p className="economic-value">
        {formatEconomic(economicSelected.value, economicSelected.unit)}
      </p>
      <p className="detail-title">
        {
          economicIndicators.find((item) => item.code === economicIndicator)?.[
            language === "zh" ? "zh" : "en"
          ]
        }
      </p>
      <dl className="event-facts">
        <div>
          <dt>{t.source}</dt>
          <dd>World Bank</dd>
        </div>
        <div>
          <dt>Year</dt>
          <dd>{economicSelected.date}</dd>
        </div>
        <div>
          <dt>Indicator</dt>
          <dd>{economicSelected.indicator}</dd>
        </div>
      </dl>
      <div className="source-note">
        <CircleAlert size={15} />
        {t.economyHelp}
      </div>
    </div>
  ) : (
    <div className="selected-details">
      <div className="eyebrow">
        <ShieldCheck size={14} />
        {t.selected}
      </div>
      <h1>{selected.location}</h1>
      <p className="detail-title">{selected.title}</p>
      <p className="detail-summary">{selected.summary}</p>
      <div className="score-row">
        <div>
          <span>{t.severity}</span>
          <b style={{ color: severityColor(selected.severity) }}>
            {selected.severity}%
          </b>
        </div>
        <div>
          <span>{t.confidence}</span>
          <b>{selected.confidence}%</b>
        </div>
      </div>
      <div className="confidence-bar">
        <i style={{ width: `${selected.confidence}%` }} />
      </div>
      <dl className="event-facts">
        <div>
          <dt>{t.source}</dt>
          <dd>{selected.source}</dd>
        </div>
        <div>
          <dt>Event ID</dt>
          <dd>#{selected.id}</dd>
        </div>
        <div>
          <dt>Location</dt>
          <dd>
            {selected.coordinates[1].toFixed(3)},{" "}
            {selected.coordinates[0].toFixed(3)}
          </dd>
        </div>
      </dl>
      <div className="source-note">
        <CircleAlert size={15} />
        {language === "zh"
          ? "位置表示历史报告地点，不表示实时部队位置。"
          : "Location reflects a historical report, not a live troop position."}
      </div>
    </div>
  );

  return (
    <main ref={workspaceRef} className="app-shell" data-report-theme={reportTheme} data-active-tab={tab}>
      <header className="topbar">
        <a
          className="brand"
          href="/"
          aria-label="ORAKT official website"
          target="_top"
        >
          <span className="brand-mark">
            <OraktBrandIcon size={32}/>
          </span>
          <span>
            <b>ORAKT</b>
            <i>WORLD</i>
          </span>
        </a>
        <nav className="tabs" aria-label="Primary navigation">
          {([
            ['map',MapPin,'事件地图','Event map'],
            ['evidence',BrainCircuit,'证据报告','Evidence reports'],
            ['alpha',Activity,'Alpha 因子','Alpha factors'],
            ['portfolio',Layers3,'组合实验室','Portfolio lab'],
            ['intelligence',Newspaper,'情报市场','Intelligence market'],
            ['assets',Layers3,'链上资产','On-chain assets'],
            ['markets',Activity,'市场行情','Markets'],
            ['data',Database,'研究资料库','Research library'],
            ['chains',Activity,'证据链推演','Evidence chains'],
            ['personal',BrainCircuit,'询问 ORAKT','Ask ORAKT'],
          ] as const).map(([item,Icon,zh,en]) => (
            <button
              key={item}
              className={tab === item || (item === "evidence" && tab === "sec") ? "active" : ""}
              onClick={() => changeTab(item)}
            >
              <Icon size={16} aria-hidden="true"/><span>{language==='zh'?zh:en}</span>
            </button>
          ))}
        </nav>
        <div className="top-actions">
          <button className="theme-toggle" type="button" aria-label={language==="zh"?"切换全局明暗主题":"Toggle workspace appearance"} title={language==="zh"?"切换明暗":"Toggle appearance"} onClick={()=>chooseReportTheme(reportTheme==="dark"?"light":"dark")}>{reportTheme==="dark"?<Sun size={17}/>:<Moon size={17}/>}<span>{language==="zh"?(reportTheme==="dark"?"浅色":"深色"):(reportTheme==="dark"?"Light":"Dark")}</span></button>
          <a className="home-return" href="/" target="_top">{language === "zh" ? "返回官网" : "Home"}</a>
          <a className="privacy-pill" href="/account" aria-label="Account center">
            <LockKeyhole size={13} />
            {language === "zh" ? "账户" : "Account"}
          </a>
          <button
            className="language"
            onClick={() => setLanguage(language === "zh" ? "en" : "zh")}
          >
            <Languages size={15} />
            {language === "zh" ? "EN" : "中文"}
          </button>
        </div>
      </header>
      <section className="status-strip">
        <span>
          <Radio size={13} /> {t.snapshot} ·{" "}
          {manifest
            ? new Date(manifest.generatedAt).toLocaleString(
                language === "zh" ? "zh-CN" : "en-CA",
              )
            : (language === "zh" ? "时间见各数据源" : "See individual sources")}
        </span>
        <span>{t.readonly}</span>
        <span>{t.disclaimer}</span>
        <ReleaseStatus language={language}/>
      </section>
      {tab === "map" && (
        <section className="map-workspace">
          <aside className="event-rail">
            <label className="search-box">
              <Search size={16} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t.search}
              />
            </label>
            <div className="filter-label">{t.filters}</div>
            <div className="window-switcher">
              {(Object.keys(t.windows) as WindowKey[]).map((key) => (
                <button
                  key={key}
                  onClick={() => setWindowKey(key)}
                  className={windowKey === key ? "active" : ""}
                >
                  {t.windows[key]}
                </button>
              ))}
            </div>
            <div className="desktop-layer-controls">
              <div className="layer-row">
                <span>
                  <i className="layer-dot" />
                  {t.conflict}
                </span>
                <b>
                  {conflictEnabled ? formatCount(visibleEvents.length) : 0}{" "}
                  {t.eventCount}
                </b>
              </div>
              {layerControls}
            </div>
            <small className="list-cap-note">
              {language === "zh"
                ? `视口渲染 · 共 ${formatCount(mapListItems.length)} 条，滚动时按需绘制`
                : `Viewport rendered · ${formatCount(mapListItems.length)} rows, drawn on scroll`}
            </small>
            <div className="event-list">{eventList}</div>
          </aside>
          <div className="map-stage">
            <div ref={mapContainer} className="map-canvas" />
            {mapChainSelection.includes('apple-network')&&<div className="apple-map-hud"><b>AAPL / GLOBAL SUPPLY ATLAS</b><span>{language==='zh'?'187 家供应商 · 603 条可定位记录 · 参考路线':'187 suppliers · 603 located records · reference routes'}</span><a href="/platform/chains?chain=apple-network">{language==='zh'?'完整研究':'Full study'} ↗</a></div>}
            {mapChainSelection.includes('hormuz-helium')&&!mapChainSelection.includes('apple-network')&&<div className="apple-map-hud hormuz-map-hud"><b>HORMUZ → He → SEMICONDUCTORS</b><span>{language==='zh'?'青：氦气 · 橙：能源 · 绿：缓冲 / 虚线：推演，非实时货运':'Cyan: helium · amber: energy · lime: buffers / dashed: hypotheses, not live cargo'}</span><a href="/platform/chains?chain=hormuz-helium">{language==='zh'?'完整报告与投资设想':'Full study & investment hypotheses'} ↗</a></div>}
            {mapLoadState !== "ready" && (
              <div
                className={`map-boot-status ${mapLoadState === "error" ? "is-error" : ""}`}
                role={mapLoadState === "error" ? "alert" : "status"}
              >
                {mapLoadState === "error" ? (
                  <CircleAlert size={22} />
                ) : (
                  <LoaderCircle className="spin" size={22} />
                )}
                <b>
                  {mapLoadState === "error"
                    ? language === "zh"
                      ? "地图加载失败"
                      : "Map failed to load"
                    : language === "zh"
                      ? "正在分阶段加载地图"
                      : "Loading map in stages"}
                </b>
                <span>
                  {mapLoadState === "error"
                    ? language === "zh"
                      ? "可单独重试地图，不会重新载入整个页面。"
                      : "Retry the map without reloading the whole page."
                    : language === "zh"
                      ? "地图就绪后再载入所选时间范围的事件。"
                      : "Events load after the map is ready."}
                </span>
                {mapLoadState === "error" && (
                  <>
                    {mapLoadError && <small>{mapLoadError}</small>}
                    <button
                      type="button"
                      onClick={() => setMapBootNonce((value) => value + 1)}
                    >
                      {language === "zh" ? "重试地图" : "Retry map"}
                    </button>
                  </>
                )}
              </div>
            )}
            {((conflictEnabled && severityEnabled) || supplyEnabled) && (
              <div className="map-legend">
                {conflictEnabled && severityEnabled && (
                  <>
                    <span>
                      <i className="low" />
                      {language === "zh" ? "低冲突" : "Low conflict"}
                    </span>
                    <span>
                      <i className="medium" />
                      {language === "zh" ? "中" : "Medium"}
                    </span>
                    <span>
                      <i className="high" />
                      {language === "zh" ? "高" : "High"}
                    </span>
                  </>
                )}
                {supplyEnabled && (
                  <>
                    <span>
                      <i className="facility" />
                      {t.exactFacility}
                    </span>
                    <span>
                      <i className="region" />
                      {t.regionalReference}
                    </span>
                  </>
                )}
              </div>
            )}
            <div className="mobile-map-summary">
              <span>
                <i className={conflictEnabled ? "online" : ""} />
                {t.conflict}
              </span>
              <b>{conflictEnabled ? formatCount(visibleEvents.length) : 0}</b>
              {supplyEnabled && (
                <>
                  <span>
                    <i className="supply-online" />
                    {t.supplyChain}
                  </span>
                  <b>{formatCount(visibleSupplySites.length)}</b>
                </>
              )}
            </div>
            <div className="timeline-control">
              <button
                onClick={() => {
                  if (timelineDay >= timelineMaxDay) setTimelineDay(0);
                  setPlaying(!playing);
                }}
                aria-label={playing ? t.pause : t.play}
              >
                {playing ? <Pause size={15} /> : <Play size={15} />}
              </button>
              <div>
                <span>
                  <Clock3 size={13} />
                  {t.replay}
                  <b>{cursorDateLabel}</b>
                </span>
                <input
                  aria-label={t.replay}
                  type="range"
                  min="0"
                  max={timelineMaxDay}
                  value={Math.min(timelineDay, timelineMaxDay)}
                  onChange={(event) => {
                    setPlaying(false);
                    setTimelineDay(Number(event.target.value));
                  }}
                />
              </div>
            </div>
          </div>
<aside className="detail-panel">{mapChainSelection.includes('apple-network')?<AppleMapInspector active={mapChainView.active} language={language}/>:mapChainSelection.includes('hormuz-helium')?<Suspense fallback={<p>…</p>}><HormuzMapInspector chain={mapChainData?.chains?.find((c:any)=>c.id==='hormuz-helium')} active={mapChainView.active} language={language} onSelect={(n:any)=>setMapChainView((v:any)=>({...v,active:n}))}/></Suspense>:selectedDetails}</aside>
          <div className="mobile-map-dock" aria-label="Map tools">
            <button
              className={mobilePanel === "layers" ? "active" : ""}
              onClick={() =>
                setMobilePanel(mobilePanel === "layers" ? null : "layers")
              }
            >
              <Layers3 size={18} />
              <span>{t.layers}</span>
              <b>
                {Number(conflictEnabled) +
                  Number(economyEnabled) +
                  Number(supplyEnabled)}
              </b>
            </button>
            <button
              className={mobilePanel === "events" ? "active" : ""}
              onClick={() =>
                setMobilePanel(mobilePanel === "events" ? null : "events")
              }
            >
              <ListFilter size={18} />
              <span>{t.events}</span>
              <b>
                {formatCount(
                  (conflictEnabled ? visibleEvents.length : 0) +
                    (supplyEnabled ? visibleSupplySites.length : 0),
                )}
              </b>
            </button>
            <button
              className={mobilePanel === "detail" ? "active" : ""}
              onClick={() =>
                setMobilePanel(mobilePanel === "detail" ? null : "detail")
              }
            >
              <ShieldCheck size={18} />
              <span>{t.detail}</span>
            </button>
          </div>
          {mobilePanel && (
            <section
              className={`mobile-sheet sheet-${mobilePanel}`}
              aria-label={mobilePanel}
            >
              <header>
                <b>
                  {mobilePanel === "layers"
                    ? t.layers
                    : mobilePanel === "events"
                      ? t.events
                      : t.detail}
                </b>
                <button
                  onClick={() => setMobilePanel(null)}
                  aria-label={t.close}
                >
                  <X size={20} />
                </button>
              </header>
              <div className="mobile-sheet-body">
                {mobilePanel === "layers" && layerControls}
                {mobilePanel === "events" && (
                  <>
                    <label className="search-box">
                      <Search size={16} />
                      <input
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        placeholder={t.search}
                      />
                    </label>
                    <small className="list-cap-note">{t.showing}</small>
                    <div className="mobile-event-list">{eventList}</div>
                  </>
                )}
                {mobilePanel === "detail" && (mapChainSelection.includes('apple-network')?<AppleMapInspector active={mapChainView.active} language={language}/>:mapChainSelection.includes('hormuz-helium')?<Suspense fallback={<p>…</p>}><HormuzMapInspector chain={mapChainData?.chains?.find((c:any)=>c.id==='hormuz-helium')} active={mapChainView.active} language={language} onSelect={(n:any)=>setMapChainView((v:any)=>({...v,active:n}))}/></Suspense>:selectedDetails)}
              </div>
            </section>
          )}
        </section>
      )}

      {tab === "evidence" && !accessRights?.reports && <ReportCatalogPreview language={language} ready={Boolean(accessRights)} failed={accessError}/>}
      {(tab === "evidence" || tab === "sec") && accessRights?.reports && (
        <section className="content-page evidence-page">
          <header className="research-workspace-toolbar">
            <div><span className="eyebrow">ORAKT RESEARCH</span><h1>{language === "zh" ? "研究工作台" : "Research workspace"}</h1></div>
            <p>{language==="zh"?"选择研究类型，筛选资料，再展开阅读与核验。":"Choose a research type, filter the library, then read and verify."}</p>
          </header>
          <div
            className="evidence-view-switch"
            role="tablist"
            aria-label={
              language === "zh" ? "报告区域" : "Evidence report areas"
            }
          >
            <button
              type="button"
              role="tab"
              aria-selected={tab === "evidence" && evidenceView === "single"}
              className={tab === "evidence" && evidenceView === "single" ? "active" : ""}
              onClick={() => {changeTab("evidence");setEvidenceView("single");}}
            >
              <FileSearch size={17} />
              <span>
                <b>{language === "zh" ? "单公司报告" : "Company reports"}</b>
                <small>
                  {language === "zh"
                    ? "筛选、选择版本并审核"
                    : "Filter, select and review"}
                </small>
              </span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={evidenceView === "cross"}
              className={evidenceView === "cross" ? "active" : ""}
              onClick={() => {changeTab("evidence");setEvidenceView("cross");}}
            >
              <Activity size={17} />
              <span>
                <b>
                  {language === "zh" ? "宏观事件横向报告" : "Macro-event reports"}
                </b>
                <small>
                  {language === "zh"
                    ? "议息、非农与公司传导"
                    : "FOMC, payrolls & companies"}
                </small>
              </span>
            </button>
            {([['entry', '建仓观察', 'Entry watchlist', '独立价格与证据筛选', 'Price and evidence gates'], ['crypto', '加密市场', 'Crypto markets', '现货报价与日 K 线', 'Spot quotes & daily candles']] as const).map(([key, zh, en, subZh, subEn]) => <button type="button" role="tab" key={key} aria-selected={evidenceView === key} className={evidenceView === key ? "active" : ""} onClick={() => {changeTab("evidence");setEvidenceView(key);}}><Layers3 size={17}/><span><b>{language === "zh" ? zh : en}</b><small>{language === "zh" ? subZh : subEn}</small></span></button>)}
            <button type="button" role="tab" aria-selected={tab==="sec"} className={tab==="sec"?"active":""} onClick={()=>{setEvidenceView("single");changeTab("sec");}}><ShieldCheck size={17}/><span><b>{language==="zh"?"SEC 证据审核":"SEC source review"}</b><small>{language==="zh"?"财报原文与证据核对":"Filings and evidence checks"}</small></span></button>
          </div>
          {tab === "evidence" && evidenceView === "crypto" && <MarketExpansion kind="crypto" language={language}/>}
          {evidenceView === "operations" && <button onClick={()=>changeTab('alpha')}>{language==='zh'?'历史补全已迁至 Alpha 因子专区':'Historical coverage has moved to Alpha Lab'}</button>}
          {tab === "evidence" && evidenceView === "single" && accessRights?.research && <DisclosureReviews language={language}/>}

          {tab === "evidence" && evidenceView === "single" && (
            <>
          <section className="report-filter-bar">
            <CompanyReportCoverage language={language}/>
            <p className="report-category-note">{language==='zh'?`单公司财报研究：${allLocalReports.filter(isCompanyReport).length} 份，统一按财务期间与九章模板查阅。旧版五维／多维研究已归入证据链，历史尚未全部补齐。`:`Periodic company research: ${allLocalReports.filter(isCompanyReport).length} reports using a nine-chapter template. Legacy multidimensional research is in Evidence chains; historical coverage is incomplete.`} <a href="/platform/chains">{language==='zh'?'查看五维研究完整报告 →':'Read legacy research reports →'}</a></p>
            <label className="report-date-basis"><span>{language==="zh"?"筛选日期口径":"Date basis"}</span><select value={dateBasis} onChange={e=>setDateBasis(e.target.value)}><option value="generated">{language==="zh"?"报告生成日期":"Generated date"}</option><option value="evidence">{language==="zh"?"证据截止日期":"Evidence cutoff"}</option></select></label>
            <header>
              <div>
                <span className="eyebrow">
                  <ListFilter size={14} />
                  {language === "zh" ? "报告筛选器" : "Report filters"}
                </span>
                <h2>
                  {language === "zh"
                    ? "按时间、市场与公司查找报告"
                    : "Find reports by time, market and company"}
                </h2>
              </div>
              <b>
                {equityCatalog?.companies.length ??
                  manifest?.remoteSnapshot.activeChinaSectorLeaders ??
                  0}
                <small>
                  {language === "zh"
                    ? "家A股/美股龙头已入库"
                    : "A-share and U.S. leaders retained"}
                </small>
              </b>
            </header>
            <p className="watchlist-priority">{language==='zh'?`自选优先 · ${watchedTickers.length} 家公司`:`Watchlist first · ${watchedTickers.length} companies`} · <a href="/account">{language==='zh'?'管理自选':'Edit watchlist'}</a></p>
            <div className="report-filter-grid">
              <label>
                <span>{language === "zh" ? "市场" : "Market"}</span>
                <select
                  aria-label={language === "zh" ? "报告市场" : "Report market"}
                   value={reportMarket}
                   onChange={(event) => {
                     setReportMarket(event.target.value as ReportMarket);
                     setReportCompany("all");
                     setReportFilterNotice("");
                   }}
                >
                  <option value="all">
                    {language === "zh" ? "全部市场" : "All markets"}
                  </option>
                  <option value="china">
                    {language === "zh" ? "A股" : "China A-shares"}
                  </option>
                  <option value="us">
                    {language === "zh" ? "美股" : "U.S. equities"}
                  </option>
                  <option value="global">
                    {language === "zh" ? "宏观/全球" : "Macro / global"}
                  </option>
                </select>
              </label>
              <label>
                <span>{language === "zh" ? "公司" : "Company"}</span>
                <select
                   aria-label={language === "zh" ? "报告公司" : "Report company"}
                   value={reportCompany}
                   onChange={(event) => {
                     setReportCompany(event.target.value);
                     setReportFilterNotice("");
                   }}
                >
                  <option value="all">
                    {language === "zh" ? "全部公司" : "All companies"}
                  </option>
                  {companyOptions.map((item) => (
                    <option value={item.key} key={item.key}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>{language === "zh" ? "起始日期" : "From"}</span>
                <input
                  aria-label={
                    language === "zh" ? "报告起始日期" : "Report start date"
                  }
                   type={language==='en'?'text':'date'} placeholder="YYYY-MM-DD" lang={language==='en'?'en':'zh-CN'} pattern="\d{4}-\d{2}-\d{2}"
                   value={reportFrom}
                   onChange={(event) => {
                     setReportFrom(event.target.value);
                     setReportFilterNotice("");
                   }}
                />
              </label>
              <label>
                <span>{language === "zh" ? "结束日期" : "To"}</span>
                <input
                  aria-label={
                    language === "zh" ? "报告结束日期" : "Report end date"
                  }
                   type={language==='en'?'text':'date'} placeholder="YYYY-MM-DD" lang={language==='en'?'en':'zh-CN'} pattern="\d{4}-\d{2}-\d{2}"
                   value={reportTo}
                   onChange={(event) => {
                     setReportTo(event.target.value);
                     setReportFilterNotice("");
                   }}
                 />
               </label>
               <label className="report-version-field">
                 <span>
                   {language === "zh" ? "报告时间与版本" : "Report date and version"}
                 </span>
                 <select
                   aria-label={
                     language === "zh" ? "选择具体报告" : "Select a report version"
                   }
                   value={visibleReportVersion}
                   disabled={reportVersionOptions.length === 0}
                   onChange={(event) => stageLocalReport(event.target.value)}
                 >
                   {reportVersionOptions.length === 0 ? (
                     <option value="">
                       {language === "zh"
                         ? "当前条件暂无报告"
                         : "No report matches these filters"}
                     </option>
                   ) : (
                     reportVersionOptions.map((item) => (
                       <option value={item.id} key={item.id}>
                         {(dateBasis==='generated'?item.createdAt:reportFilterDate(item,'evidence')||item.createdAt)?.slice(0,10)} · {item.ticker || item.companyName || "GLOBAL"} · #{item.localInquiryId ?? item.id}{item.historical ? ` · ${language==="zh"?"财务期末":"Period end"} ${item.historical.periodEnd}` : ""}
                       </option>
                     ))
                   )}
                 </select>
                 <small>
                   {language === "zh"
                     ? `当前条件内共 ${reportVersionOptions.length} 份，可选择同一公司的不同研究期间和版本。`
                     : `${reportVersionOptions.length} matching reports; choose a specific generation time.`}
                 </small>
               </label>
             </div>
             <div className="report-filter-presets">
              <button type="button" onClick={() => setReportWindow(30)}>
                30D
              </button>
              <button type="button" onClick={() => setReportWindow(90)}>
                90D
              </button>
              <button type="button" onClick={() => setReportWindow(365)}>
                1Y
              </button>
              <button type="button" onClick={() => setReportWindow(null)}>
                {language === "zh" ? "全部时间" : "All time"}
              </button>
               <span>
                 {language === "zh"
                   ? `已应用 ${localReports.length} / ${allLocalReports.length} 份`
                   : `${localReports.length} of ${allLocalReports.length} reports applied`}
               </span>
             </div>
             <div className="report-filter-commit">
               <div aria-live="polite">
                 <b>
                   {language === "zh" ? "选择完成后再载入" : "Load after choosing"}
                 </b>
                 <span>
                   {reportFilterNotice ||
                     (language === "zh"
                       ? "修改市场、公司或时间不会立即清空下面的报告。"
                       : "Changing a field will not clear the current report until confirmed.")}
                 </span>
               </div>
               <button
                 type="button"
                 onClick={applyReportFilters}
                 disabled={!visibleReportVersion || reportDetailLoading}
               >
                 <Check size={16} />
                 {language === "zh" ? "确定并查看" : "Apply and view"}
               </button>
             </div>
           </section>
            </>
          )}
          {evidenceView === "entry" && <section className="entry-watchlist">
            <header>
              <div>
                <span className="eyebrow">
                  <Activity size={14} />
                  {language === "zh"
                    ? "建仓价格观察"
                    : "Entry-price watchlist"}
                </span>
                <h2>
                  {language === "zh"
                    ? "已发布报告中的可复核建仓观察池"
                    : "Reviewable entry zones in published reports"}
                </h2>
                <p>
                  {language === "zh"
                    ? "仅保留本地审计无引用错误、数据日期在最新一周内、接近支撑位、预估盈亏比至少 2:1、下行风险 2%–8.5% 且上行空间至少 6% 的结果。"
                    : "Requires clean local citations, data no more than one week behind the newest market date, proximity to support, at least 2:1 estimated reward/risk, 2%–8.5% downside and at least 6% upside."}
                </p>
              </div>
              <b>
                {entryCandidates.length}
                <small>
                  {language === "zh" ? "当前符合" : "currently eligible"}
                </small>
              </b>
            </header>
            <label className="entry-market-filter"><span>{language === "zh" ? "观察市场" : "Market"}</span><select value={entryMarket} onChange={event => setEntryMarket(event.target.value as "all" | "china" | "us")}><option value="all">{language === "zh" ? "全部股票市场" : "All equities"}</option><option value="china">{language === "zh" ? "A股" : "A-shares"}</option><option value="us">{language === "zh" ? "美股" : "U.S."}</option></select></label>
            <p className="entry-snapshot-note">{language === "zh" ? "按已发布报告截止日筛选，不代表此刻仍在建仓区。查看每项行情日期，并在行动前核对最新价格。" : "Screened as of each published report, not current executable prices. Verify market dates and fresh prices before acting."}</p>
            {entryCandidates.length ? (
              <div className="entry-watch-grid">
                {entryCandidates.map((item) => (
                  <button
                    type="button"
                    key={`${item.marketRegion}:${item.ticker}`}
                    onClick={() => { setReportMarket(item.marketRegion); setReportCompany(`${item.marketRegion}:${item.ticker}`); setReportFrom(""); setReportTo(""); setAppliedReportMarket(item.marketRegion); setAppliedReportCompany(`${item.marketRegion}:${item.ticker}`); setAppliedReportFrom(""); setAppliedReportTo(""); setReportVersion(item.report.id); setEvidenceView("single"); void loadLocalReport(item.report); }}
                  >
                    <header>
                      <span>
                        {item.marketRegion === "china" ? "A股" : "US"}
                      </span>
                      <div>
                        <b>{item.ticker}</b>
                        <small>{item.company}</small>
                      </div>
                      <strong>{item.rankingScore}</strong>
                    </header>
                    <dl>
                      <div>
                        <dt>{language === "zh" ? "观察区间" : "Entry zone"}</dt>
                        <dd>
                          {formatMarketPrice(item.zoneLower, item.marketRegion)} –{" "}
                          {formatMarketPrice(item.zoneUpper, item.marketRegion)}
                        </dd>
                      </div>
                      <div>
                        <dt>{language === "zh" ? "当前参考" : "Current"}</dt>
                        <dd>
                          {formatMarketPrice(item.currentPrice, item.marketRegion)}
                        </dd>
                      </div>
                      <div>
                        <dt>{language === "zh" ? "止损参考" : "Stop reference"}</dt>
                        <dd>
                          {formatMarketPrice(item.stopReference, item.marketRegion)}
                        </dd>
                      </div>
                      <div>
                        <dt>{language === "zh" ? "目标参考" : "Target reference"}</dt>
                        <dd>
                          {formatMarketPrice(item.targetReference, item.marketRegion)}
                        </dd>
                      </div>
                    </dl>
                    <footer>
                      <span>
                        {language === "zh" ? "盈亏比" : "Reward/risk"}{" "}
                        <b>{item.rewardRiskRatio.toFixed(2)}:1</b>
                      </span>
                      <span>
                        {formatMove(item.downsideFraction * -1)} /{" "}
                        {formatMove(item.upsideFraction)}
                      </span>
                      <time>{item.observedOn}</time>
                    </footer>
                  </button>
                ))}
              </div>
            ) : (
              <div className="entry-watch-empty">
                <CircleAlert size={17} />
                <span>
                  {language === "zh"
                    ? "当前已发布数据中没有同时通过证据、价格、风险和时效门槛的股票。新数据发布后重新评估，不放宽门槛填充结果。"
                    : "No stock in the published data passes all gates. Reassessment requires a new data release; thresholds are not relaxed to populate the list."}
                </span>
              </div>
            )}
            <footer>
              <ShieldCheck size={14} />
              <span>
                {language === "zh"
                  ? "观察区由最近支撑位向上延伸半个 ATR（最多 3%）；缺少完整 OHLCV 时使用 2.5%。止损和目标来自报告中的机械情景，不构成个性化投资建议或保证成交价格。"
                  : "The zone extends half an ATR above recent support, capped at 3%; 2.5% is used when full OHLCV is unavailable. Stops and targets are mechanical report scenarios, not personalized advice or guaranteed prices."}
              </span>
            </footer>
          </section>}
          {tab === "evidence" && evidenceView === "single" && (<>
          <div className="desktop-report-shell">
            <aside className="desktop-report-browser">
          <section className="local-report-library">
            <header>
              <div>
                <span className="eyebrow">
                  <Database size={14} />
                  {language === "zh"
                    ? "本地 AI 报告库"
                    : "Local AI report library"}
                </span>
                <h1>
                  {language === "zh"
                    ? "已生成并审计的研究报告"
                    : "Generated and audited research reports"}
                </h1>
                <p>
                  {language === "zh"
                    ? "来自本机 Ollama 的已发布报告，仅供只读查阅；手机端可查看完整报告。公众网站不开放生成与反馈写入。OpenAI 未参与这些报告的本地审计。"
                    : "Published reports from local Ollama, available read-only in full on mobile. Public generation and feedback writes are disabled. OpenAI did not perform these local audits."}
                </p>
              </div>
              <b>
                {localReports.length} {language === "zh" ? "份报告" : "reports"}
              </b>
            </header>
            {localReportsLoading ? (
              <div className="report-library-state">
                <LoaderCircle className="spin" size={17} />
                {language === "zh"
                  ? "正在读取本地报告…"
                  : "Loading local reports…"}
              </div>
            ) : localReportsError ? (
              <div className="report-library-state error">
                <CircleAlert size={17} />
                <span>{localReportsError}</span>
                <button type="button" onClick={() => window.location.reload()}>
                  {language === "zh" ? "重新载入" : "Reload"}
                </button>
              </div>
            ) : localReports.length === 0 ? (
              <div className="report-library-state">
                <CircleAlert size={17} />
                {language === "zh"
                  ? "当前筛选范围没有已完成报告"
                  : "No completed reports match these filters"}
              </div>
            ) : (
              <div className="local-report-list">
                {listedLocalReports.map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    className={reportVersion === item.id ? "active" : ""}
                    aria-pressed={reportVersion === item.id}
                    onClick={() => stageLocalReport(item.id)}
                  >
                    <span>
                      <i>
                        {item.audit?.status === "data_quality_blocked"
                          ? language === "zh"
                            ? "数据受阻"
                            : "Data blocked"
                          : language === "zh"
                            ? "已审计"
                            : "Audited"}
                      </i>
                      {item.localInquiryId && (
                        <small>#{item.localInquiryId}</small>
                      )}
                    </span>
                    <b>{language === 'en' && item.questionEn ? item.questionEn : item.question}</b>
                    <footer>
                      <span>
                        {item.ticker
                          ? `${item.marketRegion === "china" ? "A股" : "US"} · ${item.ticker}`
                          : item.model.replace("ollama:", "")}
                      </span>
                      <time>
                        {reportDisplayDate(item.historical?.periodEnd || item.dataCutoff || item.createdAt, language)}
                      </time>
                    </footer>
                  </button>
                ))}
              </div>
            )}
            {localReports.length > listedLocalReports.length && (
              <small className="list-cap-note">
                {language === "zh"
                  ? `为降低手机内存占用，仅显示前 ${listedLocalReports.length} 份；可先按公司或时间缩小范围。`
                  : `To protect mobile memory, only the first ${listedLocalReports.length} are shown. Narrow the company or date filters to see a specific report.`}
              </small>
            )}
          </section>
            </aside>
            <main className="desktop-report-reader">
              <header className="report-reader-heading">
                <div>
                  <span className="eyebrow">
                    <FileSearch size={14} />
                    {language === "zh" ? "深度报告工作台" : "Research report workspace"}
                  </span>
                  <h2>
                    {report
                      ? `${report.ticker ? `${report.ticker} · ` : ""}${report.companyName || report.question}`
                      : language === "zh"
                        ? "选择一份报告开始阅读"
                        : "Choose a report to begin reading"}
                  </h2>
                  <p>
                    {language === "zh"
                      ? "正文、证据链、评分拆解与数据限制集中在同一阅读区；桌面端目录保持可见。"
                      : "The report body, evidence chain, score breakdown and data limitations stay together while the desktop library remains visible."}
                  </p>
                </div>
                <div className="report-reader-status">
                  <span>
                    {language === "zh" ? "按需载入" : "On-demand"}
                  </span>
                  <b>
                    {report
                      ? (report.confidence == null ? (language === "zh" ? "预测置信度未估计" : "Predictive confidence not estimated") : `${report.confidence}% ${language === "zh" ? "方向支持度" : "directional support"}`)
                      : language === "zh"
                        ? "等待选择"
                        : "Awaiting selection"}
                  </b>
                </div>
              </header>
          <div className="public-readonly-notice">
            <LockKeyhole size={18} />
            <div>
              <b>{language === "zh" ? "公众只读报告库" : "Public read-only report library"}</b>
              <span>
                {language === "zh"
                  ? "本版本仅用于筛选、阅读和核对已发布报告；在线 AI 生成与反馈写入已关闭。"
                  : "This release only filters and reads published reports. Online AI generation and feedback writes are disabled."}
              </span>
            </div>
          </div>
          {reportDetailLoading && (
            <div className="report-detail-state">
              <LoaderCircle className="spin" size={18} />
              <div>
                <b>
                  {language === "zh"
                    ? "正在载入完整报告"
                    : "Loading the full report"}
                </b>
                <span>
                  {language === "zh"
                    ? "目录已经加载，只读取当前选中的一份报告。"
                    : "The index is ready; only the selected report is being downloaded."}
                </span>
              </div>
            </div>
          )}
          {reportDetailError && !reportDetailLoading && (
            <div className="report-detail-state error">
              <CircleAlert size={18} />
              <div>
                <b>{reportDetailError}</b>
                <span>
                  {language === "zh"
                    ? "报告目录仍然可用，不需要重新选择筛选条件。"
                    : "The report index remains available; your filters are preserved."}
                </span>
              </div>
              {reportVersionOptions[0] && (
                <button
                  type="button"
                  onClick={() =>
                    void loadLocalReport(
                      reportVersionOptions.find(
                        (item) => item.id === visibleReportVersion,
                      ) ?? reportVersionOptions[0],
                    )
                  }
                >
                  {language === "zh" ? "重试" : "Retry"}
                </button>
              )}
            </div>
          )}
          {localReports.length > 0 && !report && !reportDetailLoading && !reportDetailError && (
            <div className="report-detail-state">
              <FileSearch size={18} />
              <div>
                <b>
                  {language === "zh"
                    ? "尚未载入报告正文"
                    : "No report body loaded"}
                </b>
                <span>
                  {language === "zh"
                    ? "请选择市场、公司、时间和版本，再点击“确定并查看”。页面一次只载入一份报告。"
                    : "Choose the market, company, date and version, then select Apply and view. Only one report is loaded at a time."}
                </span>
              </div>
            </div>
          )}
          {localReports.length > 0 && report && !reportDetailLoading && (
            <article className="report-paper">
              <header className="report-header">
                <div>
                  <span className="report-kicker">
                    <BrainCircuit size={14} />
                    {report.origin === "local_ollama"
                      ? language === "zh"
                        ? "本地 OLLAMA · 确定性审计"
                        : "LOCAL OLLAMA · DETERMINISTIC AUDIT"
                      : report.analysisMode === "news_first"
                        ? "NEWS-FIRST INTELLIGENCE REPORT"
                        : "AI EVIDENCE REPORT"}
                  </span>
                  <h1>{report.question}</h1>
                  <p>
                    {report.ticker && (
                      <>
                        {report.marketRegion === "china"
                          ? language === "zh"
                            ? "A股"
                            : "China A-share"
                          : language === "zh"
                            ? "美股"
                            : "U.S. equity"}{" "}
                        · {report.ticker}
                        {report.companyName ? ` · ${report.companyName}` : ""}
                        {report.sector ? ` · ${report.sector}` : ""}
                        <br />
                      </>
                    )}
                    {language==='zh'?'研究期间':'Research period'} · {report.historical?.periodEnd || report.dataCutoff || report.createdAt?.slice(0,10)}
                    {report.dataCutoff
                      ? ` · ${language === "zh" ? "数据截止" : "data cutoff"} ${report.dataCutoff}`
                      : ""}
                  </p>
                </div>
                <div
                  className="confidence-ring"
                  style={{
                    background: report.confidence == null ? 'var(--surface)' : `conic-gradient(var(--green) 0 ${report.confidence}%,#e1e6e3 ${report.confidence}% 100%)`,
                  }}
                >
                  <b>{report.confidence == null ? '—' : `${report.confidence}%`}</b>
                  <span>{report.confidence == null ? (language === 'zh' ? '预测置信度未估计' : 'Predictive confidence unestimated') : t.finalConfidence}</span>
                </div>
              </header>
              {report.audit && (
                <section className={`local-audit-strip ${report.audit.status}`}>
                  <ShieldCheck size={18} />
                  <div>
                    <b>
                      {language === "zh"
                        ? (report.historical ? "助手内容复审" : "本地确定性审计")
                        : (report.historical ? "Assistant content review" : "Local deterministic audit")}{" "}
                      · {report.audit.version}
                    </b>
                    <span>
                      {language === "zh"
                        ? `状态 ${report.audit.status}；引用 ${report.audit.citedReferences}，缺失 ${report.audit.missingReferences}，仅标题引用 ${report.audit.headlineOnlyReferences}`
                        : `Status ${report.audit.status}; ${report.audit.citedReferences} citations, ${report.audit.missingReferences} missing, ${report.audit.headlineOnlyReferences} headline-only`}
                    </span>
                  </div>
                  <em>
                    {report.audit.openaiUsed
                      ? language === "zh"
                        ? "使用 OpenAI"
                        : "OpenAI used"
                      : language === "zh"
                        ? "未使用 OpenAI"
                        : "No OpenAI"}
                  </em>
                </section>
              )}
              <details className="historical-report-note"><summary>{language==='zh'?'研究口径与版本记录':'Research scope & version history'}</summary><p>{report.model} · {language==='zh'?'实际生成':'Generated'}: {report.createdAt}</p>{report.historical&&<><p>{language==='zh'?'证据截止':'Evidence cutoff'}: {report.historical.asOf} · {language==='zh'?'数据库补建研究，不作为当时已发布的预测参与胜率统计。':'Reconstructed database research; not counted as a prediction published at the historical date.'}</p><ul>{(report.historical.corrections||[]).map((v:string,i:number)=><li key={i}>{v}</li>)}</ul></>}</details>
              <FullResearchBody report={report} language={language}/>
            </article>
          )}
            </main>
          </div>
            </>
          )}
          {evidenceView === "cross" && !accessRights?.research && <section className="report-section"><h2>{language==="zh"?"横向比较需要 Research 授权":"Comparisons require Research access"}</h2><a href="/account">{language==="zh"?"查看账号权限":"View access"}</a></section>}
          {evidenceView === "cross" && accessRights?.research && (
            <section className="cross-report-workspace">
              <header>
                <div>
                  <span className="eyebrow">
                    <Activity size={14} />
                    {language === "zh"
                      ? "横向连接与同口径比较"
                      : "Cross-company links and like-for-like comparison"}
                  </span>
                  <h1>
                    {language === "zh"
                      ? "跨公司与宏观研究"
                      : "Cross-company & macro research"}
                  </h1>
                  <p>
                    {language === "zh"
                      ? "宏观研究观察关键经济事件之后的市场变化；同行比较核对不同公司的财务与经营差异。请选择你要查验的问题。"
                      : "Macro research studies markets after key economic events; peer comparisons examine financial and operating differences. Choose the question you want to explore."}
                  </p>
                </div>
                <b>
                  {comparisonReports.length + (semiconductorComparison ? 1 : 0)}
                  <small>{language === "zh" ? "份横向报告" : "comparisons"}</small>
                </b>
              </header>
              <div className="comparison-mode-tabs" aria-label={language==="zh"?"研究类型":"Research type"}>
                <button type="button" aria-pressed={comparisonMode==="macro"} onClick={()=>setComparisonMode("macro")}>{language==="zh"?"宏观事件研究":"Macro events"}</button>
                <button type="button" aria-pressed={comparisonMode==="peers"} onClick={()=>setComparisonMode("peers")}>{language==="zh"?"同行公司比较":"Company peers"}</button>
              </div>
              {comparisonMode==="macro" ? <>
                <p className="comparison-explainer">{language==="zh"?"选取一次 FOMC 议息或非农发布，查看事件后 1、5、20 个交易日的市场反应。这是已有数据的事件研究，不会因点击而重新调用 AI。":"Choose an FOMC decision or payroll release to examine market reactions over 1, 5 and 20 trading days. This opens retained event studies; it does not start a new AI run."}</p>
                <MacroEventReports language={language}/>
              </> : <>
              <p className="comparison-explainer">{language==="zh"?"先选择公司与报告日期，再点“确定并查看”。每份报告保留其当时可得的资料，不是实时行情；财季、币种或会计口径不同的项目不作直接排名。":"Choose a company and report date, then Apply and view. Reports retain the information available at their cutoff, not live prices. Different fiscal periods, currencies or accounting bases are not ranked as like-for-like."}</p>
              <div className="cross-report-picker">
                <label>
                  <span>
                    {language === "zh"
                      ? "选择竞争对手同口径报告"
                      : "Choose a peer comparison"}
                  </span>
                  <select
                    value={comparisonReport?.id ?? ""}
                    disabled={comparisonReports.length === 0}
                    onChange={(event) => {
                      comparisonLoadSequenceRef.current += 1;
                      comparisonAbortRef.current?.abort();
                      setComparisonReportId(event.target.value);
                      setComparisonDetail(null);
                      setComparisonDetailError("");
                      setComparisonDetailLoading(false);
                    }}
                  >
                    {comparisonReports.length === 0 ? (
                      <option value="">
                        {language === "zh"
                          ? "暂无横向报告"
                          : "No cross-company report available"}
                      </option>
                    ) : (
                      comparisonReports.map((item) => (
                        <option value={item.id} key={item.id}>
                          {item.ticker || item.companyName || "GLOBAL"} · {new Date(
                            item.createdAt,
                          ).toLocaleDateString(
                            language === "zh" ? "zh-CN" : "en-CA",
                          )}
                        </option>
                      ))
                    )}
                  </select>
                </label>
                <button
                  type="button"
                  disabled={!comparisonReport || comparisonDetailLoading}
                  onClick={() =>
                    comparisonReport && void loadComparisonReport(comparisonReport)
                  }
                >
                  <Check size={15} />
                  {language === "zh" ? "确定并查看" : "Apply and view"}
                </button>
                <span>
                  <Database size={14} />
                  {language === "zh"
                    ? "10‑Q、年度财报与产品披露保持各自口径和可得日。"
                    : "10-Q, annual filings and product disclosures retain their own periods and availability dates."}
                </span>
              </div>
              {semiconductorComparison && <details className="research-fold sector-reference">
                <summary>{language==="zh"?"附：半导体行业财务对照":"Reference: semiconductor financial comparison"}</summary>
                <p>{language==="zh"?"这是单独的行业资料，与上方选中的公司报告不同。请按表内数据日期和会计口径查验。":"This is a separate sector reference, not the selected company report. Check the dates and accounting bases shown in its tables."}</p>
                <Suspense fallback={<p role="status">{language==="zh"?"读取行业对照…":"Loading sector comparison…"}</p>}><SemiconductorComparisonPanel comparison={semiconductorComparison} language={language}/></Suspense>
              </details>}
              {comparisonDetailLoading ? (
                <div className="report-detail-state">
                  <LoaderCircle className="spin" size={17} />
                  {language === "zh"
                    ? "正在载入横向报告…"
                    : "Loading peer comparison…"}
                </div>
              ) : comparisonDetailError ? (
                <div className="report-detail-state error">
                  <CircleAlert size={17} />
                  <div>
                    <b>{comparisonDetailError}</b>
                  </div>
                  {comparisonReport && (
                    <button
                      type="button"
                      onClick={() => void loadComparisonReport(comparisonReport)}
                    >
                      {language === "zh" ? "重试" : "Retry"}
                    </button>
                  )}
                </div>
              ) : comparisonDetail?.competitorComparison &&
                comparisonDetail.id === comparisonReport?.id ? (
                <CompetitorOperatingPanel
                  comparison={comparisonDetail.competitorComparison}
                  language={language}
                />
              ) : (
                <div className="report-library-state">
                  <CircleAlert size={17} />
                  {language === "zh"
                    ? "请选择一份竞争对手报告，然后点击“确定并查看”。"
                    : "Choose a peer report, then select Apply and view."}
                </div>
              )}
              </>}
            </section>
          )}
        </section>
      )}

      {tab === "sec" && !accessRights?.reports && <section className="content-page"><h1>{language==="zh"?"证据核验 · 会员权限":"Evidence · Member access"}</h1><p>{language==="zh"?"此区域需要 Signal 或 Research 授权。":"Signal or Research access is required."}</p><a href="/account">{language==="zh"?"查看账号权限":"View account access"}</a></section>}
      {tab === "sec" && accessRights?.reports && (
        <section className="content-page sec-page">
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                <ShieldCheck size={14} />
                SEC PRIMARY EVIDENCE
              </span>
              <h1>{t.secTitle}</h1>
              <p>{t.secSubtitle}</p>
            </div>
            <span className="healthy">
              <i />
              {secEvidence
                ? new Date(secEvidence.generatedAt).toLocaleDateString(
                    language === "zh" ? "zh-CN" : "en-CA",
                  )
                : t.secNoData}
            </span>
          </div>
          <div className="sec-metric-grid">
            {secEvidence &&
              [
                [t.secAssets, secEvidence.metrics.assetsSearched],
                [t.secFilings, secEvidence.metrics.candidateFilings],
                [t.secValues, secEvidence.metrics.valueCandidates],
                [t.secPending, secEvidence.metrics.pendingReview],
                [t.secConflicts, secEvidence.metrics.lifecycleConflicts],
              ].map(([label, value]) => (
                <article key={String(label)}>
                  <span>{label}</span>
                  <b>{value}</b>
                </article>
              ))}
          </div>
          <div className="sec-remote-boundary">
            <ShieldCheck size={18} />
            <div>
              <b>{t.secRemoteBoundary}</b>
              <p>
                {language === "zh"
                  ? "接受证据不等于确认终值；存在代码复用或生命周期冲突时，系统会继续隔离该资产。"
                  : "Accepting evidence is not the same as verifying a terminal value. Ticker reuse and lifecycle conflicts remain quarantined."}
              </p>
            </div>
          </div>
          <div className="sec-mobile-queue">
            {secEvidence?.candidates.map((candidate) => {
              return (
                <article
                  className={`sec-mobile-card ${candidate.reviewStatus}`}
                  key={candidate.evidenceKey}
                >
                  <header>
                    <div>
                      <span>
                        {candidate.symbol} · {candidate.form} ·{" "}
                        {candidate.filedOn}
                      </span>
                      <h2>{candidate.name}</h2>
                    </div>
                    <b>{candidate.confidence}%</b>
                  </header>
                  <div className="sec-value-row">
                    <strong>
                      {candidate.valueUnit === "acquirer_shares_per_share"
                        ? `${candidate.candidateValue}×`
                        : `$${Number(candidate.candidateValue ?? 0).toFixed(2)}`}
                    </strong>
                    <span>{secTypeLabel(candidate.evidenceType)}</span>
                  </div>
                  <p className="sec-excerpt">{candidate.excerpt}</p>
                  <div className="sec-card-meta">
                    <span>
                      {t.secIdentity}: <b>{candidate.identityStatus}</b>
                    </span>
                    <a
                      href={candidate.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {t.secSource}
                      <ExternalLink size={12} />
                    </a>
                  </div>
                  <div
                    className={`sec-factor-gate ${candidate.factorEligible ? "ready" : "blocked"}`}
                  >
                    <b>
                      {candidate.factorEligible
                        ? t.secFactorReady
                        : t.secFactorBlocked}
                    </b>
                    <span>{secFactorMessage(candidate)}</span>
                  </div>
                  <div className="readonly-inline-note">
                    <LockKeyhole size={14} />
                    {language === "zh" ? "公众网站仅展示已发布的审核记录" : "The public site shows published review records only"}
                  </div>
                </article>
              );
            }) ?? <div className="empty-state">{t.secNoData}</div>}
          </div>
        </section>
      )}

      {tab === "data" && <DataLibrary language={language}/>}
      {tab === "portfolio" && <Suspense fallback={<p role="status">{language==='zh'?'加载组合工具…':'Loading portfolio tools…'}</p>}><PortfolioLab language={language}/></Suspense>}
      {tab === "intelligence" && <IntelligenceMarket embedded displayLanguage={language}/>}
      {tab === "assets" && <Suspense fallback={<p role="status">{language==='zh'?'加载链上资产…':'Loading on-chain assets…'}</p>}><AssetIntelligence language={language}/></Suspense>}
      {tab === "markets" && <MarketsWorkspace language={language}/>}
      {tab === "alpha" && <Suspense fallback={<p role="status">{language==='zh'?'加载 Alpha 工具…':'Loading Alpha tools…'}</p>}><AlphaLab language={language}/></Suspense>}
      {tab === "personal" && <Suspense fallback={<p role="status">{language==='zh'?'正在打开询问 ORAKT…':'Opening Ask ORAKT…'}</p>}><PersonalResearch language={language}/></Suspense>}
      {tab === "chains" && <Suspense fallback={<p role="status">{language==='zh'?'加载证据链…':'Loading chains…'}</p>}><EvidenceChains language={language} renderReport={(r,l)=><FullResearchBody report={r} language={l}/>} onMap={()=>{setChainEnabled(true);changeTab('map')}}/></Suspense>}

    </main>
  );
}
