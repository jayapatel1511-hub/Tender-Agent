#!/usr/bin/env python3
"""Scrape public MERX bid-result and award summary pages into a second SQLite DB."""

from __future__ import annotations

import argparse
import io
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = REPO_ROOT / "data" / "bid-results.sqlite"
DEFAULT_SCHEMA = REPO_ROOT / "db" / "bid_results_schema.sql"
MERX_BASE = "https://www.merx.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

DEFAULT_KEYWORDS = ("Nova Scotia", "NS")
RESULT_PATHS = {
    "bid-result": "/public/solicitations/bid-results",
    "awarded": "/public/solicitations/awarded",
}
DCC_RECENT_AWARDS_URL = (
    "https://dccmft.dcc-cdc.gc.ca/?p=public&path=%2FRecently_Awarded_Contracts.pdf&u=contracts_public"
)
BUYER_AWARD_SOURCES = {
    "dcc-recently-awarded-contracts": DCC_RECENT_AWARDS_URL,
}


@dataclass
class ResultNotice:
    notice_id: str
    result_type: str
    title: str
    buyer: str
    location: str
    published_date: str
    result_date: str
    detail_url: str
    solicitation_id: str
    summary_text: str
    raw: dict[str, Any]


@dataclass
class AwardDetail:
    notice_id: str
    supplier_name: str
    awarded_value: str
    award_date: str
    contract_dates: str
    confidence: str
    raw_text: str


@dataclass
class BidderResult:
    notice_id: str
    bidder_name: str
    bid_amount: str
    is_awarded: int
    rank: int | None
    confidence: str
    raw_text: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def iso_date(value: str) -> str:
    text = value.strip().replace("/", "-")
    return text


def parse_iso_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(iso_date(value))
    except ValueError:
        return None


def within_date_window(value: str, since_date: date | None, until_date: date | None) -> bool:
    parsed = parse_iso_date(value)
    if parsed is None:
        return True
    if since_date and parsed < since_date:
        return False
    if until_date and parsed > until_date:
        return False
    return True


def fetch_bytes(url: str, timeout: int = 30) -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
            "Referer": MERX_BASE + "/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        return response.read(), content_type


def fetch_text(url: str, timeout: int = 30) -> str:
    body, content_type = fetch_bytes(url, timeout)
    if "pdf" in content_type.lower() or body.startswith(b"%PDF"):
        return pdf_text(body)
    return body.decode("utf-8", errors="replace")


def pdf_text(body: bytes) -> str:
    reader = PdfReader(io.BytesIO(body))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def listing_url(
    result_type: str,
    keyword: str | None,
    page: int,
    sort_by: str = "",
    sort_direction: str = "",
) -> str:
    query = {}
    if keyword:
        query["keywords"] = keyword
    if page > 1:
        query["pageNumber"] = str(page)
    if sort_by:
        query["sortBy"] = sort_by
    if sort_direction:
        query["sortDirection"] = sort_direction.upper()
    suffix = "?" + urllib.parse.urlencode(query) if query else ""
    return MERX_BASE + RESULT_PATHS[result_type] + suffix


def parse_listing(html: str, result_type: str) -> list[ResultNotice]:
    soup = BeautifulSoup(html, "html.parser")
    notices: list[ResultNotice] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        text = normalize_space(anchor.get_text(" "))
        if not text or "Published" not in text:
            continue
        if result_type == "bid-result" and "Published Bid Results" not in text:
            continue
        if result_type == "awarded" and "Awarded" not in text:
            continue
        if not any(token in href for token in ("/solicitations/", "/view-notice/", "/award-without-solicitation/")):
            continue

        notice_id = notice_id_from(href, text)
        if not notice_id or notice_id in seen:
            continue
        seen.add(notice_id)

        title = class_text(anchor, "rowTitle")
        buyer = class_text(anchor, "buyer-name")
        location = class_text(anchor, "location")
        published_date, result_date = parse_dates(text, result_type)
        if not title:
            title = parse_title_from_summary(text, buyer, location, result_type)

        detail_url = urllib.parse.urljoin(MERX_BASE, href).split("?")[0]
        notices.append(
            ResultNotice(
                notice_id=notice_id,
                result_type=result_type,
                title=title,
                buyer=buyer,
                location=location,
                published_date=published_date,
                result_date=result_date,
                detail_url=detail_url,
                solicitation_id="",
                summary_text=text,
                raw={"href": href},
            )
        )
    return notices


def class_text(anchor: Any, class_name: str) -> str:
    child = anchor.find(class_=lambda value: value and class_name in str(value).split())
    if child is None:
        return ""
    return normalize_space(child.get_text(" "))


