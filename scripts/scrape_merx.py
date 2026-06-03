#!/usr/bin/env python3
"""Public MERX tender intelligence scraper.

Collects only publicly visible MERX listing/detail data. Login-only, paid, or
restricted tabs are recorded as access limitations and are not bypassed.
"""

from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "merx_tenders.sqlite"
DEFAULT_SCHEMA = REPO_ROOT / "db" / "merx_tenders_schema.sql"
DEFAULT_REPORT = REPO_ROOT / "data" / "merx_scrape_report_latest.json"
MERX_BASE = "https://www.merx.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

LISTING_PATHS = {
    "open": "/public/solicitations/open",
    "closed": "/public/solicitations/closed",
    "bid-result": "/public/solicitations/bid-results",
    "awarded": "/public/solicitations/awarded",
}

PROVINCE_TERMS = {
    "all": (None,),
    "ab": ("Alberta", "AB"),
    "bc": ("British Columbia", "BC"),
    "mb": ("Manitoba", "MB"),
    "nb": ("New Brunswick", "NB"),
    "nl": ("Newfoundland and Labrador", "NL"),
    "ns": ("Nova Scotia", "NS"),
    "nt": ("Northwest Territories", "NT"),
    "nu": ("Nunavut", "NU"),
    "on": ("Ontario", "ON"),
    "pe": ("Prince Edward Island", "PE"),
    "qc": ("Quebec", "QC"),
    "sk": ("Saskatchewan", "SK"),
    "yt": ("Yukon", "YT"),
}

PROVINCE_FROM_TEXT = {
    "ALBERTA": "AB",
    "BRITISH COLUMBIA": "BC",
    "MANITOBA": "MB",
    "NEW BRUNSWICK": "NB",
    "NEWFOUNDLAND": "NL",
    "NOVA SCOTIA": "NS",
    "NORTHWEST TERRITORIES": "NT",
    "NUNAVUT": "NU",
    "ONTARIO": "ON",
    "PRINCE EDWARD ISLAND": "PE",
    "QUEBEC": "QC",
    "QUÉBEC": "QC",
    "SASKATCHEWAN": "SK",
    "YUKON": "YT",
}


@dataclass
class ListingTender:
    tender_id: str
    merx_reference: str
    source_url: str
    status: str
    title: str = ""
    issuing_organization: str = ""
    location_text: str = ""
    publication_date_raw: str = ""
    publication_datetime: str | None = None
    closing_date_raw: str = ""
    closing_datetime: str | None = None
    result_date_raw: str = ""
    result_datetime: str | None = None
    summary_text: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class TenderRecord:
    tender_id: str
    merx_reference: str
    solicitation_number: str = ""
    source_id: str = ""
    source_url: str = ""
    title: str = ""
    status: str = ""
    project_type: str = ""
    issuing_organization: str = ""
    owner_organization: str = ""
    location_text: str = ""
    province: str = ""
    country: str = "Canada"
    description: str = ""
    publication_datetime: str | None = None
    publication_date_raw: str = ""
    closing_datetime: str | None = None
    closing_date_raw: str = ""
    bid_intent: str = ""
    bid_intent_deadline: str | None = None
    bid_intent_deadline_raw: str = ""
    question_acceptance_deadline: str | None = None
    question_acceptance_deadline_raw: str = ""
    questions_submitted_online: str = ""
    bid_submission_type: str = ""
    pricing_type: str = ""
    raw_text: str = ""
    raw_html_hash: str = ""
    raw_json: dict[str, Any] = field(default_factory=dict)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u200b", " ")).strip()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def parse_date_text(value: str) -> tuple[str | None, str]:
    raw = clean_text(value)
    if not raw or raw.lower() in {"not available", "n/a", "none"}:
        return None, raw
    match = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})(?:\s+(\d{1,2}):(\d{2})(?:\s*([AP]M))?)?", raw, re.I)
    if not match:
        return None, raw
    year, month, day, hour, minute, ampm = match.groups()
    if hour and minute:
        h = int(hour)
        if ampm:
            if ampm.upper() == "PM" and h != 12:
                h += 12
            elif ampm.upper() == "AM" and h == 12:
                h = 0
        return f"{year}-{month}-{day}T{h:02d}:{int(minute):02d}:00", raw
    return f"{year}-{month}-{day}", raw


def parsed_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def in_date_range(value: str | None, since: date | None, until: date | None) -> bool:
    parsed = parsed_date(value)
    if parsed is None:
        return True
    if since and parsed < since:
        return False
    if until and parsed > until:
        return False
    return True


def cli_date(value: str) -> date | None:
    if not value:
        return None
    if value.lower() == "today":
        return date.today()
    return parsed_date(parse_date_text(value)[0])


def normalize_company_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", clean_text(value).upper()).strip()


def money_value(value: str) -> tuple[float | None, str]:
    raw = clean_text(value)
    # Require an explicit currency marker so bare numbers (e.g. a rank or "1")
    # are never mistaken for a dollar amount.
    match = re.search(r"\$\s*([0-9][0-9,]*)(?:\.([0-9]{1,2}))?", raw)
    if not match:
        return None, raw
    whole = match.group(1).replace(",", "")
    cents = (match.group(2) or "00").ljust(2, "0")[:2]
    return float(f"{whole}.{cents}"), raw


def infer_province(location: str) -> str:
    text = clean_text(location).upper()
    for code in PROVINCE_TERMS:
        if code != "all" and re.search(rf"\b{re.escape(code.upper())}\b", text):
            return code.upper()
    for name, code in PROVINCE_FROM_TEXT.items():
        if name in text:
            return code
    return ""


