#!/usr/bin/env python3
"""Generate Tier 2 downstream artifacts from triage results."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database_store import connect, import_triage


DEFAULT_TRIAGE = Path("data/triage/triage-latest.json")
DEFAULT_SNAPSHOT = Path("data/open-tenders/open-tenders-latest.json")
DEFAULT_STATE = Path("data/seen_tenders_state.json")
DEFAULT_DATABASE = Path("data/tender-agent.sqlite")
DEFAULT_OUTPUT_DIR = Path("proposals/outputs/ns-tenders")
DEFAULT_ACTIVE_DIR = Path("proposals/active/ns-tenders")
DEFAULT_RECIPIENT = "jpatel1511@outlook.com"
EMAIL_BUCKETS = {"prime-consultant-fit", "partner-or-subconsultant-fit"}


def main() -> int:
    args = parse_args()
    triage = read_json(args.triage)
    snapshot = read_json(args.snapshot) if args.snapshot.exists() else {"tenders": []}
    state = read_json(args.state) if args.state.exists() else {"seen_tender_ids": []}
    tender_index = build_tender_index(snapshot)
    seen = {str(item) for item in state.get("seen_tender_ids", [])}

    results = [item for item in triage.get("results", []) if isinstance(item, dict)]
    relevant = [item for item in results if item.get("bucket") in EMAIL_BUCKETS]
    prime = [item for item in results if item.get("bucket") == "prime-consultant-fit"]
    new_relevant = [item for item in relevant if str(item.get("tender_id")) not in seen]

    cleanup_stale_prime_briefs(results, args.active_dir)
    generated_briefs = [
        write_brief(item, tender_index.get(str(item.get("tender_id")), {}), args.active_dir)
        for item in prime
    ]

    email_brief_path = None
    email_payload_path = None
    if new_relevant:
        email_brief_path, email_payload_path = write_email_artifacts(
            new_relevant,
            tender_index,
            args.output_dir,
            args.recipient,
        )
        for item in new_relevant:
            seen.add(str(item.get("tender_id")))

    now = utc_now()
    write_json(
        args.state,
        {
            "seen_tender_ids": sorted(seen),
            "last_run_at": now,
        },
    )

    notion_export_path = write_notion_export(results, tender_index, args.output_dir, now)
    database_import = None
    if args.database:
        with connect(args.database, Path("db/schema.sql")) as connection:
            run_id, count = import_triage(connection, args.triage)
            record_external_logs(
                connection,
                run_id=run_id,
                notion_export_path=notion_export_path,
                email_payload_path=email_payload_path,
                email_results=new_relevant,
                recipient=args.recipient,
            )
            connection.commit()
        database_import = {
            "run_id": run_id,
            "triage_results": count,
            "database": str(args.database),
            "notion_log_rows": 1,
            "email_log_rows": len(new_relevant) if email_payload_path else 0,
        }

    log_path = write_run_log(
        args.output_dir,
        now,
        {
            "triage_path": str(args.triage),
            "snapshot_path": str(args.snapshot),
            "state_path": str(args.state),
            "result_count": len(results),
            "relevant_count": len(relevant),
            "new_relevant_count": len(new_relevant),
            "generated_briefs": [str(path) for path in generated_briefs],
            "email_brief_path": str(email_brief_path) if email_brief_path else None,
            "email_payload_path": str(email_payload_path) if email_payload_path else None,
            "email_sent": False,
            "email_decision": "payload-created" if new_relevant else "no-new-relevant-tenders",
            "notion_export_path": str(notion_export_path),
            "notion_sync_status": "exported-public-safe-upsert-payload",
            "database_import": database_import,
        },
    )

    print(f"Downstream triage results: {len(results)}")
    print(f"Relevant leads: {len(relevant)}; new relevant leads: {len(new_relevant)}")
    print(f"Generated prime-fit briefs: {len(generated_briefs)}")
    print(f"Notion export: {notion_export_path}")
    if email_payload_path:
        print(f"Email payload: {email_payload_path}")
    print(f"Run log: {log_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Tender Agent Tier 2 downstream outputs.")
    parser.add_argument("--triage", type=Path, default=DEFAULT_TRIAGE)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--no-database", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--active-dir", type=Path, default=DEFAULT_ACTIVE_DIR)
    parser.add_argument("--recipient", default=DEFAULT_RECIPIENT)
    args = parser.parse_args()
    if args.no_database:
        args.database = None
    return args


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_tender_index(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in snapshot.get("tenders", []):
        if not isinstance(item, dict):
            continue
        tender_id = text_value(item, "tender_id", "tenderId", "id")
        if tender_id:
            index[tender_id] = item
    return index


def text_value(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is None and isinstance(mapping.get("raw"), dict):
            value = mapping["raw"].get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug[:90] or "tender").strip("-")


def yaml_scalar(value: Any) -> str:
    text = "" if value is None else str(value)
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def block_text(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def portal_url(tender_id: str, tender: dict[str, Any]) -> str:
    return text_value(tender, "portal_url", "portalUrl", "tenderUrl") or (
        f"https://procurement-portal.novascotia.ca/tenders/{tender_id}"
    )


def write_brief(result: dict[str, Any], tender: dict[str, Any], active_dir: Path) -> Path:
    active_dir.mkdir(parents=True, exist_ok=True)
    tender_id = str(result.get("tender_id"))
    title = text_value(tender, "title") or tender_id
    path = active_dir / f"{slugify(tender_id + '-' + title)}.yaml"
    expected_id_line = f"tender_id: \"{tender_id}\""
    for existing in active_dir.glob("*.yaml"):
        if existing == path:
            continue
        text = existing.read_text(encoding="utf-8", errors="ignore")
        if expected_id_line in text or f"tender_id: {tender_id}" in text:
            existing.unlink()
    lines = [
        f"client: {yaml_scalar(text_value(tender, 'procurement_entity', 'procurementEntity') or text_value(tender, 'end_user_entity', 'endUserEntity') or 'Nova Scotia public sector')}",
        f"opportunity: {yaml_scalar(title)}",
        f"due_date: {yaml_scalar(text_value(tender, 'closing_date', 'closingDate'))}",
        'industry: "Civil engineering"',
        'service_line: "infrastructure"',
        'project_region: "atlantic"',
        "rfp_text: >",
        f"  Tender {tender_id}: {block_text(title)}.",
        f"  Procurement entity: {block_text(text_value(tender, 'procurement_entity', 'procurementEntity'))}.",
        f"  Closing: {block_text(text_value(tender, 'closing_date', 'closingDate'))}.",
        f"  Portal URL: {portal_url(tender_id, tender)}.",
        f"  Description: {block_text(text_value(tender, 'description'))}.",
        f"pursuit_type: {yaml_scalar(result.get('pursuit_type'))}",
        f"bid_fit: {yaml_scalar(result.get('bid_fit') or result.get('bucket'))}",
        f"classification_confidence: {yaml_scalar(result.get('confidence'))}",
        f"classification_note: {yaml_scalar(result.get('reason'))}",
        "goals:",
        "  - Review tender notice and documents for fit.",
        "  - Confirm eligibility, submission method, schedule, and compliance requirements.",
        "scope:",
        "  - Capture tender requirements.",
        "  - Prepare pursue/no-pursue recommendation.",
        "  - Draft proposal response outline if qualified.",
        "constraints:",
        "  - Verify all tender documents directly in the Nova Scotia Procurement Portal before bidding.",
        "source:",
        f"  portal_url: {yaml_scalar(portal_url(tender_id, tender))}",
        f"  tender_id: {yaml_scalar(tender_id)}",
        "triage:",
        f"  bucket: {yaml_scalar(result.get('bucket'))}",
        f"  urgent: {str(bool(result.get('urgent'))).lower()}",
        f"  next_action: {yaml_scalar(result.get('next_action'))}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def cleanup_stale_prime_briefs(results: list[dict[str, Any]], active_dir: Path) -> None:
    if not active_dir.exists():
        return
    non_prime_ids = {
        str(item.get("tender_id"))
        for item in results
        if item.get("tender_id") and item.get("bucket") != "prime-consultant-fit"
    }
    if not non_prime_ids:
        return
    for path in active_dir.glob("*.yaml"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for tender_id in non_prime_ids:
            pattern = r"(?m)^\s*tender_id:\s*\"?" + re.escape(tender_id) + r"\"?\s*$"
            if re.search(pattern, text):
                path.unlink()
                break


def write_email_artifacts(
    results: list[dict[str, Any]],
    tender_index: dict[str, dict[str, Any]],
    output_dir: Path,
    recipient: str,
) -> tuple[Path, Path]:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    brief_dir = output_dir / "email-briefs"
    payload_dir = output_dir / "email-payloads"
    brief_dir.mkdir(parents=True, exist_ok=True)
    payload_dir.mkdir(parents=True, exist_ok=True)
    strong = [item for item in results if item.get("bucket") == "prime-consultant-fit"]
    partner = [item for item in results if item.get("bucket") == "partner-or-subconsultant-fit"]
    subject = f"Tender Leads - {now.strftime('%Y-%m-%d')} - {len(strong)} Strong / {len(partner)} Review"
    body = build_email_body(results, tender_index, subject)
    brief_path = brief_dir / f"tender-leads-{stamp}.txt"
    payload_path = payload_dir / f"tender-leads-{stamp}.json"
    brief_path.write_text(body, encoding="utf-8")
    write_json(
        payload_path,
        {
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "tender_ids": [str(item.get("tender_id")) for item in results],
            "created_at": utc_now(),
            "public_safe": True,
            "sent": False,
        },
    )
    return brief_path, payload_path


def build_email_body(results: list[dict[str, Any]], tender_index: dict[str, dict[str, Any]], subject: str) -> str:
    strong = [item for item in results if item.get("bucket") == "prime-consultant-fit"]
    partner = [item for item in results if item.get("bucket") == "partner-or-subconsultant-fit"]
    lines = [
        f"Subject: {subject}",
        "",
        "Summary",
        f"{len(results)} new relevant tender leads found.",
        f"{len(strong)} strong-fit engineering pursuits.",
        f"{len(partner)} partner/subconsultant leads.",
        "",
    ]
    if strong:
        lines.extend(["Priority Leads", ""])
        append_email_section(lines, strong, tender_index, "Strong Fit")
    if partner:
        lines.extend(["Partner / Subconsultant Leads", ""])
        append_email_section(lines, partner, tender_index, "Partner Lead")
    lines.extend(
        [
            "Notes",
            "Only public tender information is included.",
            "Verify scope, addenda, closing date, mandatory meetings, submission rules, and eligibility directly in the Nova Scotia Procurement Portal before acting.",
            "",
        ]
    )
    return "\n".join(lines)


def append_email_section(
    lines: list[str],
    results: list[dict[str, Any]],
    tender_index: dict[str, dict[str, Any]],
    label: str,
) -> None:
    for item in results:
        tender_id = str(item.get("tender_id"))
        tender = tender_index.get(tender_id, {})
        lines.extend(
            [
                f"[{label}] {text_value(tender, 'title') or tender_id}",
                f"Buyer: {text_value(tender, 'procurement_entity', 'procurementEntity') or text_value(tender, 'end_user_entity', 'endUserEntity')}",
                f"Tender ID: {tender_id}",
                f"Closes: {text_value(tender, 'closing_date', 'closingDate')}",
                f"Link: {portal_url(tender_id, tender)}",
                f"Fit: {item.get('bucket')} confidence {item.get('confidence')}",
                f"Why it surfaced: {item.get('reason')}",
                f"Action: {item.get('next_action')}",
                "",
            ]
        )


def write_notion_export(
    results: list[dict[str, Any]],
    tender_index: dict[str, dict[str, Any]],
    output_dir: Path,
    now: str,
) -> Path:
    export_dir = output_dir / "notion-sync"
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / "notion-upsert-latest.json"
    rows = []
    for item in results:
        tender_id = str(item.get("tender_id"))
        tender = tender_index.get(tender_id, {})
        rows.append(
            {
                "Tender ID": tender_id,
                "Opportunity": text_value(tender, "title") or tender_id,
                "Procurement Entity": text_value(tender, "procurement_entity", "procurementEntity"),
                "Closing Date": text_value(tender, "closing_date", "closingDate"),
                "Portal URL": portal_url(tender_id, tender),
                "Pursuit Type": item.get("pursuit_type"),
                "Bid Fit": item.get("bid_fit") or item.get("bucket"),
                "Priority": "Urgent" if item.get("urgent") else priority_for_bucket(str(item.get("bucket"))),
                "Status": item.get("bucket"),
                "Next Action": item.get("next_action"),
                "Last Checked": now,
            }
        )
    write_json(path, {"dedupe_key": "Tender ID", "last_checked": now, "rows": rows})
    return path


def record_external_logs(
    connection: Any,
    *,
    run_id: str,
    notion_export_path: Path,
    email_payload_path: Path | None,
    email_results: list[dict[str, Any]],
    recipient: str,
) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO notion_sync_log (
            run_id, action, status, synced_at, raw_json
        )
        VALUES (?, 'export-upsert-payload', 'exported', ?, ?)
        """,
        (
            run_id,
            now,
            json.dumps({"path": str(notion_export_path), "live_connector_update": False}, sort_keys=True),
        ),
    )
    if not email_payload_path:
        return
    for item in email_results:
        connection.execute(
            """
            INSERT INTO email_log (
                run_id, tender_id, recipient, subject, status, payload_path, raw_json
            )
            VALUES (?, ?, ?, ?, 'payload-created-not-sent', ?, ?)
            """,
            (
                run_id,
                str(item.get("tender_id")),
                recipient,
                "Tender Leads",
                str(email_payload_path),
                json.dumps(item, sort_keys=True),
            ),
        )


def priority_for_bucket(bucket: str) -> str:
    if bucket == "prime-consultant-fit":
        return "High"
    if bucket == "partner-or-subconsultant-fit":
        return "Medium"
    if bucket == "needs-review":
        return "Review"
    return "Low"


def write_run_log(output_dir: Path, now: str, payload: dict[str, Any]) -> Path:
    log_dir = output_dir / "run-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = log_dir / f"tier2-downstream-{stamp}.json"
    write_json(path, {"ran_at": now, **payload})
    return path


if __name__ == "__main__":
    raise SystemExit(main())
