"""BaoStock-backed CSI 800 sector leaders and adjusted daily A-share history."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

import baostock as bs  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import MarketObservation, MarketSeries, MarketSyncState

PROVIDER_KEY = "baostock_china_leaders"
SOURCE_NAME = "BaoStock"
SOURCE_URL = "https://www.baostock.com/"
RANKING_METRIC = (
    "CSI 300 + CSI 500 sector composite: market cap 20%, revenue 15%, net profit 15%, "
    "ROE 10%, net-income growth 15%, liquidity 15%, valuation 10%"
)
UNIVERSE_NAME = "CSI 300 + CSI 500 (CSI 800 proxy)"


class ChinaDailySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    close: float = Field(gt=0)
    traded_amount_cny: float = Field(gt=0)
    pe_ttm: float | None = None
    pb_mrq: float | None = None


class ChinaFundamentalSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    financial_as_of: date | None = None
    revenue_cny: float | None = None
    net_profit_cny: float | None = None
    total_shares: float | None = None
    roe: float | None = None
    yoy_net_income: float | None = None


class ChinaEquityLeader(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_code: str
    symbol: str
    name: str
    sector: str
    industry: str
    rank: int = Field(ge=1)
    ranking_amount_cny: float = Field(ge=0)
    composite_score: float = Field(ge=0, le=100)
    financial_as_of: date | None = None
    market_cap_cny: float | None = None
    revenue_cny: float | None = None
    net_profit_cny: float | None = None
    roe: float | None = None
    yoy_net_income: float | None = None
    pe_ttm: float | None = None
    pb_mrq: float | None = None


class ChinaEquitySyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_key: str = PROVIDER_KEY
    universe: str = UNIVERSE_NAME
    universe_as_of: date
    ranking_start: date
    ranking_end: date
    candidates_scanned: int = Field(ge=0)
    sectors: int = Field(ge=0)
    leaders_selected: int = Field(ge=0)
    price_series_synced: int = Field(ge=0)
    observations_upserted: int = Field(ge=0)
    leaders: list[ChinaEquityLeader]
    errors: list[str] = Field(default_factory=list)


def sync_china_equity_leaders(
    session: Session,
    *,
    history_start: date,
    history_end: date,
    leaders_per_sector: int = 10,
    ranking_days: int = 90,
    provider: Any = bs,
    commit_each_leader: bool = False,
) -> ChinaEquitySyncResult:
    """Rank liquid CSI 300 and CSI 500 members by sector and retain histories."""
    state = _sync_state(session)
    state.last_started_at = datetime.now(UTC)
    state.history_start = history_start
    state.history_end = history_end
    state.last_error = None
    login = provider.login()
    if str(login.error_code) != "0":
        message = f"BaoStock login failed: {login.error_code} {login.error_msg}"
        state.last_error = message
        raise RuntimeError(message)
    errors: list[str] = []
    try:
        constituents = _index_constituents(provider)
        industry_rows = _result_rows(provider.query_stock_industry())
        industry_by_code = {
            row[1]: (row[2], row[3])
            for row in industry_rows
            if len(row) >= 4 and row[1]
        }
        constituent_dates = [
            observed_on
            for row in constituents
            if row and (observed_on := _parse_date(row[0])) is not None
        ]
        universe_as_of = max(constituent_dates, default=history_end)
        if hasattr(provider, "query_daily_history_k_AStock"):
            ranking_end, daily_snapshots = _latest_bulk_snapshots(
                provider,
                end=history_end,
            )
            ranking_start = ranking_end
        else:
            ranking_end = history_end
            ranking_start = history_end - timedelta(days=ranking_days - 1)
            daily_snapshots = {}
        financial_year, financial_quarter = _available_financial_period(ranking_end)
        ranked: dict[str, list[dict[str, Any]]] = {}
        for row in constituents:
            if len(row) < 3:
                continue
            code = row[1]
            name = row[2]
            industry = industry_by_code.get(code, (name, ""))[1]
            sector = broad_china_sector(industry)
            if sector is None:
                continue
            try:
                daily = daily_snapshots.get(code)
                amount = (
                    daily.traded_amount_cny
                    if daily is not None
                    else _average_traded_amount(
                        provider,
                        code=code,
                        start=ranking_start,
                        end=history_end,
                    )
                )
            except (IndexError, TypeError, ValueError) as exc:
                errors.append(f"{code}: ranking {type(exc).__name__}: {str(exc)[:120]}")
                continue
            if amount <= 0:
                continue
            ranked.setdefault(sector, []).append(
                {
                    "amount": amount,
                    "code": code,
                    "name": name,
                    "industry": industry,
                    "daily_close": daily.close if daily is not None else None,
                    "pe_ttm": daily.pe_ttm if daily is not None else None,
                    "pb_mrq": daily.pb_mrq if daily is not None else None,
                }
            )
        shortlist_size = max(leaders_per_sector * 2, leaders_per_sector + 5)
        for sector, values in ranked.items():
            shortlisted = sorted(
                values,
                key=lambda item: (-float(item["amount"]), str(item["code"])),
            )[:shortlist_size]
            for candidate in shortlisted:
                code = str(candidate["code"])
                try:
                    fundamentals = _fundamental_snapshot(
                        provider,
                        code=code,
                        year=financial_year,
                        quarter=financial_quarter,
                    )
                except (IndexError, TypeError, ValueError) as exc:
                    errors.append(
                        f"{code}: fundamentals {type(exc).__name__}: {str(exc)[:120]}"
                    )
                    fundamentals = ChinaFundamentalSnapshot()
                close = candidate.get("daily_close")
                candidate.update(
                    {
                        "market_cap": (
                            float(close) * fundamentals.total_shares
                            if isinstance(close, (int, float))
                            and fundamentals.total_shares is not None
                            and fundamentals.total_shares > 0
                            else None
                        ),
                        "revenue": fundamentals.revenue_cny,
                        "net_profit": fundamentals.net_profit_cny,
                        "roe": fundamentals.roe,
                        "yoy_net_income": fundamentals.yoy_net_income,
                        "financial_as_of": fundamentals.financial_as_of,
                    }
                )
            ranked[sector] = shortlisted
        leaders: list[ChinaEquityLeader] = []
        for sector, values in sorted(ranked.items()):
            scored = _score_sector_candidates(values)
            for rank, candidate in enumerate(
                sorted(
                    scored,
                    key=lambda item: (
                        -float(item["composite_score"]),
                        -float(item["amount"]),
                        str(item["code"]),
                    ),
                )[:leaders_per_sector],
                start=1,
            ):
                leaders.append(
                    ChinaEquityLeader(
                        provider_code=str(candidate["code"]),
                        symbol=str(candidate["code"]).split(".", 1)[-1],
                        name=str(candidate["name"]),
                        sector=sector,
                        industry=str(candidate["industry"]),
                        rank=rank,
                        ranking_amount_cny=round(float(candidate["amount"]), 2),
                        composite_score=round(float(candidate["composite_score"]), 4),
                        financial_as_of=candidate.get("financial_as_of"),
                        market_cap_cny=_optional_round(candidate.get("market_cap")),
                        revenue_cny=_optional_round(candidate.get("revenue")),
                        net_profit_cny=_optional_round(candidate.get("net_profit")),
                        roe=_optional_round(candidate.get("roe"), digits=8),
                        yoy_net_income=_optional_round(
                            candidate.get("yoy_net_income"), digits=8
                        ),
                        pe_ttm=_optional_round(candidate.get("pe_ttm"), digits=6),
                        pb_mrq=_optional_round(candidate.get("pb_mrq"), digits=6),
                    )
                )
        _mark_existing_catalog_inactive(session)
        _upsert_catalog(session, leaders)
        fetched_at = datetime.now(UTC)
        snapshot_rows = [
            row
            for leader in leaders
            for row in _leader_snapshot_rows(
                leader,
                observed_on=ranking_end,
                fetched_at=fetched_at,
            )
        ]
        snapshot_observations = _upsert_observations(session, snapshot_rows)
        if commit_each_leader:
            session.commit()
        observation_total = snapshot_observations
        series_synced = 0
        for leader in leaders:
            try:
                local_start, local_end = session.execute(
                    select(
                        func.min(MarketObservation.observed_on),
                        func.max(MarketObservation.observed_on),
                    ).where(MarketObservation.series_id == f"CN:{leader.symbol}")
                ).one()
                selected_history_start = history_start
                if (
                    local_start is not None
                    and local_end is not None
                    and local_start <= history_start
                ):
                    selected_history_start = max(
                        history_start,
                        local_end - timedelta(days=10),
                    )
                rows = _history_rows(
                    provider,
                    code=leader.provider_code,
                    start=selected_history_start,
                    end=history_end,
                    fetched_at=fetched_at,
                )
                observation_total += _upsert_observations(session, rows)
                series_synced += 1
            except (IndexError, TypeError, ValueError) as exc:
                errors.append(
                    f"{leader.provider_code}: history {type(exc).__name__}: {str(exc)[:120]}"
                )
            if commit_each_leader:
                session.commit()
        state.last_success_at = datetime.now(UTC)
        state.series_synced = series_synced
        state.observations_upserted = observation_total
        state.last_error = "; ".join(errors[:8]) or None
        session.flush()
        return ChinaEquitySyncResult(
            universe_as_of=universe_as_of,
            ranking_start=ranking_start,
            ranking_end=ranking_end,
            candidates_scanned=sum(len(values) for values in ranked.values()),
            sectors=len(ranked),
            leaders_selected=len(leaders),
            price_series_synced=series_synced,
            observations_upserted=observation_total,
            leaders=leaders,
            errors=errors,
        )
    finally:
        provider.logout()


def broad_china_sector(industry: str) -> str | None:
    """Map CSRC industry codes into stable cross-market research sectors."""
    match = re.match(r"^([A-S])(\d{2})?", industry.strip().upper())
    if match is None:
        return None
    letter = match.group(1)
    number = int(match.group(2)) if match.group(2) else None
    if letter == "A":
        return "Agriculture"
    if letter == "B":
        return "Energy and mining"
    if letter == "C":
        if number == 27:
            return "Health care"
        if number == 36:
            return "Automotive"
        if number == 39:
            return "Technology"
        if number is not None and 13 <= number <= 24:
            return "Consumer"
        if number is not None and 25 <= number <= 33:
            return "Materials"
        return "Industrials"
    return {
        "D": "Utilities",
        "E": "Industrials",
        "F": "Consumer",
        "G": "Transportation",
        "H": "Consumer",
        "I": "Technology",
        "J": "Financials",
        "K": "Real estate",
        "L": "Business services",
        "M": "Business services",
        "N": "Utilities",
        "O": "Consumer",
        "P": "Consumer",
        "Q": "Health care",
        "R": "Communication",
        "S": "Business services",
    }.get(letter)


def _index_constituents(provider: Any) -> list[list[str]]:
    """Return the current CSI 800 proxy universe without duplicate constituents."""
    rows = _result_rows(provider.query_hs300_stocks())
    if hasattr(provider, "query_zz500_stocks"):
        rows.extend(_result_rows(provider.query_zz500_stocks()))
    deduplicated: dict[str, list[str]] = {}
    for row in rows:
        if len(row) >= 3 and row[1]:
            deduplicated[str(row[1])] = row
    return list(deduplicated.values())


def _average_traded_amount(provider: Any, *, code: str, start: date, end: date) -> float:
    result = provider.query_history_k_data_plus(
        code,
        "date,code,amount,tradestatus,isST",
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        frequency="d",
        adjustflag="2",
    )
    rows = _result_rows(result)
    amounts = [
        float(row[2])
        for row in rows
        if len(row) >= 5
        and row[2]
        and row[3] == "1"
        and row[4] == "0"
        and float(row[2]) > 0
    ]
    return sum(amounts) / len(amounts) if amounts else 0.0


def _latest_bulk_snapshots(
    provider: Any,
    *,
    end: date,
    lookback_days: int = 10,
) -> tuple[date, dict[str, ChinaDailySnapshot]]:
    """Load one complete trading-day snapshot instead of 300 symbol requests."""
    errors: list[str] = []
    for offset in range(lookback_days):
        observed_on = end - timedelta(days=offset)
        result = provider.query_daily_history_k_AStock(observed_on.isoformat())
        try:
            rows = _result_rows(result)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        fields = [str(value) for value in getattr(result, "fields", [])]
        try:
            code_index = fields.index("code")
            close_index = fields.index("close")
            amount_index = fields.index("amount")
            trade_index = fields.index("tradestatus")
            st_index = fields.index("isST")
        except ValueError as exc:
            raise ValueError("BaoStock bulk daily response is missing ranking fields") from exc
        pe_index = fields.index("peTTM") if "peTTM" in fields else None
        pb_index = fields.index("pbMRQ") if "pbMRQ" in fields else None
        snapshots = {
            row[code_index]: ChinaDailySnapshot(
                close=float(row[close_index]),
                traded_amount_cny=float(row[amount_index]),
                pe_ttm=(
                    _optional_float(row[pe_index]) if pe_index is not None else None
                ),
                pb_mrq=(
                    _optional_float(row[pb_index]) if pb_index is not None else None
                ),
            )
            for row in rows
            if len(row) > max(code_index, close_index, amount_index, trade_index, st_index)
            and row[close_index]
            and row[amount_index]
            and row[trade_index] == "1"
            and row[st_index] == "0"
            and float(row[close_index]) > 0
            and float(row[amount_index]) > 0
        }
        if snapshots:
            return observed_on, snapshots
    detail = "; ".join(errors[:3])
    raise ValueError(f"BaoStock has no bulk daily data near {end}: {detail}")


def _available_financial_period(observed_on: date) -> tuple[int, int]:
    """Choose a quarter that should already be public under PRC filing deadlines."""
    if observed_on.month >= 8:
        return observed_on.year, 2
    if observed_on.month >= 5:
        return observed_on.year, 1
    return observed_on.year - 1, 3


def _fundamental_snapshot(
    provider: Any,
    *,
    code: str,
    year: int,
    quarter: int,
) -> ChinaFundamentalSnapshot:
    if not hasattr(provider, "query_profit_data"):
        return ChinaFundamentalSnapshot()
    profit_result = provider.query_profit_data(code, year=year, quarter=quarter)
    profit_rows = _result_rows(profit_result)
    profit_fields = [str(value) for value in getattr(profit_result, "fields", [])]
    profit = _field_row(profit_fields, profit_rows[0] if profit_rows else [])
    growth: dict[str, str] = {}
    if hasattr(provider, "query_growth_data"):
        growth_result = provider.query_growth_data(code, year=year, quarter=quarter)
        growth_rows = _result_rows(growth_result)
        growth_fields = [str(value) for value in getattr(growth_result, "fields", [])]
        growth = _field_row(growth_fields, growth_rows[0] if growth_rows else [])
    return ChinaFundamentalSnapshot(
        financial_as_of=_parse_date(profit.get("statDate", "")),
        revenue_cny=_optional_float(profit.get("MBRevenue")),
        net_profit_cny=_optional_float(profit.get("netProfit")),
        total_shares=_optional_float(profit.get("totalShare")),
        roe=_optional_float(profit.get("roeAvg")),
        yoy_net_income=_optional_float(growth.get("YOYNI")),
    )


def _field_row(fields: list[str], row: list[str]) -> dict[str, str]:
    return {field: row[index] for index, field in enumerate(fields) if index < len(row)}


def _score_sector_candidates(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply transparent within-sector percentile weights to leadership factors."""
    dimensions = {
        "market_cap": (0.20, True, True),
        "revenue": (0.15, True, True),
        "net_profit": (0.15, True, False),
        "roe": (0.10, True, False),
        "yoy_net_income": (0.15, True, False),
        "amount": (0.15, True, True),
        "pe_ttm": (0.05, False, False),
        "pb_mrq": (0.05, False, False),
    }
    component_scores = {
        key: _percentile_scores(values, key=key, higher_is_better=higher, positive_only=positive)
        for key, (_, higher, positive) in dimensions.items()
    }
    scored: list[dict[str, Any]] = []
    for candidate in values:
        code = str(candidate["code"])
        score = sum(
            weight * component_scores[key].get(code, 0.0)
            for key, (weight, _, _) in dimensions.items()
        )
        scored.append({**candidate, "composite_score": round(score * 100, 6)})
    return scored