class Fetcher:
    def __init__(self, delay_seconds: float, retries: int, timeout: int) -> None:
        self.delay_seconds = delay_seconds
        self.retries = retries
        self.timeout = timeout
        self.last_request_at = 0.0

    def fetch(self, url: str) -> tuple[str, int]:
        full_url = urllib.parse.urljoin(MERX_BASE, url)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            wait = self.delay_seconds - (time.time() - self.last_request_at)
            if wait > 0:
                time.sleep(wait)
            request = urllib.request.Request(
                full_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Referer": MERX_BASE + "/",
                },
            )
            try:
                self.last_request_at = time.time()
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = response.read().decode("utf-8", errors="replace")
                    return body, int(response.status)
            except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                last_error = exc
                if isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403, 404}:
                    raise
                time.sleep(min(30.0, (2**attempt) * self.delay_seconds))
        assert last_error is not None
        raise last_error


def listing_url(status: str, page: int, keyword: str | None, sort_by: str = "", sort_direction: str = "") -> str:
    query: dict[str, str] = {}
    if keyword:
        query["keywords"] = keyword
    if page > 1:
        query["pageNumber"] = str(page)
    if sort_by:
        query["sortBy"] = sort_by
    if sort_direction:
        query["sortDirection"] = sort_direction.upper()
    suffix = "?" + urllib.parse.urlencode(query) if query else ""
    return MERX_BASE + LISTING_PATHS[status] + suffix


def notice_id_from_href(href: str) -> str:
    match = re.search(r"/(?:view-notice|award-without-solicitation)/(\d+)|/(\d{7,})(?:\?|$)", href)
    if match:
        return next(group for group in match.groups() if group)
    return sha256_text(href)[:16]


def date_pairs(container: Any) -> dict[str, tuple[str | None, str]]:
    pairs: dict[str, tuple[str | None, str]] = {}
    for label in container.select(".dateLabel"):
        parent = label.parent
        value_node = parent.select_one(".dateValue") if parent else None
        label_text = clean_text(label.get_text(" "))
        value_text = clean_text(value_node.get_text(" ")) if value_node else ""
        if label_text and value_text:
            pairs[label_text.lower()] = parse_date_text(value_text)
    return pairs


def parse_listing(html: str, status: str) -> list[ListingTender]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[ListingTender] = []
    seen: set[str] = set()
    for row_title in soup.select(".rowTitle"):
        anchor = row_title.find_parent("a", href=True)
        if anchor is None:
            continue
        href = str(anchor["href"])
        if not any(token in href for token in ("/solicitations/", "/view-notice/", "/award-without-solicitation/")):
            continue
        merx_reference = notice_id_from_href(href)
        if merx_reference in seen:
            continue
        seen.add(merx_reference)
        title = clean_text(row_title.get_text(" "))
        buyer = class_text(anchor, "buyer-name")
        location = class_text(anchor, "location")
        text = clean_text(anchor.get_text(" "))
        dates = date_pairs(anchor)
        publication, publication_raw = first_date(dates, ("published", "publication"))
        closing, closing_raw = first_date(dates, ("closing", "close"))
        result, result_raw = first_date(dates, ("bid results", "awarded", "award"))
        records.append(
            ListingTender(
                tender_id=f"MERX-{merx_reference}",
                merx_reference=merx_reference,
                source_url=urllib.parse.urljoin(MERX_BASE, href).split("?")[0],
                status=status,
                title=title,
                issuing_organization=buyer,
                location_text=location,
                publication_date_raw=publication_raw,
                publication_datetime=publication,
                closing_date_raw=closing_raw,
                closing_datetime=closing,
                result_date_raw=result_raw,
                result_datetime=result,
                summary_text=text,
                raw={"href": href},
            )
        )
    return records


def first_date(dates: dict[str, tuple[str | None, str]], needles: tuple[str, ...]) -> tuple[str | None, str]:
    for label, value in dates.items():
        if any(needle in label for needle in needles):
            return value
    return None, ""


def class_text(anchor: Any, class_name: str) -> str:
    child = anchor.find(class_=lambda value: value and class_name in str(value).split())
    return clean_text(child.get_text(" ")) if child else ""


def extract_embedded_html(html: str) -> str:
    match = re.search(r"\.html\((['\"])(.*)\1\)\s*;", html, re.S)
    if not match:
        return html
    fragment = match.group(2)
    fragment = fragment.replace("\\/", "/")
    fragment = codecs.decode(fragment, "unicode_escape")
    return fragment


def tab_urls(html: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r'data-ajax-url="([^"]+)"', html)))


def fields_from_html(html: str) -> dict[str, str]:
    soup = BeautifulSoup(extract_embedded_html(html), "html.parser")
    fields: dict[str, str] = {}
    for node in soup.select(".mets-field"):
        label = node.select_one(".mets-field-label")
        body = node.select_one(".mets-field-body")
        if label and body:
            key = clean_text(label.get_text(" "))
            val = clean_text(body.get_text(" "))
            if key and val:
                fields[key] = val
    return fields


