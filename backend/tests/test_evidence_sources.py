"""Official policy and market-evidence source tests."""

import json
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import httpx

from app.core.config import Settings
from app.evidence_sources import (
    FRED_VALIDATION_SERIES,
    fetch_validation_evidence,
    parse_atlanta_fed_mpt_xlsx,
    parse_federal_reserve_feed,
    parse_treasury_yield_xml,
)


def _mpt_workbook() -> bytes:
    workbook = b"""\
    <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
      xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
      <sheets><sheet name="DATA" sheetId="1" r:id="rId1"/></sheets>
    </workbook>
    """
    relationships = b"""\
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
      <Relationship Id="rId1" Target="worksheets/sheet1.xml"
        Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>
    </Relationships>
    """
    worksheet = b"""\
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <sheetData>
        <row r="1">
          <c r="A1" t="inlineStr"><is><t>date</t></is></c>
          <c r="B1" t="inlineStr"><is><t>reference_start</t></is></c>
          <c r="C1" t="inlineStr"><is><t>target_range</t></is></c>
          <c r="D1" t="inlineStr"><is><t>field</t></is></c>
          <c r="E1" t="inlineStr"><is><t>value</t></is></c>
        </row>
        <row r="2">
          <c r="A2" t="inlineStr"><is><t>2026-06-17</t></is></c>
          <c r="B2"><v>46281</v></c>
          <c r="C2" t="inlineStr"><is><t>350bps - 375bps</t></is></c>
          <c r="D2" t="inlineStr"><is><t>Rate: mean</t></is></c>
          <c r="E2"><v>396.01</v></c>
        </row>
        <row r="3">
          <c r="A3" t="inlineStr"><is><t>2026-06-17</t></is></c>
          <c r="B3"><v>46281</v></c>
          <c r="C3" t="inlineStr"><is><t>350bps - 375bps</t></is></c>
          <c r="D3" t="inlineStr"><is><t>Prob: cut</t></is></c>
          <c r="E3"><v>12.4</v></c>
        </row>
        <row r="4">
          <c r="A4" t="inlineStr"><is><t>2026-06-17</t></is></c>
          <c r="B4"><v>46281</v></c>
          <c r="C4" t="inlineStr"><is><t>350bps - 375bps</t></is></c>
          <c r="D4" t="inlineStr"><is><t>Prob: hike</t></is></c>
          <c r="E4"><v>22.6</v></c>
        </row>
      </sheetData>
    </worksheet>
    """
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return output.getvalue()


def test_atlanta_fed_mpt_parser_builds_market_expectation_records() -> None:
    rows = parse_atlanta_fed_mpt_xlsx(_mpt_workbook())

    assert len(rows) == 1
    assert rows[0]["category"] == "market_expectation"
    assert rows[0]["observed_on"] == "2026-06-17"
    assert rows[0]["mean_rate_bps"] == 396.01
    assert rows[0]["cut_probability"] == 12.4
    assert rows[0]["hike_probability"] == 22.6
    assert rows[0]["evidence_id"].startswith("atlanta-fed-mpt:")


def test_treasury_xml_parser_extracts_two_and_ten_year_yields() -> None:
    payload = b"""\
    <feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
      <entry>
        <content type="application/xml">
          <m:properties>
            <d:NEW_DATE m:type="Edm.DateTime">2026-06-16T00:00:00</d:NEW_DATE>
            <d:BC_2YEAR m:type="Edm.Double">3.71</d:BC_2YEAR>
            <d:BC_10YEAR m:type="Edm.Double">4.19</d:BC_10YEAR>
          </m:properties>
        </content>
      </entry>
      <entry>
        <content type="application/xml">
          <m:properties>
            <d:NEW_DATE m:type="Edm.DateTime">2026-06-17T00:00:00</d:NEW_DATE>
            <d:BC_2YEAR m:type="Edm.Double">3.78</d:BC_2YEAR>
            <d:BC_10YEAR m:type="Edm.Double">4.24</d:BC_10YEAR>
          </m:properties>
        </content>
      </entry>
    </feed>
    """

    rows = parse_treasury_yield_xml(payload)

    assert [row["observed_on"] for row in rows] == [
        "2026-06-16",
        "2026-06-17",
    ]
    assert rows[0]["two_year"] == 3.71
    assert rows[1]["ten_year"] == 4.24
    assert rows[1]["evidence_id"] == "treasury-yields:2026-06-17"


def test_federal_reserve_rss_parser_retains_primary_source_link() -> None:
    payload = b"""\
    <rss version="2.0">
      <channel>
        <item>
          <title>Federal Reserve issues FOMC statement</title>
          <link>https://www.federalreserve.gov/newsevents/pressreleases/test.htm</link>
          <description><![CDATA[The Committee released its statement.]]></description>
          <pubDate>Wed, 17 Jun 2026 18:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    rows = parse_federal_reserve_feed(
        payload,
        feed_key="fed_monetary_policy",
    )

    assert len(rows) == 1
    assert rows[0]["category"] == "official_policy_communication"
    assert rows[0]["published_at"] == "2026-06-17T18:00:00+00:00"
    assert rows[0]["source_url"].startswith("https://www.federalreserve.gov/")
    assert rows[0]["evidence_id"].startswith("fed_monetary_policy:")


def test_configured_fred_returns_real_evidence_health_without_exposing_key() -> None:
    treasury_xml = b"""\
    <feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
      <entry><content><m:properties>
        <d:NEW_DATE>2026-06-17T00:00:00</d:NEW_DATE>
        <d:BC_2YEAR>3.78</d:BC_2YEAR>
        <d:BC_10YEAR>4.24</d:BC_10YEAR>
      </m:properties></content></entry>
    </feed>
    """
    fed_rss = b"""\
    <rss><channel><item>
      <title>Federal Reserve issues FOMC statement</title>
      <link>https://www.federalreserve.gov/example.htm</link>
      <description>Official statement</description>
      <pubDate>Wed, 17 Jun 2026 18:00:00 GMT</pubDate>
    </item></channel></rss>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "home.treasury.gov":
            return httpx.Response(200, content=treasury_xml)
        if request.url.host == "www.federalreserve.gov":
            return httpx.Response(200, content=fed_rss)
        if request.url.host == "www.atlantafed.org":
            return httpx.Response(200, content=_mpt_workbook())
        series_id = request.url.params["series_id"]
        return httpx.Response(
            200,
            json={
                "observations": [
                    {"date": "2026-06-16", "value": "100.0"},
                    {"date": "2026-06-17", "value": "101.0"},
                ],
                "series_id": series_id,
            },
        )

    secret = "f" * 32
    result = fetch_validation_evidence(
        Settings(fred_api_key=secret, _env_file=None),
        occurred_at=[datetime(2026, 6, 17, 18, tzinfo=UTC)],
        transport=httpx.MockTransport(handler),
    )

    assert len(result["fred_observations"]) == len(FRED_VALIDATION_SERIES) * 2
    assert len(result["market_expectations"]) == 1
    assert result["market_expectations"][0]["mean_rate_bps"] == 396.01
    mpt_health = next(
        row for row in result["source_health"] if row["key"] == "atlanta_fed_mpt"
    )
    assert mpt_health["status"] == "ready"
    fred_health = next(row for row in result["source_health"] if row["key"] == "fred")
    assert fred_health["status"] == "ready"
    assert fred_health["observation_count"] == len(FRED_VALIDATION_SERIES) * 2
    assert secret not in json.dumps(result)