def _percentile_scores(
    values: list[dict[str, Any]],
    *,
    key: str,
    higher_is_better: bool,
    positive_only: bool,
) -> dict[str, float]:
    available = [
        (str(item["code"]), float(item[key]))
        for item in values
        if isinstance(item.get(key), (int, float))
        and (not positive_only or float(item[key]) > 0)
        and (key not in {"pe_ttm", "pb_mrq"} or float(item[key]) > 0)
    ]
    available.sort(key=lambda item: item[1], reverse=not higher_is_better)
    if not available:
        return {}
    if len(available) == 1:
        return {available[0][0]: 1.0}
    return {
        code: index / (len(available) - 1)
        for index, (code, _) in enumerate(available)
    }


def _leader_snapshot_rows(
    leader: ChinaEquityLeader,
    *,
    observed_on: date,
    fetched_at: datetime,
) -> list[dict[str, Any]]:
    values = {
        "CNSCORE": leader.composite_score,
        "CNMCAP": leader.market_cap_cny,
        "CNREV": leader.revenue_cny,
        "CNNP": leader.net_profit_cny,
        "CNROE": leader.roe,
        "CNYOYNI": leader.yoy_net_income,
        "CNPE": leader.pe_ttm,
        "CNPB": leader.pb_mrq,
    }
    return [
        {
            "series_id": f"{prefix}:{leader.symbol}",
            "observed_on": observed_on,
            "value": value,
            "fetched_at": fetched_at,
        }
        for prefix, value in values.items()
        if value is not None
    ]


