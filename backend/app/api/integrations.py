"""Configuration status for credential-gated public-data providers."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.integrations import IntegrationStatusResponse, IntegrationStatusView

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get(
    "/status",
    response_model=IntegrationStatusResponse,
    summary="Show safe credential readiness for optional providers",
)
def integration_status() -> IntegrationStatusResponse:
    """Expose only configured/not-configured state, never token values."""
    settings = get_settings()
    rows = [
        IntegrationStatusView(
            key="world_bank",
            name="World Bank Indicators API",
            status="ready",
            credential_name=None,
            configured=True,
            purpose_en=(
                "Primary annual macroeconomic, population, agriculture and industrial indicators."
            ),
            purpose_zh="年度宏观、人口、农业和工业指标的主要来源。",
            documentation_url="https://datahelpdesk.worldbank.org/knowledgebase/topics/125589",
            application_url="https://data.worldbank.org/",
        ),
        IntegrationStatusView(
            key="sec_edgar",
            name="SEC EDGAR Company Facts and Submissions",
            status="ready",
            credential_name=None,
            configured=True,
            purpose_en=(
                "Official company filings and standardized XBRL facts for the "
                "reviewed US large-company universe."
            ),
            purpose_zh="美国大型公司的一手申报文件与标准化 XBRL 财务指标。",
            documentation_url=(
                "https://www.sec.gov/search-filings/"
                "edgar-application-programming-interfaces"
            ),
            application_url="https://www.sec.gov/edgar/search/",
        ),
        IntegrationStatusView(
            key="us_treasury",
            name="U.S. Treasury Yield Curve XML",
            status="ready",
            credential_name=None,
            configured=True,
            purpose_en=(
                "Official daily 2-year and 10-year Treasury yields used by the causal validator."
            ),
            purpose_zh="供因果验证器使用的官方每日2年期和10年期美国国债收益率。",
            documentation_url=("https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"),
            application_url=(
                "https://home.treasury.gov/resource-center/data-chart-center/"
                "interest-rates/TextView?type=daily_treasury_yield_curve"
            ),
        ),
        IntegrationStatusView(
            key="federal_reserve",
            name="Federal Reserve Official Feeds",
            status="ready",
            credential_name=None,
            configured=True,
            purpose_en=(
                "FOMC monetary-policy releases and Powell speeches for primary-source verification."
            ),
            purpose_zh="用于一手来源核验的FOMC货币政策发布与鲍威尔讲话。",
            documentation_url="https://www.federalreserve.gov/feeds/feeds.htm",
            application_url=("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"),
        ),
        IntegrationStatusView(
            key="atlanta_fed_mpt",
            name="Atlanta Fed Market Probability Tracker",
            status="ready",
            credential_name=None,
            configured=True,
            purpose_en=(
                "Public daily SOFR-options-implied rate-path distributions, "
                "cut probabilities and hike probabilities."
            ),
            purpose_zh="公开的每日SOFR期权隐含利率路径、降息概率与加息概率分布。",
            documentation_url=(
                "https://www.atlantafed.org/research-and-data/data/"
                "market-probability-tracker"
            ),
            application_url=(
                "https://www.atlantafed.org/research-and-data/data/"
                "market-probability-tracker"
            ),
        ),
        IntegrationStatusView(
            key="fred",
            name="Federal Reserve Economic Data (FRED)",
            status=("ready" if settings.fred_api_key else "credential_required"),
            credential_name="NEWSAPP_FRED_API_KEY",
            configured=settings.fred_api_key is not None,
            purpose_en=(
                "Fallback policy-rate, yield, equity-index, inflation, labour "
                "and industrial-production observations."
            ),
            purpose_zh="政策利率、收益率、股指、通胀、就业和工业生产数据的回退来源。",
            documentation_url=(
                "https://fred.stlouisfed.org/docs/api/fred/series_observations.html"
            ),
            application_url="https://fred.stlouisfed.org/docs/api/api_key.html",
        ),
        IntegrationStatusView(
            key="ucdp",
            name="Uppsala Conflict Data Program",
            status="ready" if settings.ucdp_access_token else "credential_required",
            credential_name="NEWSAPP_UCDP_ACCESS_TOKEN",
            configured=settings.ucdp_access_token is not None,
            purpose_en="Versioned, geocoded armed-conflict event data.",
            purpose_zh="版本化、带坐标的武装冲突事件数据。",
            documentation_url="https://ucdp.uu.se/apidocs/",
            application_url="https://ucdp.uu.se/apidocs/",
        ),
        IntegrationStatusView(
            key="acled",
            name="Armed Conflict Location & Event Data (ACLED)",
            status=(
                "ready"
                if settings.acled_access_key and settings.acled_email
                else "credential_required"
            ),
            credential_name="NEWSAPP_ACLED_ACCESS_KEY + NEWSAPP_ACLED_EMAIL",
            configured=bool(settings.acled_access_key and settings.acled_email),
            purpose_en=(
                "A second geocoded conflict-event source for cross-source "
                "corroboration and local theater footprints."
            ),
            purpose_zh="用于交叉核验和局部战区归纳的第二个带坐标冲突事件来源。",
            documentation_url="https://developer.acleddata.com/",
            application_url="https://acleddata.com/user/register",
        ),
        IntegrationStatusView(
            key="nasa_firms",
            name="NASA FIRMS",
            status=(
                "ready"
                if settings.nasa_firms_map_key
                else "credential_required"
            ),
            credential_name="NEWSAPP_NASA_FIRMS_MAP_KEY",
            configured=settings.nasa_firms_map_key is not None,
            purpose_en=(
                "Near-real-time fire and thermal-anomaly points for disaster, "
                "agriculture and industrial-impact analysis."
            ),
            purpose_zh="用于灾害、农业与工业影响分析的近实时火点和热异常坐标。",
            documentation_url=(
                "https://firms.modaps.eosdis.nasa.gov/content/academy/"
                "data_api/firms_api_use.html"
            ),
            application_url="https://firms.modaps.eosdis.nasa.gov/api/map_key/",
        ),
        IntegrationStatusView(
            key="eia_bulk",
            name="U.S. Energy Information Administration Bulk Data",
            status="ready",
            credential_name=None,
            configured=True,
            purpose_en=(
                "Public bulk energy history and forecasts, locally archived "
                "and materialized for commodity transmission chains."
            ),
            purpose_zh="用于大宗商品传导链的能源产量、库存、贸易与价格序列。",
            documentation_url="https://www.eia.gov/opendata/documentation.php",
            application_url="https://www.eia.gov/opendata/bulkfiles.php",
        ),
        IntegrationStatusView(
            key="reliefweb",
            name="ReliefWeb API",
            status="ready" if settings.reliefweb_app_name else "credential_required",
            credential_name="NEWSAPP_RELIEFWEB_APP_NAME",
            configured=settings.reliefweb_app_name is not None,
            purpose_en="Humanitarian reports, disasters and crisis updates.",
            purpose_zh="人道主义报告、灾害与危机更新。",
            documentation_url="https://apidoc.reliefweb.int/",
            application_url="https://apidoc.reliefweb.int/",
        ),
        IntegrationStatusView(
            key="twelve_data",
            name="Twelve Data",
            status="ready" if settings.twelve_data_api_key else "credential_required",
            credential_name="NEWSAPP_TWELVE_DATA_API_KEY",
            configured=settings.twelve_data_api_key is not None,
            purpose_en="Delayed or real-time global market-index observations.",
            purpose_zh="全球主要市场指数的延时或实时观测值。",
            documentation_url="https://twelvedata.com/docs",
            application_url="https://twelvedata.com/pricing",
        ),
        IntegrationStatusView(
            key="alpha_vantage",
            name="Alpha Vantage Listing & Delisting Status",
            status=("ready" if settings.alpha_vantage_api_key else "credential_required"),
            credential_name="NEWSAPP_ALPHA_VANTAGE_API_KEY",
            configured=settings.alpha_vantage_api_key is not None,
            purpose_en=(
                "Point-in-time US stock and ETF membership from 2010 onward for "
                "survivorship-bias audits, plus a bounded personal-use weekly adjusted "
                "price backfill. Catalog rows remain separate from price observations."
            ),
            purpose_zh=(
                "提供2010年后的美国股票与ETF逐时点上市/退市目录, 并按个人额度分批补充"
                "复权周线; 清单与价格观测始终分开。"
            ),
            documentation_url="https://www.alphavantage.co/documentation/",
            application_url="https://www.alphavantage.co/support/#api-key",
        ),
        IntegrationStatusView(
            key="openfigi",
            name="OpenFIGI Security Identity Mapping",
            status="ready",
            credential_name="NEWSAPP_OPENFIGI_API_KEY",
            configured=True,
            purpose_en=(
                "Cross-source FIGI, share-class and composite identity checks before "
                "provider-backfilled delisted prices can enter factor tests."
            ),
            purpose_zh=(
                "在自动补齐的退市价格进入因子检验前, 以FIGI、股份类别、公司名称和"
                "交易所执行跨源身份核验。"
            ),
            documentation_url="https://www.openfigi.com/api/documentation",
            application_url="https://www.openfigi.com/api",
        ),
        IntegrationStatusView(
            key="openai_review",
            name="OpenAI causal review and revision loop",
            status="ready" if settings.openai_api_key else "credential_required",
            credential_name="NEWSAPP_OPENAI_API_KEY",
            configured=settings.openai_api_key is not None,
            purpose_en=(
                "Automatic audit of causal direction and evidence sufficiency, "
                "followed by local-model revision and final confirmation."
            ),
            purpose_zh=(
                "通过 Responses API 对本地 AI 研究结果进行可选的第二次复核, "
                "本地结果仍作为主要记录保留."
            ),
            documentation_url="https://developers.openai.com/api/docs/guides/text",
            application_url="https://platform.openai.com/api-keys",
        ),
    ]
    return IntegrationStatusResponse(integrations=rows)