def notice_id_from(href: str, text: str) -> str:
    href_match = re.search(r"/(?:view-notice|award-without-solicitation)/(\d+)|/(\d{7,})(?:\?|$)", href)
    if href_match:
        return next(group for group in href_match.groups() if group)
    text_match = re.search(r"(\d{7,})\s*(?:\(opens|$)", text)
    return text_match.group(1) if text_match else ""


def parse_dates(text: str, result_type: str) -> tuple[str, str]:
    if result_type == "bid-result":
        match = re.search(r"Published\s+(\d{4}/\d{2}/\d{2})\s+Published Bid Results\s+(\d{4}/\d{2}/\d{2})", text)
    else:
        match = re.search(r"Published\s+(\d{4}/\d{2}/\d{2}|Not Available)\s+Awarded\s+(\d{4}/\d{2}/\d{2})", text)
    if not match:
        return "", ""
    published = "" if match.group(1) == "Not Available" else iso_date(match.group(1))
    return published, iso_date(match.group(2))


def parse_title_from_summary(text: str, buyer: str, location: str, result_type: str) -> str:
    marker = "Published Bid Results" if result_type == "bid-result" else "Awarded"
    before_dates = re.split(r"\s+Published\s+(?:\d{4}/\d{2}/\d{2}|Not Available)\s+" + re.escape(marker), text)[0]
    for suffix in (buyer, location):
        if suffix and suffix in before_dates:
            before_dates = before_dates.split(suffix)[0]
    return normalize_space(before_dates)


def enrich_notice(notice: ResultNotice, delay_seconds: float = 0.5) -> tuple[ResultNotice, list[AwardDetail], list[BidderResult]]:
    award_details: list[AwardDetail] = []
    bidder_results: list[BidderResult] = []
    try:
        html = fetch_text(notice.detail_url)
    except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        notice.raw["detail_error"] = str(exc)
        return notice, award_details, bidder_results

    notice.raw["detail_text_sample"] = normalize_space(strip_html(html))[:2000]
    solicitation_id = solicitation_id_from(html)
    notice.solicitation_id = solicitation_id
    tab_urls = tab_urls_from(html)
    notice.raw["tab_urls"] = tab_urls

    combined_texts = [strip_html(html)]
    for tab_url in tab_urls:
        if (notice.result_type == "awarded" and "/award" not in tab_url) or (
            notice.result_type == "bid-result" and "/bid-results" not in tab_url
        ):
            continue
        time.sleep(delay_seconds)
        try:
            tab_text = fetch_text(urllib.parse.urljoin(MERX_BASE, tab_url))
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            notice.raw.setdefault("tab_errors", {})[tab_url] = str(exc)
            continue
        if "SAMLRequest" in tab_text and "idp.merx.com" in tab_text:
            notice.raw.setdefault("tab_errors", {})[tab_url] = "login_required"
            continue
        combined_texts.append(strip_html(tab_text))

    combined = "\n".join(combined_texts)
    if notice.result_type == "awarded":
        award_details.extend(parse_awards(notice.notice_id, combined))
    else:
        bidder_results.extend(parse_bidder_results(notice.notice_id, combined))
    return notice, award_details, bidder_results


def strip_html(value: str) -> str:
    if "<" not in value or ">" not in value:
        return normalize_space(value)
    soup = BeautifulSoup(value, "html.parser")
    return normalize_space(soup.get_text(" "))


def solicitation_id_from(html: str) -> str:
    match = re.search(r"/public/solicitations/(\d+)/abstract", html)
    return match.group(1) if match else ""


def tab_urls_from(html: str) -> list[str]:
    urls = []
    for match in re.finditer(r'data-ajax-url="([^"]+)"', html):
        url = match.group(1)
        if "/abstract/" in url and url not in urls:
            urls.append(url)
    return urls


def parse_awards(notice_id: str, text: str) -> list[AwardDetail]:
    text = normalize_space(text)
    supplier = value_after(text, ("Supplier Awarded", "Awardee", "Supplier"))
    awarded_value = money_after(text, ("Awarded Value", "Total Awarded Value", "Contract Value"))
    award_date = date_after(text, ("Award Date", "Awarded"))
    contract_dates = value_after(text, ("Contract Dates",))
    if supplier or awarded_value or award_date:
        return [
            AwardDetail(
                notice_id=notice_id,
                supplier_name=supplier,
                awarded_value=awarded_value,
                award_date=award_date,
                contract_dates=contract_dates,
                confidence="detail",
                raw_text=text[:2000],
            )
        ]
    return []


