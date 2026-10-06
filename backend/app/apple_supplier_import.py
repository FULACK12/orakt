"""Import Apple's official FY2023 supplier list with explicit date limitations."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CompanySupplyChainCoverage, CompanySupplyChainEdge
from app.db.session import get_session_factory
from app.storage.archive import ColdArchive
from app.supply_chain import refresh_supply_chain_coverage
from app.supply_chain_sites import materialize_supply_chain_sites

APPLE_SUPPLIER_SOURCE_URL = (
    "https://www.supplychainreports.apple/files/doc_downloads/2024/04/Apple-Supplier-List.pdf"
)
APPLE_SUPPLIER_SOURCE_REF = "apple-supplier-list:FY2023"
APPLE_FY2023_END = date(2023, 9, 30)
APPLE_LIST_AVAILABLE_AT = date(2024, 4, 1)
APPLE_LIST_ARCHIVE_PATH = "raw/apple/supplier-lists/FY2023/Apple-Supplier-List-FY2023.pdf"


@dataclass(frozen=True)
class AppleSupplierRow:
    name: str
    manufacturing_locations: str


RELATED_TICKERS = {
    "advanced semiconductor engineering technology holding co., ltd.": "ASX",
    "amkor technology incorporated": "AMKR",
    "analog devices incorporated": "ADI",
    "broadcom limited": "AVGO",
    "cirrus logic incorporated": "CRUS",
    "corning incorporated": "GLW",
    "intel corporation": "INTC",
    "jabil incorporated": "JBL",
    "lumentum holdings incorporated": "LITE",
    "microchip technology incorporated": "MCHP",
    "micron technology incorporated": "MU",
    "nordic semiconductor asa": "NDCVF",
    "nxp semiconductors n.v.": "NXPI",
    "on semiconductor corporation": "ON",
    "qorvo incorporated": "QRVO",
    "qualcomm incorporated": "QCOM",
    "skyworks solutions incorporated": "SWKS",
    "stmicroelectronics n.v.": "STM",
    "synaptics incorporated": "SYNA",
    "taiwan semiconductor manufacturing company limited": "TSM",
    "texas instruments incorporated": "TXN",
    "viavi solutions incorporated": "VIAV",
    "western digital corporation": "WDC",
}


class AppleSupplierImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suppliers_parsed: int = Field(ge=0)
    suppliers_imported: int = Field(ge=0)
    related_tickers_resolved: int = Field(ge=0)
    archive_path: str


def parse_apple_supplier_pdf(path: Path) -> list[AppleSupplierRow]:
    """Parse layout columns and validate the document's stated scope and date."""
    reader = PdfReader(path)
    if len(reader.pages) != 27:
        raise ValueError(f"unexpected Apple supplier-list page count: {len(reader.pages)}")
    introduction = reader.pages[0].extract_text() or ""
    ending = reader.pages[-1].extract_text() or ""
    if "98 percent" not in introduction or "fiscal year 2023" not in introduction:
        raise ValueError("Apple supplier-list scope statement was not found")
    if "end of fiscal year 2023" not in ending:
        raise ValueError("Apple supplier-list point-in-time statement was not found")
    rows: list[AppleSupplierRow] = []
    for page in reader.pages[1:26]:
        layout = page.extract_text(extraction_mode="layout") or ""
        rows.extend(parse_supplier_layout_page(layout))
    if not 150 <= len(rows) <= 250:
        raise ValueError(f"parsed supplier count is implausible: {len(rows)}")
    names = {row.name.casefold() for row in rows}
    required = {
        "broadcom limited",
        "hon hai precision industry company limited (foxconn)",
        "micron technology incorporated",
        "taiwan semiconductor manufacturing company limited",
    }
    if not required.issubset(names):
        raise ValueError("known Apple supplier control rows are missing")
    return rows


