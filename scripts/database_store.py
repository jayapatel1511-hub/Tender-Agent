from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = REPO_ROOT / "db" / "schema.sql"
DEFAULT_DATABASE = REPO_ROOT / "data" / "tender-agent.sqlite"


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def initialize_schema(connection: sqlite3.Connection, schema_path: Path) -> None:
    schema_sql = schema_path.read_text(encoding="utf-8")
    connection.executescript(schema_sql)


def stable_run_id(prefix: str, payload: dict[str, Any], path: Path) -> str:
    for key in ("run_id", "id"):
        value = payload.get(key)
        if value:
            return f"{prefix}:{value}"

    ran_at = payload.get("ran_at") or payload.get("triaged_at") or payload.get("created_at")
    if ran_at:
        token = re.sub(r"[^0-9A-Za-z]+", "", str(ran_at))
        if token:
            return f"{prefix}:{token}"

    return f"{prefix}:{path.stem}"


def first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def tender_id_for(item: dict[str, Any]) -> str:
    value = first_present(item, ("tender_id", "tenderId", "id"))
    if not value:
        raw = item.get("raw")
        if isinstance(raw, dict):
            value = first_present(raw, ("tenderId", "tender_id", "id"))
    if not value:
        raise ValueError(f"tender record missing tender_id: {item!r}")
    return str(value)


