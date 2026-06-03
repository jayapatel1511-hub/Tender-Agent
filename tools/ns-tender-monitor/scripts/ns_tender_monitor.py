from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


BASE_URL = "https://procurement-portal.novascotia.ca"
SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROPOSAL_REPO = REPO_ROOT
DEFAULT_CRITERIA = REPO_ROOT / "config" / "targeted-stream-criteria.json"
DEFAULT_STATE = REPO_ROOT / "data" / "seen_tenders_state.json"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def request_json(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    method: str = "GET",
    data: Any | None = None,
    token: str | None = None,
) -> Any:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": f"{BASE_URL}/tenders",
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8") if data != "null" else b"null"
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with opener.open(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
    if raw.lstrip().startswith("<"):
        raise RuntimeError(f"Portal returned HTML instead of JSON for {url}: {raw[:160]}")
    return json.loads(raw)


def authenticate(opener: urllib.request.OpenerDirector) -> str:
    opener.open(
        urllib.request.Request(
            f"{BASE_URL}/tenders",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "text/html",
            },
        ),
        timeout=30,
    ).read()
    auth = request_json(
        opener,
        f"{BASE_URL}/procurementui/authenticate",
        method="POST",
        data={"rpid": "GUEST"},
    )
    token = auth.get("jwttoken") or auth.get("jwtToken")
    if not token:
        raise RuntimeError(f"Guest authentication did not return a token: {auth}")
    return token


def fetch_tenders(
    opener: urllib.request.OpenerDirector,
    token: str,
    *,
    page: int,
    page_size: int,
    keyword: str,
) -> dict[str, Any]:
    params = {
        "page": page,
        "numberOfRecords": page_size,
        "sortType": "POSTED_DATE_DESC",
        "keyword": keyword,
    }
    url = f"{BASE_URL}/procurementui/tenders?{urllib.parse.urlencode(params)}"
    return request_json(opener, url, method="POST", data="null", token=token)


def fetch_tender_detail(opener: urllib.request.OpenerDirector, token: str, tender_id: str) -> dict[str, Any]:
    params = {"tenderId": tender_id}
    url = f"{BASE_URL}/procurementui/tenders?{urllib.parse.urlencode(params)}"
    data = request_json(opener, url, method="POST", data="null", token=token)
    rows = data.get("tenderDataList") or []
    return rows[0] if rows else {}


def parse_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def text_blob(tender: dict[str, Any]) -> str:
    fields = [
        "tenderId",
        "title",
        "solicitationType",
        "procurementEntity",
        "endUserEntity",
        "description",
        "memo",
        "contactDetails",
    ]
    return " ".join(str(tender.get(field) or "") for field in fields).lower()


def match_tender(tender: dict[str, Any], criteria: dict[str, Any], now: dt.datetime) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    blob = text_blob(tender)

    statuses = [s.lower() for s in criteria.get("statuses", ["OPEN"])]
    status = str(tender.get("tenderStatus") or "").lower()
    if statuses and status not in statuses:
        return False, [f"status {status or 'blank'} not in criteria"]

    solicitation_types = [s.lower() for s in criteria.get("solicitation_types", [])]
    solicitation = str(tender.get("solicitationType") or "").lower()
    if solicitation_types and not any(s in solicitation for s in solicitation_types):
        return False, ["solicitation type not in criteria"]

    min_days = criteria.get("min_days_until_close")
    closing = parse_date(tender.get("closingDate"))
    if min_days is not None and closing:
        days = (closing - now).total_seconds() / 86400
        if days < float(min_days):
            return False, [f"closing window {days:.1f} days is below minimum"]

    for keyword in criteria.get("exclude_keywords", []):
        if keyword.lower() in blob:
            return False, [f"excluded keyword: {keyword}"]

    include_keywords = criteria.get("include_keywords", [])
    hits = [keyword for keyword in include_keywords if keyword.lower() in blob]
    if include_keywords and not hits:
        return False, ["no include keyword matched"]

    if hits:
        reasons.append("matched keywords: " + ", ".join(hits))
    return True, reasons