def parse_supplier_layout_page(layout: str) -> list[AppleSupplierRow]:
    lines = layout.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if "SUPPLIER NAME" in line),
        None,
    )
    if header_index is None:
        return []
    header = lines[header_index]
    supplier_start = header.find("SUPPLIER NAME")
    location_start = header.find("PRIMARY LOCATIONS")
    if supplier_start < 0 or location_start <= supplier_start:
        return []
    rows: list[AppleSupplierRow] = []
    current_name: str | None = None
    current_locations: list[str] = []

    def flush() -> None:
        nonlocal current_name, current_locations
        if current_name:
            rows.append(
                AppleSupplierRow(
                    name=_repair_pdf_spacing(current_name),
                    manufacturing_locations=" | ".join(
                        _repair_pdf_spacing(item) for item in current_locations if item
                    ),
                )
            )
        current_name = None
        current_locations = []

    for line in lines[header_index + 1 :]:
        if line.lstrip().startswith("* Suppliers designated"):
            break
        supplier = line[supplier_start:location_start].strip()
        location = re.sub(r"\s{2,}", " - ", line[location_start:].strip())
        if supplier:
            flush()
            current_name = supplier
            current_locations = [location] if location else []
        elif current_name and location:
            current_locations.append(location)
    flush()
    return rows


def import_apple_supplier_list(
    session: Session,
    *,
    pdf_path: Path,
    archive: ColdArchive,
) -> AppleSupplierImportResult:
    rows = parse_apple_supplier_pdf(pdf_path)
    stored_path = archive.store_bytes(APPLE_LIST_ARCHIVE_PATH, pdf_path.read_bytes())
    session.execute(
        delete(CompanySupplyChainEdge).where(
            CompanySupplyChainEdge.subject_ticker == "AAPL",
            CompanySupplyChainEdge.source_kind == "issuer_supplier_list",
            CompanySupplyChainEdge.source_ref.like(f"{APPLE_SUPPLIER_SOURCE_REF}:%"),
        )
    )
    now = datetime.now(UTC)
    resolved = 0
    for index, row in enumerate(rows, start=1):
        related_ticker = RELATED_TICKERS.get(row.name.casefold())
        resolved += related_ticker is not None
        session.add(
            CompanySupplyChainEdge(
                subject_ticker="AAPL",
                related_company_name=row.name,
                related_ticker=related_ticker,
                relationship_type="supplier",
                product_or_input=(
                    "materials, manufacturing or assembly in Apple's FY2023 "
                    "98%-of-direct-spend supplier list"
                ),
                geography=row.manufacturing_locations[:255] or None,
                dependency_level="unknown",
                review_status="verified",
                confidence=0.82,
                source_kind="issuer_supplier_list",
                source_ref=f"{APPLE_SUPPLIER_SOURCE_REF}:{index:03d}",
                source_url=APPLE_SUPPLIER_SOURCE_URL,
                source_excerpt=(
                    f"{row.name} - primary manufacturing locations: "
                    f"{row.manufacturing_locations}. Apple states this list represents "
                    "98 percent of direct spend for materials, manufacturing and assembly "
                    "worldwide for fiscal year 2023."
                )[:1_800],
                observed_at=APPLE_FY2023_END,
                available_at=APPLE_LIST_AVAILABLE_AT,
                valid_from=APPLE_FY2023_END,
                reviewed_at=now,
                reviewed_by="codex_apple_supplier_list_v1",
                review_note=(
                    "Official Apple Supplier List verifies a supplier relationship as of "
                    "FY2023; it does not identify product, volume, dependency, or continued "
                    "2026 status for this individual supplier."
                ),
            )
        )
    session.flush()
    state = session.get(CompanySupplyChainCoverage, "AAPL")
    if state is not None:
        state.gaps = [
            "official list is point-in-time FY2023, not complete current-2026 status",
            "supplier-to-component and product mapping",
            "facility capacity, contract, volume, price and delivery series",
        ]
    refresh_supply_chain_coverage(session, ticker="AAPL")
    materialize_supply_chain_sites(session, ticker="AAPL")
    session.commit()
    return AppleSupplierImportResult(
        suppliers_parsed=len(rows),
        suppliers_imported=len(rows),
        related_tickers_resolved=resolved,
        archive_path=stored_path,
    )


def _repair_pdf_spacing(value: str) -> str:
    value = re.sub(r"\b([A-Za-z]{3,}) ([a-z])\b", r"\1\2", value)
    return re.sub(r"\s+", " ", value).strip()


def main() -> None:
    parser = argparse.ArgumentParser(prog="newsapp-apple-supplier-import")
    parser.add_argument("pdf_path", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    archive = ColdArchive(
        settings.cold_data_root,
        min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
        max_used_percent=settings.cold_archive_max_used_percent,
    )
    with get_session_factory()() as session:
        result = import_apple_supplier_list(
            session,
            pdf_path=args.pdf_path,
            archive=archive,
        )
    print(result.model_dump_json(indent=2), flush=True)


if __name__ == "__main__":
    main()