def _history_rows(
    provider: Any,
    *,
    code: str,
    start: date,
    end: date,
    fetched_at: datetime,
) -> list[dict[str, Any]]:
    result = provider.query_history_k_data_plus(
        code,
        "date,code,close,volume,amount,turn,tradestatus,isST",
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        frequency="d",
        adjustflag="2",
    )
    rows: list[dict[str, Any]] = []
    symbol = code.split(".", 1)[-1]
    for values in _result_rows(result):
        if len(values) < 8 or values[6] != "1" or values[7] != "0":
            continue
        observed_on = _parse_date(values[0])
        if observed_on is None:
            continue
        for prefix, raw_value in (
            ("CN", values[2]),
            ("CNVOL", values[3]),
            ("CNAMT", values[4]),
            ("CNTURN", values[5]),
        ):
            if not raw_value:
                continue
            value = float(raw_value)
            if value < 0 or (prefix == "CN" and value <= 0):
                continue
            rows.append(
                {
                    "series_id": f"{prefix}:{symbol}",
                    "observed_on": observed_on,
                    "value": value,
                    "fetched_at": fetched_at,
                }
            )
    return rows


def _upsert_catalog(session: Session, leaders: list[ChinaEquityLeader]) -> None:
    rows: list[dict[str, Any]] = []
    for leader in leaders:
        snapshot_values = {
            "CNSCORE": leader.composite_score,
            "CNMCAP": leader.market_cap_cny,
            "CNREV": leader.revenue_cny,
            "CNNP": leader.net_profit_cny,
            "CNROE": leader.roe,
            "CNYOYNI": leader.yoy_net_income,
            "CNPE": leader.pe_ttm,
            "CNPB": leader.pb_mrq,
        }
        for prefix, label, category, unit in (
            ("CN", "前复权收盘价", "equity_price", "CNY"),
            ("CNVOL", "成交量", "equity_volume", "shares"),
            ("CNAMT", "成交额", "equity_turnover", "CNY"),
            ("CNTURN", "换手率", "equity_turnover_rate", "percent"),
            ("CNSCORE", "行业龙头综合分", "equity_factor", "score_0_100"),
            ("CNMCAP", "总市值", "company_fundamental", "CNY"),
            ("CNREV", "营业收入", "company_fundamental", "CNY"),
            ("CNNP", "净利润", "company_fundamental", "CNY"),
            ("CNROE", "平均净资产收益率", "company_fundamental", "ratio"),
            ("CNYOYNI", "净利润同比增长", "company_fundamental", "ratio"),
            ("CNPE", "滚动市盈率", "valuation", "ratio"),
            ("CNPB", "市净率", "valuation", "ratio"),
        ):
            if prefix in snapshot_values and snapshot_values[prefix] is None:
                continue
            rows.append(
                {
                    "series_id": f"{prefix}:{leader.symbol}",
                    "name": f"{leader.name} ({leader.symbol}) {label}",
                    "category": category,
                    "unit": unit,
                    "frequency": (
                        "daily"
                        if prefix in {"CN", "CNVOL", "CNAMT", "CNTURN"}
                        else "snapshot"
                    ),
                    "source_name": SOURCE_NAME,
                    "source_url": SOURCE_URL,
                    "listing_status": "active",
                    "sector": leader.sector,
                    "region": "china",
                    "neutralization_group": f"csrc:{leader.industry}",
                }
            )
    if not rows:
        return
    insert = _dialect_insert(session, MarketSeries)
    statement = insert.values(rows)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[MarketSeries.series_id],
            set_={
                "name": statement.excluded.name,
                "category": statement.excluded.category,
                "unit": statement.excluded.unit,
                "frequency": statement.excluded.frequency,
                "source_name": statement.excluded.source_name,
                "source_url": statement.excluded.source_url,
                "listing_status": statement.excluded.listing_status,
                "sector": statement.excluded.sector,
                "region": statement.excluded.region,
                "neutralization_group": statement.excluded.neutralization_group,
            },
        )
    )