def parse_categories(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(extract_embedded_html(html), "html.parser")
    categories: list[dict[str, str]] = []
    for row in soup.find_all("tr"):
        cells = [clean_text(cell.get_text(" ")) for cell in row.find_all(["td", "th"])]
        cells = [cell for cell in cells if cell and cell.lower() not in {"category", "code"}]
        if not cells:
            continue
        text = " | ".join(cells)
        if "selected categories" in text.lower():
            continue
        categories.append({"category_name": cells[-1], "category_code": cells[0] if len(cells) > 1 else "", "category_path": text})
    return dedupe_dicts(categories, ("category_name", "category_code"))


def parse_contacts(fields: dict[str, str], text: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    phone_match = re.search(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}", text)
    for key, value in fields.items():
        if "contact" in key.lower() and value:
            candidates.append({"name": value, "role": key, "phone": "", "email": "", "raw_text": value})
    if email_match or phone_match:
        candidates.append(
            {
                "name": fields.get("Contact", "") or fields.get("Contact Name", ""),
                "role": "Contact",
                "phone": phone_match.group(0) if phone_match else "",
                "email": email_match.group(0) if email_match else "",
                "raw_text": text[:1500],
            }
        )
    return dedupe_dicts(candidates, ("name", "role", "phone", "email"))


def parse_documents(html: str, access_level: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(extract_embedded_html(html), "html.parser")
    text = clean_text(soup.get_text(" "))
    if access_level != "public":
        return [{"title": "Documents tab not publicly visible", "access_level": access_level, "raw_text": text[:1000]}]
    docs: list[dict[str, str]] = []
    for row in soup.find_all("tr"):
        cells = [clean_text(cell.get_text(" ")) for cell in row.find_all(["td", "th"])]
        links = row.find_all("a", href=True)
        if len([c for c in cells if c]) < 2 and not links:
            continue
        title = next((clean_text(a.get_text(" ")) for a in links if clean_text(a.get_text(" "))), cells[0] if cells else "")
        source_url = urllib.parse.urljoin(MERX_BASE, links[0]["href"]) if links else ""
        docs.append(
            {
                "title": title,
                "document_type": cells[1] if len(cells) > 1 else "",
                "source_url": source_url,
                "filename": Path(urllib.parse.urlparse(source_url).path).name if source_url else "",
                "size_text": next((c for c in cells if re.search(r"\b(?:KB|MB|GB)\b", c, re.I)), ""),
                "publication_date": parse_date_text(" ".join(cells))[0] or "",
                "publication_date_raw": " ".join(cells),
                "access_level": "public",
                "raw_text": " | ".join(cells),
            }
        )
    return dedupe_dicts(docs, ("title", "source_url", "filename"))


def org_block_fields(block: Any) -> dict[str, str]:
    """Return label->value for the .mets-field rows inside one org/result block."""
    fields: dict[str, str] = {}
    for node in block.select(".mets-field"):
        label = node.select_one(".mets-field-label") or node.find("label")
        body = node.select_one(".mets-field-body")
        key = clean_text(label.get_text(" ")) if label else ""
        val = clean_text(body.get_text(" ")) if body else ""
        if key and val:
            fields[key] = val
        elif val and "abstractorgaddress" in " ".join(node.get("class", [])).lower():
            fields.setdefault("Address", val)
    return fields


def block_address(block: Any) -> str:
    addr = block.select_one(".abstractOrgAddress")
    if not addr:
        return ""
    body = addr.select_one(".mets-field-body")
    return clean_text(body.get_text(" ")) if body else clean_text(addr.get_text(" "))


def parse_awards(tender_id: str, payload: str) -> list[dict[str, Any]]:
    """Parse the Award tab. Handles one or many awarded suppliers per notice."""
    soup = BeautifulSoup(extract_embedded_html(payload), "html.parser")
    awards: list[dict[str, Any]] = []

    def build(scope: Any, name_hint: str = "") -> dict[str, Any] | None:
        fields = org_block_fields(scope)
        supplier = first_field(fields, ("Supplier Awarded", "Awarded Supplier", "Awardee", "Supplier")) or name_hint
        value_text = first_field(fields, ("Awarded Value", "Total Awarded Value", "Contract Value", "Value"))
        award_date, award_date_raw = parse_date_text(first_field(fields, ("Award Date", "Awarded Date")))
        if not (supplier or value_text or award_date):
            return None
        value, raw_value = money_value(value_text)
        return {
            "tender_id": tender_id,
            "awarded_supplier": supplier,
            "awarded_value": value,
            "awarded_value_text": raw_value,
            "currency": "CAD" if value is not None else "",
            "award_date": award_date,
            "award_date_raw": award_date_raw,
            "contract_number": first_field(fields, ("Contract Number", "Contract #")),
            "contract_dates": first_field(fields, ("Contract Dates", "Contract Period")),
            "description": first_field(fields, ("Description",)),
            "address": fields.get("Address", "") or block_address(scope),
            "raw_text": clean_text(scope.get_text(" "))[:2000],
        }

    for block in soup.select(".bidResultItems, .awardItems, .award-item"):
        title = block.select_one(".content-block-title")
        award = build(block, clean_text(title.get_text(" ")) if title else "")
        if award:
            awards.append(award)
    if not awards:
        award = build(soup)
        if award:
            awards.append(award)
    return awards


def parse_bids(tender_id: str, payload: str) -> list[dict[str, Any]]:
    """Parse the Bid Results tab using the per-bidder .bidResultItems blocks."""
    soup = BeautifulSoup(extract_embedded_html(payload), "html.parser")
    status = ""
    for node in soup.select(".mets-field"):
        label = node.select_one(".mets-field-label")
        body = node.select_one(".mets-field-body")
        if label and body and "publication type" in clean_text(label.get_text(" ")).lower():
            status = clean_text(body.get_text(" "))
            break
    bids: list[dict[str, Any]] = []
    for block in soup.select(".bidResultItems"):
        title = block.select_one(".content-block-title")
        name = clean_text(title.get_text(" ")) if title else ""
        if not name:
            continue
        amount_el = block.select_one(".mets-amount")
        value, raw_value = money_value(clean_text(amount_el.get_text(" ")) if amount_el else "")
        rank_el = block.select_one(".bidRank")
        rank = int(clean_text(rank_el.get_text())) if rank_el and clean_text(rank_el.get_text()).isdigit() else None
        fields = org_block_fields(block)
        bids.append(
            {
                "tender_id": tender_id,
                "bidder_name": name,
                "address": block_address(block),
                "bid_amount": value,
                "bid_amount_text": raw_value,
                "currency": "CAD" if value is not None else "",
                "bid_rank": rank,
                "bid_status": status or "parsed",
                "line_items": fields.get("Line Items", ""),
                "raw_text": clean_text(block.get_text(" "))[:1000],
            }
        )
    return bids


def first_field(fields: dict[str, str], names: tuple[str, ...]) -> str:
    lowered = {key.lower(): value for key, value in fields.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value:
            return value
    for key, value in fields.items():
        if any(name.lower() in key.lower() for name in names):
            return value
    return ""


def dedupe_dicts(items: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        marker = tuple(item.get(key, "") for key in keys)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(item)
    return out


def access_level_for(html: str) -> str:
    text = clean_text(BeautifulSoup(extract_embedded_html(html), "html.parser").get_text(" ")).lower()
    if "must register" in text or "create an account" in text:
        return "requires_registration"
    if "login" in text and "password" in text and len(text) < 1000:
        return "login_required"
    return "public"


def parse_detail(listing: ListingTender, html: str, tab_payloads: dict[str, str]) -> tuple[TenderRecord, dict[str, list[dict[str, Any]]]]:
    soup = BeautifulSoup(html, "html.parser")
    page_text = clean_text(soup.get_text(" "))
    h1 = clean_text(soup.find("h1").get_text(" ")) if soup.find("h1") else ""
    main_fields = fields_from_html(html)
    tab_fields: dict[str, str] = {}
    tab_text: dict[str, str] = {}
    categories: list[dict[str, str]] = []
    documents: list[dict[str, str]] = []
    contacts: list[dict[str, str]] = []
    awards: list[dict[str, Any]] = []
    bids: list[dict[str, Any]] = []
    amendments: list[dict[str, str]] = []
    plan_holders: list[dict[str, str]] = []

    for section, payload in tab_payloads.items():
        fragment = extract_embedded_html(payload)
        text = clean_text(BeautifulSoup(fragment, "html.parser").get_text(" "))
        tab_text[section] = text
        fields = fields_from_html(payload)
        tab_fields.update({key: value for key, value in fields.items() if value})
        access_level = access_level_for(payload)
        if section == "categories":
            categories.extend(parse_categories(payload))
        elif section in {"docs-items", "documents"}:
            documents.extend(parse_documents(payload, access_level))
        elif section in {"docs-request", "plan-holders", "plan-holders-list"} and access_level != "public":
            plan_holders.append({"company_name": "Plan/document request list not publicly visible", "list_type": section, "raw_text": text[:1000]})
        elif "award" in section:
            awards.extend(parse_awards(listing.tender_id, payload))
        elif "bid-results" in section:
            bids.extend(parse_bids(listing.tender_id, payload))

    fields = {**main_fields, **tab_fields}
    solicitation_number = first_field(fields, ("Solicitation Number", "Project Number", "Reference Number"))
    title = listing.title
    if h1 and " - " in h1:
        maybe_number, maybe_title = h1.split(" - ", 1)
        solicitation_number = solicitation_number or maybe_number.strip()
        title = title or maybe_title.strip()
    description = first_field(fields, ("Description", "Details", "Work Description"))
    publication, publication_raw = parse_date_text(first_field(fields, ("Published", "Publication Date", "Published Date"))) if fields else (None, "")
    closing, closing_raw = parse_date_text(first_field(fields, ("Closing Date", "Closing", "Submission Deadline"))) if fields else (None, "")
    bid_intent_deadline, bid_intent_deadline_raw = parse_date_text(first_field(fields, ("Bid Intent Deadline",)))
    question_deadline, question_deadline_raw = parse_date_text(first_field(fields, ("Question Acceptance Deadline", "Questions Deadline")))
    source_id = ""
    source_match = re.search(r"/public/solicitations/(\d+)/abstract", html + " ".join(tab_payloads.values()))
    if source_match:
        source_id = source_match.group(1)
    location = first_field(fields, ("Location", "Delivery Point")) or listing.location_text
    issuing_org = first_field(fields, ("Issuing Organization", "Organization")) or listing.issuing_organization
    owner_org = first_field(fields, ("Owner Organization", "Owner"))
    record = TenderRecord(
        tender_id=listing.tender_id,
        merx_reference=listing.merx_reference,
        solicitation_number=solicitation_number or listing.merx_reference,
        source_id=source_id,
        source_url=listing.source_url,
        title=title,
        status=listing.status,
        project_type=first_field(fields, ("Solicitation Type", "Project Type", "Type")),
        issuing_organization=issuing_org,
        owner_organization=owner_org,
        location_text=location,
        province=infer_province(location),
        country="Canada",
        description=description,
        publication_datetime=publication or listing.publication_datetime,
        publication_date_raw=publication_raw or listing.publication_date_raw,
        closing_datetime=closing or listing.closing_datetime,
        closing_date_raw=closing_raw or listing.closing_date_raw,
        bid_intent=first_field(fields, ("Bid Intent",)),
        bid_intent_deadline=bid_intent_deadline,
        bid_intent_deadline_raw=bid_intent_deadline_raw,
        question_acceptance_deadline=question_deadline,
        question_acceptance_deadline_raw=question_deadline_raw,
        questions_submitted_online=first_field(fields, ("Questions Submitted Online",)),
        bid_submission_type=first_field(fields, ("Bid Submission Type", "Submission Type")),
        pricing_type=first_field(fields, ("Pricing", "Pricing Type")),
        raw_text=page_text[:20000],
        raw_html_hash=sha256_text(html),
        raw_json={"listing": asdict(listing), "fields": fields, "tab_sections": sorted(tab_payloads)},
    )
    contacts.extend(parse_contacts(fields, page_text + " " + " ".join(tab_text.values())))
    if not awards:
        awards.extend(parse_awards(listing.tender_id, fields, page_text + " " + " ".join(tab_text.values())))
    if not bids:
        bids.extend(parse_bids(listing.tender_id, page_text + " " + " ".join(tab_text.values())))
    return record, {
        "categories": dedupe_dicts(categories, ("category_name", "category_code")),
        "documents": dedupe_dicts(documents, ("title", "source_url", "filename")),
        "contacts": dedupe_dicts(contacts, ("name", "role", "phone", "email")),
        "awards": dedupe_dicts(awards, ("awarded_supplier", "awarded_value_text", "award_date")),
        "bids": dedupe_dicts(bids, ("bidder_name", "bid_amount_text", "bid_rank")),
        "amendments": amendments,
        "plan_holders": plan_holders,
    }


def connect(db_path: Path, schema_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    return conn


def upsert_org(conn: sqlite3.Connection, name: str) -> int | None:
    name = clean_text(name)
    if not name:
        return None
    conn.execute("INSERT OR IGNORE INTO organizations (name) VALUES (?)", (name,))
    row = conn.execute("SELECT organization_id FROM organizations WHERE name = ?", (name,)).fetchone()
    return int(row[0]) if row else None


def upsert_company(conn: sqlite3.Connection, name: str, address: str = "", city: str = "", province: str = "", country: str = "") -> int | None:
    name = clean_text(name)
    if not name or "not publicly visible" in name.lower():
        return None
    normalized = normalize_company_name(name)
    conn.execute(
        """
        INSERT INTO companies (normalized_name, display_name, address, city, province, country, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(normalized_name) DO UPDATE SET
            display_name = excluded.display_name,
            address = COALESCE(NULLIF(excluded.address, ''), companies.address),
            city = COALESCE(NULLIF(excluded.city, ''), companies.city),
            province = COALESCE(NULLIF(excluded.province, ''), companies.province),
            country = COALESCE(NULLIF(excluded.country, ''), companies.country),
            updated_at = excluded.updated_at
        """,
        (normalized, name, address, city, province, country),
    )
    row = conn.execute("SELECT company_id FROM companies WHERE normalized_name = ?", (normalized,)).fetchone()
    return int(row[0]) if row else None


def upsert_tender(conn: sqlite3.Connection, record: TenderRecord, seen_at: str) -> str:
    existing = conn.execute("SELECT tender_id FROM tenders WHERE tender_id = ?", (record.tender_id,)).fetchone()
    issuing_id = upsert_org(conn, record.issuing_organization)
    owner_id = upsert_org(conn, record.owner_organization)
    conn.execute(
        """
        INSERT INTO tenders (
            tender_id, merx_reference, solicitation_number, source_id, source_url,
            title, status, project_type, issuing_organization_id, owner_organization_id,
            issuing_organization, owner_organization, location_text, province, country,
            description, publication_datetime, publication_date_raw, closing_datetime,
            closing_date_raw, bid_intent, bid_intent_deadline, bid_intent_deadline_raw,
            question_acceptance_deadline, question_acceptance_deadline_raw,
            questions_submitted_online, bid_submission_type, pricing_type,
            raw_text, raw_html_hash, first_seen_at, last_seen_at, raw_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(tender_id) DO UPDATE SET
            merx_reference = excluded.merx_reference,
            solicitation_number = excluded.solicitation_number,
            source_id = excluded.source_id,
            source_url = excluded.source_url,
            title = excluded.title,
            status = excluded.status,
            project_type = excluded.project_type,
            issuing_organization_id = excluded.issuing_organization_id,
            owner_organization_id = excluded.owner_organization_id,
            issuing_organization = excluded.issuing_organization,
            owner_organization = excluded.owner_organization,
            location_text = excluded.location_text,
            province = excluded.province,
            country = excluded.country,
            description = excluded.description,
            publication_datetime = excluded.publication_datetime,
            publication_date_raw = excluded.publication_date_raw,
            closing_datetime = excluded.closing_datetime,
            closing_date_raw = excluded.closing_date_raw,
            bid_intent = excluded.bid_intent,
            bid_intent_deadline = excluded.bid_intent_deadline,
            bid_intent_deadline_raw = excluded.bid_intent_deadline_raw,
            question_acceptance_deadline = excluded.question_acceptance_deadline,
            question_acceptance_deadline_raw = excluded.question_acceptance_deadline_raw,
            questions_submitted_online = excluded.questions_submitted_online,
            bid_submission_type = excluded.bid_submission_type,
            pricing_type = excluded.pricing_type,
            raw_text = excluded.raw_text,
            raw_html_hash = excluded.raw_html_hash,
            last_seen_at = excluded.last_seen_at,
            raw_json = excluded.raw_json,
            updated_at = excluded.updated_at
        """,
        (
            record.tender_id,
            record.merx_reference,
            record.solicitation_number,
            record.source_id,
            record.source_url,
            record.title,
            record.status,
            record.project_type,
            issuing_id,
            owner_id,
            record.issuing_organization,
            record.owner_organization,
            record.location_text,
            record.province,
            record.country,
            record.description,
            record.publication_datetime,
            record.publication_date_raw,
            record.closing_datetime,
            record.closing_date_raw,
            record.bid_intent,
            record.bid_intent_deadline,
            record.bid_intent_deadline_raw,
            record.question_acceptance_deadline,
            record.question_acceptance_deadline_raw,
            record.questions_submitted_online,
            record.bid_submission_type,
            record.pricing_type,
            record.raw_text,
            record.raw_html_hash,
            seen_at,
            seen_at,
            json.dumps(record.raw_json, ensure_ascii=False, sort_keys=True),
        ),
    )
    return "updated" if existing else "inserted"


def replace_children(conn: sqlite3.Connection, tender_id: str, children: dict[str, list[dict[str, Any]]]) -> None:
    for table in ("tender_categories", "contacts", "documents", "amendments", "plan_holders", "bids", "awards"):
        conn.execute(f"DELETE FROM {table} WHERE tender_id = ?", (tender_id,))
    for category in children["categories"]:
        conn.execute(
            "INSERT OR IGNORE INTO tender_categories (tender_id, category_code, category_name, category_path) VALUES (?, ?, ?, ?)",
            (tender_id, category.get("category_code", ""), category.get("category_name", ""), category.get("category_path", "")),
        )
    for contact in children["contacts"]:
        conn.execute(
            "INSERT OR IGNORE INTO contacts (tender_id, name, role, phone, email, raw_text) VALUES (?, ?, ?, ?, ?, ?)",
            (tender_id, contact.get("name", ""), contact.get("role", ""), contact.get("phone", ""), contact.get("email", ""), contact.get("raw_text", "")),
        )
    for doc in children["documents"]:
        conn.execute(
            """
            INSERT OR IGNORE INTO documents (
                tender_id, title, document_type, source_url, filename, size_text,
                publication_date, publication_date_raw, access_level, raw_text, raw_html_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tender_id,
                doc.get("title", ""),
                doc.get("document_type", ""),
                doc.get("source_url", ""),
                doc.get("filename", ""),
                doc.get("size_text", ""),
                doc.get("publication_date", "") or None,
                doc.get("publication_date_raw", ""),
                doc.get("access_level", "public"),
                doc.get("raw_text", ""),
                sha256_text(doc.get("raw_text", "")),
            ),
        )
    for holder in children["plan_holders"]:
        company_id = upsert_company(conn, holder.get("company_name", ""), holder.get("address", ""), holder.get("city", ""), holder.get("province", ""), holder.get("country", ""))
        conn.execute(
            """
            INSERT OR IGNORE INTO plan_holders (
                tender_id, company_id, company_name, address, city, province, country, list_type, raw_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tender_id, company_id, holder.get("company_name", ""), holder.get("address", ""), holder.get("city", ""), holder.get("province", ""), holder.get("country", ""), holder.get("list_type", ""), holder.get("raw_text", "")),
        )
    for bid in children["bids"]:
        company_id = upsert_company(conn, bid.get("bidder_name", ""), bid.get("address", ""))
        conn.execute(
            """
            INSERT OR IGNORE INTO bids (
                tender_id, bidder_company_id, bidder_name, address, bid_amount,
                bid_amount_text, currency, bid_rank, bid_status, raw_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tender_id, company_id, bid.get("bidder_name", ""), bid.get("address", ""), bid.get("bid_amount"), bid.get("bid_amount_text", ""), bid.get("currency", ""), bid.get("bid_rank"), bid.get("bid_status", ""), bid.get("raw_text", "")),
        )
    for award in children["awards"]:
        company_id = upsert_company(conn, award.get("awarded_supplier", ""))
        conn.execute(
            """
            INSERT OR IGNORE INTO awards (
                tender_id, supplier_company_id, awarded_supplier, awarded_value,
                awarded_value_text, currency, award_date, award_date_raw,
                contract_number, contract_dates, description, raw_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tender_id, company_id, award.get("awarded_supplier", ""), award.get("awarded_value"), award.get("awarded_value_text", ""), award.get("currency", ""), award.get("award_date"), award.get("award_date_raw", ""), award.get("contract_number", ""), award.get("contract_dates", ""), award.get("description", ""), award.get("raw_text", "")),
        )


def insert_raw_page(conn: sqlite3.Connection, tender_id: str | None, run_id: str, url: str, section: str, html: str, status: int, access_level: str) -> None:
    text = clean_text(BeautifulSoup(extract_embedded_html(html), "html.parser").get_text(" "))
    conn.execute(
        """
        INSERT OR IGNORE INTO raw_pages (
            tender_id, run_id, url, section, access_level, fetched_at,
            http_status, raw_html_hash, raw_text, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tender_id, run_id, url, section, access_level, utc_now(), status, sha256_text(html), text[:20000], json.dumps({"text_length": len(text)})),
    )


def log_error(conn: sqlite3.Connection, run_id: str, url: str, error_type: str, message: str, raw: dict[str, Any] | None = None) -> None:
    conn.execute(
        "INSERT INTO scrape_errors (run_id, url, error_type, message, raw_json) VALUES (?, ?, ?, ?, ?)",
        (run_id, url, error_type, message[:2000], json.dumps(raw or {}, ensure_ascii=False)),
    )


def discover(
    conn: sqlite3.Connection,
    fetcher: Fetcher,
    run_id: str,
    statuses: list[str],
    keywords: tuple[str | None, ...],
    since: date | None,
    until: date | None,
    max_pages: int | None,
    sort_by: str,
    sort_direction: str,
) -> tuple[dict[str, ListingTender], int]:
    discovered: dict[str, ListingTender] = {}
    pages_seen = 0
    for status in statuses:
        for keyword in keywords:
            page = 1
            while max_pages is None or page <= max_pages:
                url = listing_url(status, page, keyword, sort_by, sort_direction)
                try:
                    html, http_status = fetcher.fetch(url)
                    pages_seen += 1
                    insert_raw_page(conn, None, run_id, url, f"listing:{status}", html, http_status, "public")
                    listings = parse_listing(html, status)
                except Exception as exc:
                    log_error(conn, run_id, url, type(exc).__name__, str(exc))
                    break
                if not listings:
                    break
                new_on_page = 0
                for listing in listings:
                    primary_date = listing.publication_datetime or listing.result_datetime or listing.closing_datetime
                    if not in_date_range(primary_date, since, until):
                        continue
                    if listing.tender_id not in discovered:
                        new_on_page += 1
                    discovered[listing.tender_id] = listing
                if new_on_page == 0 and page > 40:
                    break
                page += 1
    return discovered, pages_seen


def scrape_details(
    conn: sqlite3.Connection,
    fetcher: Fetcher,
    run_id: str,
    listings: dict[str, ListingTender],
    dry_run: bool,
    detail_limit: int | None,
    resume: bool,
) -> tuple[int, int, int]:
    inserted = updated = skipped = 0
    seen_at = utc_now()
    for index, listing in enumerate(listings.values(), start=1):
        if detail_limit is not None and index > detail_limit:
            skipped += 1
            continue
        if resume:
            existing = conn.execute(
                "SELECT 1 FROM tenders WHERE tender_id = ? AND raw_html_hash IS NOT NULL AND raw_html_hash <> ''",
                (listing.tender_id,),
            ).fetchone()
            if existing:
                skipped += 1
                continue
        try:
            html, http_status = fetcher.fetch(listing.source_url)
            raw_pages_to_insert = [(listing.source_url, "detail", html, http_status, "public")]
            payloads: dict[str, str] = {}
            for tab_url in tab_urls(html):
                section = tab_url.rstrip("/").split("/")[-1]
                full_tab_url = urllib.parse.urljoin(MERX_BASE, tab_url)
                try:
                    tab_html, tab_status = fetcher.fetch(full_tab_url)
                    access = access_level_for(tab_html)
                    raw_pages_to_insert.append((full_tab_url, section, tab_html, tab_status, access))
                    if access == "public":
                        payloads[section] = tab_html
                    else:
                        payloads[section] = tab_html
                except Exception as exc:
                    log_error(conn, run_id, full_tab_url, type(exc).__name__, str(exc), {"tender_id": listing.tender_id, "section": section})
            record, children = parse_detail(listing, html, payloads)
            if dry_run:
                skipped += 1
                continue
            action = upsert_tender(conn, record, seen_at)
            for raw_url, section, raw_html, raw_status, access in raw_pages_to_insert:
                insert_raw_page(conn, listing.tender_id, run_id, raw_url, section, raw_html, raw_status, access)
            replace_children(conn, listing.tender_id, children)
            if action == "inserted":
                inserted += 1
            else:
                updated += 1
        except Exception as exc:
            skipped += 1
            log_error(conn, run_id, listing.source_url, type(exc).__name__, str(exc), {"tender_id": listing.tender_id})
    return inserted, updated, skipped


def quality_report(conn: sqlite3.Connection) -> dict[str, Any]:
    report: dict[str, Any] = {}
    one = lambda sql: conn.execute(sql).fetchone()[0]
    report["total_tenders"] = one("SELECT count(*) FROM tenders")
    report["tenders_by_year"] = rows(conn, "SELECT substr(publication_datetime, 1, 4) AS year, count(*) AS count FROM tenders GROUP BY year ORDER BY year")
    report["tenders_by_province"] = rows(conn, "SELECT COALESCE(NULLIF(province, ''), 'unknown') AS province, count(*) AS count FROM tenders GROUP BY province ORDER BY count DESC")
    report["tenders_by_category"] = rows(conn, "SELECT category_name, count(*) AS count FROM tender_categories GROUP BY category_name ORDER BY count DESC LIMIT 50")
    report["tenders_by_status"] = rows(conn, "SELECT status, count(*) AS count FROM tenders GROUP BY status ORDER BY count DESC")
    report["number_with_contacts"] = one("SELECT count(DISTINCT tender_id) FROM contacts")
    report["number_with_documents_metadata"] = one("SELECT count(DISTINCT tender_id) FROM documents")
    report["number_with_bid_results"] = one("SELECT count(DISTINCT tender_id) FROM bids")
    report["number_with_award_results"] = one("SELECT count(DISTINCT tender_id) FROM awards")
    report["top_issuing_organizations"] = rows(conn, "SELECT issuing_organization AS organization, count(*) AS count FROM tenders WHERE issuing_organization <> '' GROUP BY issuing_organization ORDER BY count DESC LIMIT 25")
    report["top_awarded_suppliers"] = rows(conn, "SELECT awarded_supplier AS supplier, count(*) AS count FROM awards WHERE awarded_supplier <> '' GROUP BY awarded_supplier ORDER BY count DESC LIMIT 25")
    report["suspicious_or_missing_dates"] = rows(
        conn,
        """
        SELECT tender_id, merx_reference, title, publication_datetime, publication_date_raw, closing_datetime, closing_date_raw
        FROM tenders
        WHERE publication_datetime IS NULL
           OR publication_datetime > date('now', '+30 day')
           OR (closing_datetime IS NOT NULL AND closing_datetime NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*')
        LIMIT 100
        """,
    )
    report["scrape_errors"] = rows(conn, "SELECT error_type, count(*) AS count FROM scrape_errors GROUP BY error_type ORDER BY count DESC")
    report["quality_checks"] = {
        "orphan_contacts": one("SELECT count(*) FROM contacts c LEFT JOIN tenders t ON t.tender_id = c.tender_id WHERE t.tender_id IS NULL"),
        "orphan_documents": one("SELECT count(*) FROM documents d LEFT JOIN tenders t ON t.tender_id = d.tender_id WHERE t.tender_id IS NULL"),
        "orphan_bids": one("SELECT count(*) FROM bids b LEFT JOIN tenders t ON t.tender_id = b.tender_id WHERE t.tender_id IS NULL"),
        "orphan_awards": one("SELECT count(*) FROM awards a LEFT JOIN tenders t ON t.tender_id = a.tender_id WHERE t.tender_id IS NULL"),
        "duplicate_merx_reference_numbers": one("SELECT count(*) FROM (SELECT merx_reference FROM tenders WHERE merx_reference IS NOT NULL GROUP BY merx_reference HAVING count(*) > 1)"),
        "datetime_fields_with_prose": one(
            """
            SELECT count(*) FROM tenders
            WHERE (publication_datetime IS NOT NULL AND publication_datetime NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*')
               OR (closing_datetime IS NOT NULL AND closing_datetime NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*')
               OR (bid_intent_deadline IS NOT NULL AND bid_intent_deadline NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*')
               OR (question_acceptance_deadline IS NOT NULL AND question_acceptance_deadline NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*')
            """
        ),
        "missing_source_url": one("SELECT count(*) FROM tenders WHERE source_url IS NULL OR source_url = ''"),
        "bids_missing_company_link": one("SELECT count(*) FROM bids WHERE bidder_name <> '' AND bidder_company_id IS NULL"),
        "awards_missing_supplier_link": one("SELECT count(*) FROM awards WHERE awarded_supplier <> '' AND supplier_company_id IS NULL"),
    }
    report["access_limitations"] = rows(conn, "SELECT section, access_level, count(*) AS count FROM raw_pages WHERE access_level <> 'public' GROUP BY section, access_level ORDER BY count DESC")
    return report


def rows(conn: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql)]


def write_report(conn: sqlite3.Connection, report_path: Path) -> dict[str, Any]:
    report = quality_report(conn)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape publicly visible MERX tender intelligence into SQLite.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--since", default="2023-01-01")
    parser.add_argument("--until", default=date.today().isoformat())
    parser.add_argument("--province", default="all", help="all or province code like ns/on/bc.")
    parser.add_argument("--category", default="all", help="Reserved for future MERX category IDs; currently logged only.")
    parser.add_argument("--keyword", action="append", dest="keywords", help="Extra keyword search. Repeatable.")
    parser.add_argument("--status", action="append", dest="statuses", choices=sorted(LISTING_PATHS), help="Limit to one or more status paths.")
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--detail-limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--sort-by", default="")
    parser.add_argument("--sort-direction", default="")
    parser.add_argument("--headless", action="store_true", help="Accepted for CLI compatibility; scraper uses HTTP public pages.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    since_date = cli_date(args.since)
    until_date = cli_date(args.until)
    province_key = args.province.lower()
    keywords: tuple[str | None, ...]
    if args.keywords:
        keywords = tuple(args.keywords)
    else:
        keywords = tuple(PROVINCE_TERMS.get(province_key, (args.province,)))
    statuses = args.statuses or list(LISTING_PATHS)
    run_id = "merx:" + re.sub(r"[^0-9A-Za-z]+", "", utc_now())
    command = " ".join(sys.argv)
    fetcher = Fetcher(args.delay_seconds, args.retries, args.timeout)

    with connect(args.db, args.schema) as conn:
        conn.execute(
            """
            INSERT INTO scrape_runs (
                run_id, started_at, status, command, since_date, until_date,
                province, category, notes
            ) VALUES (?, ?, 'running', ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                utc_now(),
                command,
                args.since,
                args.until,
                args.province,
                args.category,
                json.dumps({"statuses": statuses, "keywords": keywords, "dry_run": args.dry_run}),
            ),
        )
        discovered, pages_seen = discover(
            conn,
            fetcher,
            run_id,
            statuses,
            keywords,
            since_date,
            until_date,
            args.max_pages,
            args.sort_by,
            args.sort_direction,
        )
        inserted, updated, skipped = scrape_details(conn, fetcher, run_id, discovered, args.dry_run, args.detail_limit, args.resume)
        error_count = conn.execute("SELECT count(*) FROM scrape_errors WHERE run_id = ?", (run_id,)).fetchone()[0]
        conn.execute(
            """
            UPDATE scrape_runs
            SET completed_at = ?, status = 'completed', pages_seen = ?,
                tenders_seen = ?, inserted = ?, updated = ?, skipped = ?, errors = ?
            WHERE run_id = ?
            """,
            (utc_now(), pages_seen, len(discovered), inserted, updated, skipped, error_count, run_id),
        )
        report = write_report(conn, args.report)
        conn.commit()

    print(f"SQLite database: {args.db}")
    print(f"Run id: {run_id}")
    print(f"Pages seen: {pages_seen}")
    print(f"Tenders discovered: {len(discovered)}")
    print(f"Inserted: {inserted}")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {error_count}")
    print(f"Report: {args.report}")
    print(json.dumps({k: report[k] for k in ("total_tenders", "number_with_contacts", "number_with_documents_metadata", "number_with_bid_results", "number_with_award_results")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