def is_actionable_consulting_tender(tender: dict[str, Any]) -> bool:
    blob = text_blob(tender)
    consulting_signals = [
        "feasibility",
        "study",
        "assessment",
        "capacity study",
        "assimilative capacity",
        "design",
        "design study",
        "design services",
        "engineering services",
        "consulting",
        "consultant",
        "report",
        "master plan",
        "planning",
        "model",
        "modelling",
        "stormwater management project",
        "condition assessment",
        "hydraulic",
    ]
    construction_signals = [
        "asphalt repaving",
        "paving",
        "gravelling",
        "bridge rehabilitation",
        "bridge replacement",
        "window replacement",
        "recladding",
        "culvert",
        "sprinkler work",
        "utility extensions",
        "supply & installation",
        "supply and installation",
        "materials, labour and equipment",
    ]
    supply_signals = [
        "supply of",
        "supply & programming",
        "radios",
        "rescue tools",
        "vehicle",
        "tractor",
        "electrical supplies",
        "lamps and ballasts",
        "media destruction",
        "vendor",
    ]
    return (
        any(signal in blob for signal in consulting_signals)
        and not any(signal in blob for signal in construction_signals)
        and not any(signal in blob for signal in supply_signals)
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "tender"


def yaml_scalar(value: Any) -> str:
    if value is None or value == "":
        return '""'
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def write_brief(tender: dict[str, Any], proposal_repo: Path, reasons: list[str]) -> Path:
    active_dir = proposal_repo / "proposals" / "active" / "ns-tenders"
    active_dir.mkdir(parents=True, exist_ok=True)
    tender_id = str(tender.get("tenderId") or tender.get("id") or "unknown")
    path = active_dir / f"{slugify(tender_id + '-' + str(tender.get('title') or ''))}.yaml"
    expected_tender_id = f'tender_id: "{tender_id}"'
    for existing_path in active_dir.glob("*.yaml"):
        if existing_path == path:
            continue
        if expected_tender_id in existing_path.read_text(encoding="utf-8", errors="ignore"):
            existing_path.unlink()
    closing = parse_date(tender.get("closingDate"))
    due_date = closing.date().isoformat() if closing else ""
    portal_url = f"{BASE_URL}/tenders/{urllib.parse.quote(tender_id)}"
    body = [
        f"client: {yaml_scalar(tender.get('procurementEntity') or tender.get('endUserEntity') or 'Nova Scotia public sector')}",
        f"opportunity: {yaml_scalar(tender.get('title') or tender_id)}",
        f"due_date: {yaml_scalar(due_date)}",
        'industry: "Civil engineering"',
        'service_line: "infrastructure"',
        'project_region: "atlantic"',
        "rfp_text: >",
        f"  Tender {tender_id}: {tender.get('title') or ''}.",
        f"  Solicitation type: {tender.get('solicitationType') or ''}.",
        f"  Procurement entity: {tender.get('procurementEntity') or ''}.",
        f"  End-user entity: {tender.get('endUserEntity') or ''}.",
        f"  Status: {tender.get('tenderStatus') or ''}.",
        f"  Posted: {tender.get('postDate') or ''}.",
        f"  Closing: {tender.get('closingDate') or ''}.",
        f"  Portal URL: {portal_url}.",
        f"  Description: {tender.get('description') or ''}.",
        "goals:",
        "  - Review tender notice and documents for fit.",
        "  - Confirm eligibility, submission method, schedule, and compliance requirements.",
        "scope:",
        "  - Capture tender requirements.",
        "  - Prepare pursue/no-pursue recommendation.",
        "  - Draft proposal response outline if qualified.",
        "constraints:",
        "  - Verify all tender documents directly in the Nova Scotia Procurement Portal before bidding.",
        "decision_criteria:",
        "  - Strategic fit.",
        "  - Technical capability.",
        "  - Available response time.",
        "  - Compliance requirements.",
        "source:",
        f"  portal_url: {yaml_scalar(portal_url)}",
        f"  tender_id: {yaml_scalar(tender_id)}",
        "match_reasons:",
    ]
    body.extend(f"  - {yaml_scalar(reason)}" for reason in reasons)
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor Nova Scotia public tenders and create Tender Agent briefs.")
    parser.add_argument("--criteria", type=Path, default=DEFAULT_CRITERIA)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--proposal-repo", type=Path, default=DEFAULT_PROPOSAL_REPO)
    parser.add_argument("--keyword", default="")
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--include-seen", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    criteria = load_json(args.criteria, {})
    state = load_json(args.state, {"seen_tender_ids": []})
    seen = set(state.get("seen_tender_ids", []))

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    token = authenticate(opener)
    now = dt.datetime.now()
    matches: list[dict[str, Any]] = []

    for page in range(1, args.max_pages + 1):
        data = fetch_tenders(opener, token, page=page, page_size=args.page_size, keyword=args.keyword)
        rows = data.get("tenderDataList") or []
        if not rows:
            break
        for row in rows:
            tender_id = str(row.get("tenderId") or row.get("id") or "")
            if not tender_id:
                continue
            if tender_id in seen and not args.include_seen:
                continue
            ok, reasons = match_tender(row, criteria, now)
            if not ok:
                continue
            detail = fetch_tender_detail(opener, token, tender_id)
            tender = {**row, **detail}
            ok, reasons = match_tender(tender, criteria, now)
            if ok and is_actionable_consulting_tender(tender):
                matches.append({"tender": tender, "reasons": reasons})

    summary_dir = args.proposal_repo / "proposals" / "outputs" / "ns-tenders"
    summary_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    for item in matches:
        tender = item["tender"]
        reasons = item["reasons"]
        if not args.dry_run:
            brief = write_brief(tender, args.proposal_repo, reasons)
            generated.append(str(brief))
            seen.add(str(tender.get("tenderId")))

    run_summary = {
        "ran_at": now.isoformat(timespec="seconds"),
        "dry_run": args.dry_run,
        "matches": matches,
        "generated_briefs": generated,
        "generated_analyses": [],
    }
    summary_path = summary_dir / f"ns-tender-monitor-{now.strftime('%Y%m%d-%H%M%S')}.json"
    save_json(summary_path, run_summary)

    if not args.dry_run:
        state["seen_tender_ids"] = sorted(seen)
        state["last_run_at"] = now.isoformat(timespec="seconds")
        save_json(args.state, state)

    print(json.dumps({
        "matches": len(matches),
        "generated_briefs": generated,
        "generated_analyses": [],
        "summary_path": str(summary_path),
        "dry_run": args.dry_run,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
