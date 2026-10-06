"""Archive first-batch official announcements and extract source-reported clocks.

This is a provenance probe, not a claim that today's HTML is the original version
or that the timestamp is the market's first knowledge. It does not enqueue jobs.
"""

import asyncio
import hashlib
import json
import re
from contextlib import suppress
from datetime import UTC, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.filing_timing import parse_accepted_at

SOURCES = {
    "AAPL": "https://images.apple.com/newsroom/2026/07/apple-reports-third-quarter-results/",
    "AMD": "https://ir.amd.com/news-events/press-releases/detail/1295/"
    "amd-reports-second-quarter-2026-financial-results",
    "NVDA": "https://nvidianews.nvidia.com/news/"
    "nvidia-announces-financial-results-for-second-quarter-fiscal-2027/",
}


class PublicationTags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.candidates = []
        self.current = None
        self.jsonld = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "time" and "datetime" in attrs:
            self.current = {"value": attrs["datetime"], "text": "", "kind": "time"}
        if tag == "meta" and (attrs.get("property") or attrs.get("name")) in (
            "article:published_time",
            "datePublished",
            "date-published",
        ):
            self.candidates.append(
                {"value": attrs.get("content", ""), "text": "", "kind": "published_meta"}
            )
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.jsonld = ""

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data
        if self.jsonld is not None:
            self.jsonld += data

    def handle_endtag(self, tag):
        if tag == "time" and self.current is not None:
            self.candidates.append(self.current)
            self.current = None
        if tag == "script" and self.jsonld is not None:
            with suppress(ValueError):
                self._read_json(json.loads(self.jsonld))
            self.jsonld = None

    def _read_json(self, value):
        if isinstance(value, list):
            for item in value:
                self._read_json(item)
        elif isinstance(value, dict):
            if value.get("@type") in ("NewsArticle", "Article", "PressRelease") and isinstance(
                value.get("datePublished"), str
            ):
                self.candidates.append(
                    {"value": value["datePublished"], "text": "", "kind": "article_jsonld"}
                )
            if "@graph" in value:
                self._read_json(value["@graph"])


def publication_candidates(html: str) -> list[dict]:
    parser = PublicationTags()
    parser.feed(html)
    candidates = []
    for item in parser.candidates:
        raw = item["value"]
        if not re.match(r"\d{4}-\d{2}-\d{2}", raw):
            continue  # Ignore copyright years, never infer midnight.
        stamp = parse_accepted_at(raw)
        precision = "second" if stamp else "unknown"
        if (
            not stamp
            and item["kind"] == "time"
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00", raw)
        ):
            zones = re.findall(r"\b(EDT|EST|PDT|PST|UTC)\b", item["text"])
            if len(set(zones)) == 1:
                offset = {"EDT": -4, "EST": -5, "PDT": -7, "PST": -8, "UTC": 0}[zones[0]]
                try:
                    stamp = (
                        datetime.fromisoformat(raw)
                        .replace(
                            tzinfo=timezone(timedelta(hours=offset)),
                        )
                        .astimezone(UTC)
                    )
                    precision = "minute"
                except ValueError:
                    pass
        candidates.append(
            {
                "raw_value": raw,
                "visible_time_text": item["text"].strip(),
                "source_field": item["kind"],
                "precision": precision,
                "window_start_utc": stamp.isoformat() if stamp else None,
                "window_end_exclusive_utc": (
                    stamp + timedelta(seconds=60 if precision == "minute" else 1)
                ).isoformat()
                if stamp
                else None,
            }
        )
    return candidates


def retain_release(root: Path, ticker: str, url: str, content: bytes) -> dict:
    digest = hashlib.sha256(content).hexdigest()
    folder = root / "raw/earnings-releases" / ticker
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{digest}.html"
    try:
        with target.open("xb") as output:
            output.write(content)
    except FileExistsError:
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("archive_integrity_error") from None
    record = {
        "ticker": ticker,
        "source_url": url,
        "sha256": digest,
        "archive_path": str(target.relative_to(root)),
        "observed_at": datetime.now(UTC).isoformat(),
        "publication_candidates": publication_candidates(content.decode("utf-8", errors="replace")),
        "original_historical_version_verified": False,
        "execution_permitted": False,
    }
    # One immutable probe per downloaded version; repeated probes preserve the audit record.
    try:
        with (folder / f"{digest}.json").open("x", encoding="utf-8") as output:
            json.dump(record, output, indent=2, ensure_ascii=False)
    except FileExistsError:
        pass
    return record


async def run():
    results = []
    async with httpx.AsyncClient(
        timeout=45, headers={"User-Agent": "ORAKT public research"}
    ) as client:
        for ticker, url in SOURCES.items():
            try:
                response = await client.get(url)
                response.raise_for_status()
                results.append(
                    retain_release(get_settings().cold_data_root, ticker, url, response.content)
                )
            except (httpx.HTTPError, ValueError) as exc:
                results.append({"ticker": ticker, "error": type(exc).__name__})
    return results


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