def _mark_existing_catalog_inactive(session: Session) -> None:
    """Keep historical rows but prevent former leaders entering new report batches."""
    session.execute(
        update(MarketSeries)
        .where(
            MarketSeries.region == "china",
            MarketSeries.source_name == SOURCE_NAME,
            MarketSeries.series_id.like("CN%:%"),
        )
        .values(listing_status="inactive")
    )


def _upsert_observations(session: Session, rows: list[dict[str, Any]]) -> int:
    deduplicated = list(
        {(row["series_id"], row["observed_on"]): row for row in rows}.values()
    )
    for start in range(0, len(deduplicated), 5_000):
        batch = deduplicated[start : start + 5_000]
        if not batch:
            continue
        insert = _dialect_insert(session, MarketObservation)
        statement = insert.values(batch)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[MarketObservation.series_id, MarketObservation.observed_on],
                set_={
                    "value": statement.excluded.value,
                    "fetched_at": statement.excluded.fetched_at,
                },
            )
        )
    return len(deduplicated)


def _result_rows(result: Any) -> list[list[str]]:
    if str(result.error_code) != "0":
        raise ValueError(f"BaoStock query failed: {result.error_code} {result.error_msg}")
    rows: list[list[str]] = []
    while result.next():
        rows.append([str(value) for value in result.get_row_data()])
    return rows


def _sync_state(session: Session) -> MarketSyncState:
    state = session.get(MarketSyncState, PROVIDER_KEY)
    if state is None:
        state = MarketSyncState(
            provider_key=PROVIDER_KEY,
            series_synced=0,
            observations_upserted=0,
        )
        session.add(state)
    return state


def _dialect_insert(session: Session, model: type[Any]) -> Any:
    if session.get_bind().dialect.name == "sqlite":
        return sqlite_insert(model)
    return postgresql_insert(model)


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and abs(parsed) != float("inf") else None


def _optional_round(value: object, *, digits: int = 2) -> float | None:
    parsed = _optional_float(value)
    return round(parsed, digits) if parsed is not None else None