def upsert_run(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    run_type: str,
    started_at: str,
    completed_at: str | None = None,
    source: str | None = None,
    snapshot_path: Path | None = None,
    triage_path: Path | None = None,
    notes: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO runs (
            run_id, run_type, started_at, completed_at, status, source,
            snapshot_path, triage_path, notes
        )
        VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            run_type = excluded.run_type,
            started_at = excluded.started_at,
            completed_at = excluded.completed_at,
            status = excluded.status,
            source = excluded.source,
            snapshot_path = COALESCE(excluded.snapshot_path, runs.snapshot_path),
            triage_path = COALESCE(excluded.triage_path, runs.triage_path),
            notes = excluded.notes
        """,
        (
            run_id,
            run_type,
            started_at,
            completed_at,
            source,
            str(snapshot_path) if snapshot_path else None,
            str(triage_path) if triage_path else None,
            notes,
        ),
    )


def upsert_tender(connection: sqlite3.Connection, tender: dict[str, Any], seen_at: str) -> str:
    raw = tender.get("raw") if isinstance(tender.get("raw"), dict) else {}
    tender_id = tender_id_for(tender)
    title = first_present(tender, ("title",)) or first_present(raw, ("title",))
    status = first_present(tender, ("status",)) or first_present(raw, ("tenderStatus",))
    solicitation_type = first_present(tender, ("solicitation_type", "solicitationType")) or first_present(
        raw, ("solicitationType",)
    )
    procurement_entity = first_present(tender, ("procurement_entity", "procurementEntity")) or first_present(
        raw, ("procurementEntity",)
    )
    end_user_entity = first_present(tender, ("end_user_entity", "endUserEntity")) or first_present(
        raw, ("endUserEntity",)
    )
    post_date = first_present(tender, ("post_date", "postDate")) or first_present(raw, ("postDate",))
    closing_date = first_present(tender, ("closing_date", "closingDate")) or first_present(raw, ("closingDate",))
    description = first_present(tender, ("description",)) or first_present(raw, ("description",))
    portal_url = first_present(tender, ("portal_url", "portalUrl", "tenderUrl")) or first_present(raw, ("tenderUrl",))
    source = first_present(tender, ("source",)) or "nova-scotia-procurement-portal"
    last_seen_at = str(first_present(tender, ("last_seen_at", "lastSeenAt")) or seen_at)

    connection.execute(
        """
        INSERT INTO tenders (
            tender_id, title, status, solicitation_type, procurement_entity,
            end_user_entity, post_date, closing_date, description, portal_url,
            source, first_seen_at, last_seen_at, raw_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(tender_id) DO UPDATE SET
            title = excluded.title,
            status = excluded.status,
            solicitation_type = excluded.solicitation_type,
            procurement_entity = excluded.procurement_entity,
            end_user_entity = excluded.end_user_entity,
            post_date = excluded.post_date,
            closing_date = excluded.closing_date,
            description = excluded.description,
            portal_url = excluded.portal_url,
            source = excluded.source,
            first_seen_at = COALESCE(tenders.first_seen_at, excluded.first_seen_at),
            last_seen_at = excluded.last_seen_at,
            raw_json = excluded.raw_json,
            updated_at = excluded.updated_at
        """,
        (
            tender_id,
            title,
            status,
            solicitation_type,
            procurement_entity,
            end_user_entity,
            post_date,
            closing_date,
            description,
            portal_url,
            source,
            last_seen_at,
            last_seen_at,
            json_text(tender),
        ),
    )
    return tender_id


def import_snapshot(connection: sqlite3.Connection, snapshot_path: Path) -> tuple[str, int]:
    payload = load_json(snapshot_path)
    tenders = payload.get("tenders")
    if not isinstance(tenders, list):
        raise ValueError(f"{snapshot_path} missing tenders list")

    run_id = stable_run_id("snapshot", payload, snapshot_path)
    ran_at = str(payload.get("ran_at") or utc_now())
    source = str(payload.get("source") or "nova-scotia-procurement-portal")

    upsert_run(
        connection,
        run_id=run_id,
        run_type="open_tender_snapshot",
        started_at=ran_at,
        completed_at=ran_at,
        source=source,
        snapshot_path=snapshot_path,
        notes=f"open_tender_count={payload.get('open_tender_count', len(tenders))}",
    )

    imported = 0
    for item in tenders:
        if not isinstance(item, dict):
            continue
        tender_id = upsert_tender(connection, item, ran_at)
        seen_at = str(first_present(item, ("last_seen_at", "lastSeenAt")) or ran_at)
        connection.execute(
            """
            INSERT INTO open_tender_snapshots (
                run_id, tender_id, snapshot_path, seen_at, raw_json
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id, tender_id) DO UPDATE SET
                snapshot_path = excluded.snapshot_path,
                seen_at = excluded.seen_at,
                raw_json = excluded.raw_json
            """,
            (run_id, tender_id, str(snapshot_path), seen_at, json_text(item)),
        )
        imported += 1

    return run_id, imported


def triage_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("results", "triage_results", "tenders", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if "tender_id" in payload or "tenderId" in payload:
        return [payload]
    raise ValueError("triage JSON must contain results, triage_results, tenders, items, or a single tender result")


def bool_as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        return int(value.strip().lower() in {"1", "true", "yes", "y", "urgent"})
    return int(bool(value))


def import_triage(connection: sqlite3.Connection, triage_path: Path) -> tuple[str, int]:
    payload = load_json(triage_path)
    items = triage_items(payload)
    run_id = stable_run_id("triage", payload, triage_path)
    triaged_at = str(payload.get("triaged_at") or payload.get("ran_at") or utc_now())
    source = payload.get("source")

    upsert_run(
        connection,
        run_id=run_id,
        run_type="triage",
        started_at=triaged_at,
        completed_at=triaged_at,
        source=str(source) if source else None,
        triage_path=triage_path,
        notes=f"triage_count={len(items)}",
    )

    imported = 0
    for item in items:
        tender_id = tender_id_for(item)
        connection.execute(
            """
            INSERT INTO tenders (tender_id, source, first_seen_at, last_seen_at, raw_json, updated_at)
            VALUES (?, 'nova-scotia-procurement-portal', ?, ?, ?, datetime('now'))
            ON CONFLICT(tender_id) DO UPDATE SET
                last_seen_at = COALESCE(tenders.last_seen_at, excluded.last_seen_at),
                updated_at = excluded.updated_at
            """,
            (tender_id, triaged_at, triaged_at, json_text({"tender_id": tender_id})),
        )
        connection.execute(
            """
            INSERT INTO triage_results (
                run_id, tender_id, criteria_version, bucket, pursuit_type,
                bid_fit, confidence, reason, next_action, urgent, triaged_at, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, tender_id) DO UPDATE SET
                criteria_version = excluded.criteria_version,
                bucket = excluded.bucket,
                pursuit_type = excluded.pursuit_type,
                bid_fit = excluded.bid_fit,
                confidence = excluded.confidence,
                reason = excluded.reason,
                next_action = excluded.next_action,
                urgent = excluded.urgent,
                triaged_at = excluded.triaged_at,
                raw_json = excluded.raw_json
            """,
            (
                run_id,
                tender_id,
                first_present(item, ("criteria_version", "criteriaVersion")) or payload.get("criteria_version"),
                str(first_present(item, ("bucket", "triage_bucket")) or "needs-review"),
                first_present(item, ("pursuit_type", "pursuitType")),
                first_present(item, ("bid_fit", "bidFit")),
                first_present(item, ("confidence", "classification_confidence")),
                first_present(item, ("reason", "classification_note")),
                first_present(item, ("next_action", "nextAction")),
                bool_as_int(item.get("urgent")),
                str(first_present(item, ("triaged_at", "triagedAt")) or triaged_at),
                json_text(item),
            ),
        )
        imported += 1

    return run_id, imported


def connect(database_path: Path, schema_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    initialize_schema(connection, schema_path)
    return connection


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Tender Agent JSON outputs into SQLite.")
    parser.add_argument("--snapshot", type=Path, help="Open tender snapshot JSON to import.")
    parser.add_argument("--triage", type=Path, help="Triage latest/results JSON to import.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE, help="SQLite database path.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Schema SQL path.")
    args = parser.parse_args()

    if not args.snapshot and not args.triage:
        parser.error("provide --snapshot, --triage, or both")

    with connect(args.database, args.schema) as connection:
        if args.snapshot:
            run_id, count = import_snapshot(connection, args.snapshot)
            print(f"Imported snapshot {args.snapshot}: run_id={run_id}, tenders={count}")
        if args.triage:
            if args.triage.exists():
                run_id, count = import_triage(connection, args.triage)
                print(f"Imported triage {args.triage}: run_id={run_id}, results={count}")
            else:
                print(f"Skipped missing triage file: {args.triage}")
        connection.commit()

    print(f"SQLite database: {args.database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