def parse_bidder_results(notice_id: str, text: str) -> list[BidderResult]:
    text = normalize_space(text)
    results: list[BidderResult] = []
    money_pattern = re.compile(r"([A-Z][A-Za-z0-9&.,'()/ -]{2,80}?)\s+(\$[0-9][0-9,]*(?:\.[0-9]{2})?\s*(?:CAD)?)")
    for index, match in enumerate(money_pattern.finditer(text), start=1):
        bidder = normalize_space(match.group(1))
        lower_bidder = bidder.lower()
        if any(
            skip in lower_bidder
            for skip in (
                "estimated cost",
                "total cost",
                "awarded value",
                "price /",
                "payments made",
                "construction contracts over",
            )
        ):
            continue
        results.append(
            BidderResult(
                notice_id=notice_id,
                bidder_name=bidder,
                bid_amount=match.group(2),
                is_awarded=1 if "award" in bidder.lower() else 0,
                rank=index,
                confidence="detail-money-pattern",
                raw_text=text[max(0, match.start() - 250) : match.end() + 250],
            )
        )
    return results[:50]


def parse_dcc_recent_awards(text: str) -> list[tuple[ResultNotice, AwardDetail]]:
    normalized = normalize_space(text)
    row_pattern = re.compile(r"(?=[A-Z]{2}\d{6}\s+\d{5}\b)")
    provinces = "AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|QC|SK|YT"
    parsed: list[tuple[ResultNotice, AwardDetail]] = []
    for row in row_pattern.split(normalized):
        row = row.strip()
        if not row:
            continue
        header = re.match(r"(?P<project>[A-Z]{2}\d{6})\s+(?P<subproject>\d{5})(?:\s+(?P<reference>\d{6}))?\s+(?P<rest>.*)", row)
        if not header:
            continue
        amount_match = re.search(r"(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<amount>\$[0-9][0-9,]*\.[0-9]{2})\s+", header.group("rest"))
        if not amount_match:
            continue
        before_amount = normalize_space(header.group("rest")[: amount_match.start()])
        after_amount = normalize_space(header.group("rest")[amount_match.end() :])
        supplier_match = re.match(
            rf"(?P<supplier>.+)\s+(?P<city>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){{0,2}})\s+(?P<province>{provinces})(?:\s+.*)?$",
            after_amount,
        )
        if not supplier_match:
            continue

        reference = header.group("reference") or ""
        if reference:
            notice_id = f"0000{reference}" if len(reference) == 6 else reference
        else:
            notice_id = f"DCC-{header.group('project')}-{header.group('subproject')}"
        title, location = split_dcc_title_location(before_amount)
        raw_text = row
        notice = ResultNotice(
            notice_id=notice_id,
            result_type="awarded",
            title=title,
            buyer="Defence Construction Canada",
            location=location,
            published_date="",
            result_date=amount_match.group("date"),
            detail_url=DCC_RECENT_AWARDS_URL,
            solicitation_id=f"{header.group('project')}-{header.group('subproject')}",
            summary_text=raw_text,
            raw={
                "source": "dcc-recently-awarded-contracts",
                "project": header.group("project"),
                "subproject": header.group("subproject"),
                "reference": reference,
                "supplier_city": normalize_space(supplier_match.group("city")),
                "supplier_province": supplier_match.group("province"),
            },
        )
        award = AwardDetail(
            notice_id=notice_id,
            supplier_name=normalize_space(supplier_match.group("supplier")),
            awarded_value=amount_match.group("amount"),
            award_date=amount_match.group("date"),
            contract_dates="",
            confidence="detail",
            raw_text=raw_text,
        )
        parsed.append((notice, award))
    return parsed


def collect_buyer_award_sources() -> tuple[list[tuple[ResultNotice, AwardDetail]], dict[str, Any]]:
    awards: list[tuple[ResultNotice, AwardDetail]] = []
    stats: dict[str, Any] = {}
    dcc_url = BUYER_AWARD_SOURCES["dcc-recently-awarded-contracts"]
    try:
        dcc_pdf, _ = fetch_bytes(dcc_url, timeout=60)
        dcc_awards = parse_dcc_recent_awards(pdf_text(dcc_pdf))
        awards.extend(dcc_awards)
        stats["dcc-recently-awarded-contracts"] = {
            "url": dcc_url,
            "awards": len(dcc_awards),
        }
    except Exception as exc:
        stats["dcc-recently-awarded-contracts"] = {
            "url": dcc_url,
            "error": str(exc),
        }
    return awards, stats


def split_dcc_title_location(value: str) -> tuple[str, str]:
    known_location_terms = (
        "Greenwood",
        "CFB Halifax",
        "Halifax",
        "Oromocto",
        "Petawawa",
        "Kingston",
        "Trenton",
        "CFB Edmonton",
        "CFB Esquimalt",
        "Bagotville",
        "CFB Wainwright",
    )
    for location in known_location_terms:
        marker = f" {location}"
        if marker in value:
            title = value.split(marker, 1)[0]
            return normalize_space(title), normalize_space(value[len(title) :])
    return value, ""


def value_after(text: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        match = re.search(re.escape(label) + r"\s+(.{1,160}?)(?:\s+(?:Awarded Value|Award Date|Contract Dates|Description|Address|Contact Information)\b|$)", text, re.I)
        if match:
            return normalize_space(match.group(1))
    return ""


def money_after(text: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        match = re.search(re.escape(label) + r".{0,80}?(\$[0-9][0-9,]*(?:\.[0-9]{2})?(?:\s*CAD)?)", text, re.I)
        if match:
            return match.group(1)
    return ""


def date_after(text: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        match = re.search(re.escape(label) + r".{0,80}?(\d{4}/\d{2}/\d{2}|\d{4}-\d{2}-\d{2})", text, re.I)
        if match:
            return iso_date(match.group(1))
    return ""


def connect(database: Path, schema: Path) -> sqlite3.Connection:
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(schema.read_text(encoding="utf-8"))
    return connection


def upsert_notice(connection: sqlite3.Connection, notice: ResultNotice, seen_at: str) -> None:
    source = str(notice.raw.get("source") or "merx-public-results")
    connection.execute(
        """
        INSERT INTO result_notices (
            notice_id, result_type, title, buyer, location, published_date,
            result_date, detail_url, solicitation_id, summary_text, source,
            first_seen_at, last_seen_at, raw_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(notice_id) DO UPDATE SET
            result_type = excluded.result_type,
            title = excluded.title,
            buyer = excluded.buyer,
            location = excluded.location,
            published_date = excluded.published_date,
            result_date = excluded.result_date,
            detail_url = excluded.detail_url,
            solicitation_id = excluded.solicitation_id,
            summary_text = excluded.summary_text,
            source = excluded.source,
            last_seen_at = excluded.last_seen_at,
            raw_json = excluded.raw_json,
            updated_at = excluded.updated_at
        """,
        (
            notice.notice_id,
            notice.result_type,
            notice.title,
            notice.buyer,
            notice.location,
            notice.published_date,
            notice.result_date,
            notice.detail_url,
            notice.solicitation_id,
            notice.summary_text,
            source,
            seen_at,
            seen_at,
            json.dumps(asdict(notice), ensure_ascii=False, sort_keys=True),
        ),
    )


def insert_award(connection: sqlite3.Connection, award: AwardDetail) -> None:
    connection.execute(
        """
        DELETE FROM award_details
        WHERE notice_id = ?
          AND awarded_value = ?
          AND award_date = ?
          AND supplier_name != ?
          AND (
              supplier_name LIKE ? || '%'
              OR ? LIKE supplier_name || '%'
          )
        """,
        (
            award.notice_id,
            award.awarded_value,
            award.award_date,
            award.supplier_name,
            award.supplier_name,
            award.supplier_name,
        ),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO award_details (
            notice_id, supplier_name, awarded_value, award_date,
            contract_dates, confidence, raw_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            award.notice_id,
            award.supplier_name,
            award.awarded_value,
            award.award_date,
            award.contract_dates,
            award.confidence,
            award.raw_text,
        ),
    )


def insert_bid(connection: sqlite3.Connection, bid: BidderResult) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO bidder_results (
            notice_id, bidder_name, bid_amount, is_awarded,
            rank, confidence, raw_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bid.notice_id,
            bid.bidder_name,
            bid.bid_amount,
            bid.is_awarded,
            bid.rank,
            bid.confidence,
            bid.raw_text,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape MERX bid results and award summaries into SQLite.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--detail-limit", type=int, default=10)
    parser.add_argument("--keyword", action="append", dest="keywords", help="Keyword/location to search. Repeatable.")
    parser.add_argument("--all-merx", action="store_true", help="Scrape MERX result pages without a keyword filter.")
    parser.add_argument("--since-date", help="Keep result notices on or after this date, e.g. 2023-01-01.")
    parser.add_argument("--until-date", help="Keep result notices on or before this date. Defaults to no upper bound.")
    parser.add_argument("--sort-by", default="", help="MERX sort field, e.g. bidResultsPublicationDate or publicationDate.")
    parser.add_argument("--sort-direction", default="", choices=("", "ASC", "DESC", "asc", "desc"), help="MERX sort direction.")
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    parser.add_argument("--no-details", action="store_true")
    parser.add_argument("--skip-buyer-awards", action="store_true")
    parser.add_argument("--skip-dcc-awards", action="store_true")
    args = parser.parse_args()

    started = utc_now()
    run_id = "bid-results:" + re.sub(r"[^0-9A-Za-z]+", "", started)
    keywords: tuple[str | None, ...] = (None,) if args.all_merx else tuple(args.keywords or DEFAULT_KEYWORDS)
    since_date = parse_iso_date(args.since_date or "")
    until_date = parse_iso_date(args.until_date or "")
    all_notices: dict[str, ResultNotice] = {}
    listing_errors: list[str] = []

    for result_type in RESULT_PATHS:
        for keyword in keywords:
            for page in range(1, args.max_pages + 1):
                url = listing_url(result_type, keyword, page, args.sort_by, args.sort_direction)
                try:
                    html = fetch_text(url)
                except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                    listing_errors.append(f"{url}: {exc}")
                    break
                notices = parse_listing(html, result_type)
                if not notices:
                    break
                for notice in notices:
                    if within_date_window(notice.result_date, since_date, until_date):
                        all_notices[notice.notice_id] = notice
                time.sleep(args.delay_seconds)

    detail_count = 0
    award_count = 0
    bid_count = 0
    seen_at = utc_now()
    buyer_awards: list[tuple[ResultNotice, AwardDetail]] = []
    buyer_award_stats: dict[str, Any] = {}
    if not args.skip_buyer_awards and not args.skip_dcc_awards:
        buyer_awards, buyer_award_stats = collect_buyer_award_sources()
        buyer_awards = [
            (notice, award)
            for notice, award in buyer_awards
            if within_date_window(notice.result_date, since_date, until_date)
        ]
        for notice, _award in buyer_awards:
            all_notices[notice.notice_id] = notice

    with connect(args.database, args.schema) as connection:
        connection.execute(
            "INSERT OR REPLACE INTO result_runs (run_id, source, started_at, status, notes) VALUES (?, ?, ?, 'running', ?)",
            (
                run_id,
                "merx-public-results",
                started,
                json.dumps(
                    {
                        "keywords": keywords,
                        "all_merx": args.all_merx,
                        "max_pages": args.max_pages,
                        "since_date": args.since_date,
                        "until_date": args.until_date,
                        "sort_by": args.sort_by,
                        "sort_direction": args.sort_direction,
                    }
                ),
            ),
        )
        for notice in sorted(all_notices.values(), key=detail_priority):
            awards: list[AwardDetail] = []
            bids: list[BidderResult] = []
            if not args.no_details and detail_count < args.detail_limit:
                notice, awards, bids = enrich_notice(notice, args.delay_seconds)
                detail_count += 1
            upsert_notice(connection, notice, seen_at)
            for award in awards:
                insert_award(connection, award)
                award_count += 1
            for bid in bids:
                insert_bid(connection, bid)
                bid_count += 1
        for notice, award in buyer_awards:
            upsert_notice(connection, notice, seen_at)
            insert_award(connection, award)
            award_count += 1
        completed = utc_now()
        connection.execute(
            "UPDATE result_runs SET completed_at = ?, status = 'completed', notes = ? WHERE run_id = ?",
            (
                completed,
                json.dumps(
                    {
                        "keywords": keywords,
                        "all_merx": args.all_merx,
                        "max_pages": args.max_pages,
                        "since_date": args.since_date,
                        "until_date": args.until_date,
                        "sort_by": args.sort_by,
                        "sort_direction": args.sort_direction,
                        "notices": len(all_notices),
                        "details_checked": detail_count,
                        "awards_parsed": award_count,
                        "bids_parsed": bid_count,
                        "listing_errors": listing_errors,
                        "buyer_award_sources": buyer_award_stats,
                    },
                    ensure_ascii=False,
                ),
                run_id,
            ),
        )
        connection.commit()

    print(f"SQLite database: {args.database}")
    print(f"Run id: {run_id}")
    print(f"Notices: {len(all_notices)}")
    print(f"Details checked: {detail_count}")
    print(f"Awards parsed: {award_count}")
    print(f"Bid rows parsed: {bid_count}")
    if listing_errors:
        print("Listing errors:")
        for error in listing_errors:
            print(f"- {error}")
    return 0


def detail_priority(notice: ResultNotice) -> tuple[int, str, str]:
    if "/award-without-solicitation/" in notice.detail_url:
        group = 0
    elif notice.result_type == "awarded":
        group = 1
    else:
        group = 2
    return (group, notice.result_date or "", notice.notice_id)


if __name__ == "__main__":
    raise SystemExit(main())
