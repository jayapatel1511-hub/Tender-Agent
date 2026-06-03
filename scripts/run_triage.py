#!/usr/bin/env python3
"""Build a deterministic Tier 2 triage artifact from a stored tender snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SNAPSHOT = Path("data/open-tenders/open-tenders-latest.json")
DEFAULT_PROFILE = Path("config/targeted-stream-criteria.json")
DEFAULT_OUTPUT = Path("data/triage/triage-latest.json")
DEFAULT_DATABASE = Path("data/tender-agent.sqlite")

BUCKETS = (
    "prime-consultant-fit",
    "partner-or-subconsultant-fit",
    "needs-review",
    "off-profile-consulting",
    "likely-skip",
)

PROFESSIONAL_ROLE_TERMS = (
    "assessment",
    "assessments",
    "asset management",
    "capacity study",
    "condition assessment",
    "consultant",
    "consulting",
    "design",
    "design services",
    "engineering",
    "engineering services",
    "feasibility",
    "feasibility study",
    "hydraulic",
    "modelling",
    "planning",
    "professional services",
    "review",
    "study",
)

DOMAIN_TERMS = {
    "municipal civil": (
        "business park",
        "civil",
        "culvert",
        "curb",
        "drainage",
        "grading",
        "infrastructure",
        "municipal",
        "public works",
        "servicing",
        "sidewalk",
        "site servicing",
        "street",
        "streetscape",
        "subdivision",
        "utility extension",
        "utility extensions",
    ),
    "transportation": (
        "active transportation",
        "bridge",
        "corridor",
        "highway",
        "intersection",
        "multi-use path",
        "road",
        "road safety",
        "roadway",
        "sidewalk",
        "traffic",
        "traffic calming",
        "trail",
        "transit",
        "transportation",
    ),
    "water/wastewater": (
        "aeration",
        "biosolids",
        "lagoon",
        "lift station",
        "prv",
        "pump station",
        "sewer",
        "sludge",
        "sludge holding tank",
        "transmission main",
        "utility",
        "wastewater",
        "water plant",
        "water treatment",
        "water treatment plant",
        "water utility",
        "watermain",
    ),
    "stormwater": (
        "erosion",
        "flood",
        "hydrologic",
        "outfall",
        "stormwater",
        "watershed",
    ),
}

BUYER_TERMS = (
    "bridge",
    "county",
    "department of public works",
    "halifax water",
    "municipality",
    "province of nova scotia",
    "public works",
    "regional municipality",
    "town of",
    "village of",
    "water",
)

CONTRACTOR_LED_TERMS = (
    "asphalt",
    "construction",
    "construction services",
    "installation",
    "invitation to tender",
    "maintenance",
    "paving",
    "rehabilitation",
    "repaving",
    "replacement",
    "request for quotation",
    "supply",
    "upgrades",
)

GOODS_OR_OFF_PROFILE_TERMS = (
    "advertising",
    "communications",
    "corporate social responsibility",
    "equipment",
    "finance",
    "food",
    "goods",
    "human resources",
    "janitorial",
    "legal",
    "office supplies",
    "software",
    "training",
    "truck",
    "vehicle",
)

FORCE_SKIP_TERMS = (
    "notice of intent to participate",
    "this is not a rfp or tender",
    "canoe procurement",
    "cab & chassis",
    "cab and chassis",
    "dump body",
    "plow & salt/sand spreader",
    "salt/sand spreader",
    "website development",
    "website development and support",
)

CONTRACTOR_TITLE_TERMS = (
    "capital paving",
    "construction services",
    "pre-selection",
    "replacement",
    "supply",
    "upgrades",
    "vendor",
)

PRIME_TITLE_TERMS = (
    "assessment",
    "capacity study",
    "condition assessment",
    "design",
    "engineering",
    "engineering services",
    "feasibility",
    "study",
)

OFF_PROFILE_DOMAIN_COMBOS = (
    ("utility management", "building"),
    ("utility management", "buildings"),
)


def main() -> int:
    args = parse_args()
    snapshot_path = args.snapshot
    profile_path = args.profile
    output_path = args.output

    snapshot = read_json(snapshot_path)
    profile = read_json(profile_path)
    tenders = extract_tenders(snapshot)
    ran_at = now_iso()
    criteria_version = get_criteria_version(profile, profile_path)

    results = [
        triage_tender(tender, profile, ran_at)
        for tender in sorted(tenders, key=tender_sort_key)
    ]
    bucket_counts = {bucket: 0 for bucket in BUCKETS}
    for result in results:
        bucket_counts[result["bucket"]] = bucket_counts.get(result["bucket"], 0) + 1

    artifact = {
        "ran_at": ran_at,
        "snapshot_path": str(snapshot_path),
        "criteria_version": criteria_version,
        "result_count": len(results),
        "bucket_counts": bucket_counts,
        "results": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    print(f"Wrote {output_path} with {len(results)} triaged tenders.")
    print("Bucket counts: " + ", ".join(f"{k}={v}" for k, v in bucket_counts.items()))
    if args.database:
        import_into_database(args.database, output_path)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-triage a stored open tender snapshot into data/triage/triage-latest.json."
    )
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help="SQLite database to update after writing triage. Use --no-database to skip.",
    )
    parser.add_argument("--no-database", action="store_true", help="Write JSON only; do not update SQLite.")
    args = parser.parse_args()
    if args.no_database:
        args.database = None
    return args


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def extract_tenders(snapshot: Any) -> list[dict[str, Any]]:
    if isinstance(snapshot, list):
        return [item for item in snapshot if isinstance(item, dict)]
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be a JSON object or array.")
    for key in ("tenders", "results", "items", "matches"):
        value = snapshot.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    raise ValueError("Snapshot does not contain a tenders/results/items/matches array.")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_criteria_version(profile: dict[str, Any], profile_path: Path) -> str:
    explicit = profile.get("criteria_version") or profile.get("version") or profile.get("profile_version")
    if explicit:
        return str(explicit)
    digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()[:12]
    return f"unversioned-sha256-{digest}"


def tender_sort_key(tender: dict[str, Any]) -> tuple[str, str]:
    return (
        text_value(tender, "closing_date", "closingDate"),
        text_value(tender, "tender_id", "tenderId", "id"),
    )


def triage_tender(tender: dict[str, Any], profile: dict[str, Any], triaged_at: str) -> dict[str, Any]:
    tender_id = text_value(tender, "tender_id", "tenderId", "id") or "unknown"
    closing_date = text_value(tender, "closing_date", "closingDate")
    title_lower = text_value(tender, "title").lower()
    text = tender_text(tender)
    raw_lower = text.lower()

    include_hits = find_terms(profile_terms(profile, "surface_hints", "include_keywords"), raw_lower)
    exclude_hits = find_terms(profile_terms(profile, "noise_hints", "exclude_keywords"), raw_lower)
    domain_hits = find_domain_hits(raw_lower)
    role_hits = find_terms(PROFESSIONAL_ROLE_TERMS, raw_lower)
    buyer_hits = find_terms(BUYER_TERMS, raw_lower)
    contractor_hits = find_terms(CONTRACTOR_LED_TERMS, raw_lower)
    off_profile_hits = find_terms(GOODS_OR_OFF_PROFILE_TERMS, raw_lower)
    force_skip_hits = find_terms(FORCE_SKIP_TERMS, raw_lower)
    contractor_title_hits = find_terms(CONTRACTOR_TITLE_TERMS, title_lower)
    prime_title_hits = find_terms(PRIME_TITLE_TERMS, title_lower)
    off_profile_combo_hits = [
        " + ".join(combo)
        for combo in OFF_PROFILE_DOMAIN_COMBOS
        if all(term in raw_lower for term in combo)
    ]

    is_consulting = bool(role_hits) or "request for proposal" in raw_lower
    has_domain = bool(domain_hits)
    has_buyer = bool(buyer_hits)
    is_contractor_led = bool(contractor_hits)

    if force_skip_hits:
        bucket = "likely-skip"
        confidence = 0.95
        pursuit_type = "skip"
        next_action = "No action."
    elif off_profile_combo_hits:
        bucket = "off-profile-consulting"
        confidence = 0.82
        pursuit_type = "skip"
        next_action = "Skip unless a later profile adds this building operations domain."
    elif has_domain and contractor_title_hits and not prime_title_hits:
        bucket = "partner-or-subconsultant-fit"
        confidence = 0.72 if has_buyer else 0.66
        pursuit_type = "partner"
        next_action = "Check documents for engineering support, CA, inspection, or partner role."
    elif has_domain and role_hits:
        bucket = "prime-consultant-fit"
        confidence = 0.88
        pursuit_type = "prime"
        next_action = "Review scope documents and confirm lead consultant fit."
    elif has_domain and is_contractor_led:
        bucket = "partner-or-subconsultant-fit"
        confidence = 0.72 if has_buyer else 0.66
        pursuit_type = "partner"
        next_action = "Check documents for engineering support, CA, inspection, or partner role."
    elif has_domain and has_buyer:
        bucket = "needs-review"
        confidence = 0.62
        pursuit_type = "needs-review"
        next_action = "Fetch detail page or documents before deciding pursuit role."
    elif has_domain:
        bucket = "needs-review"
        confidence = 0.55
        pursuit_type = "needs-review"
        next_action = "Confirm whether the infrastructure asset has a professional-services role."
    elif is_consulting:
        bucket = "off-profile-consulting"
        confidence = 0.72
        pursuit_type = "skip"
        next_action = "Skip unless a later profile adds this consulting domain."
    elif off_profile_hits or exclude_hits:
        bucket = "likely-skip"
        confidence = 0.84
        pursuit_type = "skip"
        next_action = "No action."
    elif include_hits:
        bucket = "needs-review"
        confidence = 0.5
        pursuit_type = "needs-review"
        next_action = "Keyword matched but domain/service role needs confirmation."
    else:
        bucket = "likely-skip"
        confidence = 0.68
        pursuit_type = "skip"
        next_action = "No action."

    urgent = is_urgent(closing_date, triaged_at)
    if urgent and bucket in {"prime-consultant-fit", "partner-or-subconsultant-fit", "needs-review"}:
        next_action = "Urgent review before close. " + next_action

    reason_parts = []
    if domain_hits:
        reason_parts.append("domain: " + ", ".join(format_domain_hits(domain_hits)))
    if role_hits:
        reason_parts.append("professional role: " + ", ".join(role_hits[:4]))
    if contractor_hits and bucket == "partner-or-subconsultant-fit":
        reason_parts.append("contractor-led hints: " + ", ".join(contractor_hits[:4]))
    if contractor_title_hits:
        reason_parts.append("contractor/vendor title hints: " + ", ".join(contractor_title_hits[:4]))
    if buyer_hits:
        reason_parts.append("buyer/context: " + ", ".join(buyer_hits[:4]))
    if include_hits and not domain_hits:
        reason_parts.append("profile keyword hints: " + ", ".join(include_hits[:4]))
    if exclude_hits and domain_hits:
        reason_parts.append("overrode exclude hint because asset/domain is in scope: " + ", ".join(exclude_hits[:3]))
    elif exclude_hits and not domain_hits:
        reason_parts.append("exclude hints: " + ", ".join(exclude_hits[:3]))
    if off_profile_hits and not domain_hits:
        reason_parts.append("off-profile hints: " + ", ".join(off_profile_hits[:3]))
    if force_skip_hits:
        reason_parts.append("force-skip procurement notice hints: " + ", ".join(force_skip_hits[:3]))
    if off_profile_combo_hits:
        reason_parts.append("off-profile domain combination: " + ", ".join(off_profile_combo_hits[:3]))
    if not reason_parts:
        reason_parts.append("no target-domain asset or professional service signal found")

    return {
        "tender_id": tender_id,
        "bucket": bucket,
        "pursuit_type": pursuit_type,
        "bid_fit": bucket if bucket in {"prime-consultant-fit", "partner-or-subconsultant-fit"} else None,
        "confidence": round(confidence, 2),
        "reason": "; ".join(reason_parts),
        "next_action": next_action,
        "urgent": urgent,
        "triaged_at": triaged_at,
    }


def text_value(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is None and isinstance(mapping.get("raw"), dict):
            value = mapping["raw"].get(key)
        if value is not None:
            return str(value)
    return ""


def profile_terms(profile: dict[str, Any], primary_key: str, legacy_key: str) -> list[str]:
    values = profile.get(primary_key)
    if values is None:
        values = profile.get(legacy_key, [])
    if isinstance(values, list):
        return [str(value) for value in values]
    return []


def tender_text(tender: dict[str, Any]) -> str:
    parts: list[str] = []
    keys = (
        "tender_id",
        "tenderId",
        "title",
        "status",
        "solicitation_type",
        "solicitationType",
        "procurement_entity",
        "procurementEntity",
        "end_user_entity",
        "endUserEntity",
        "description",
        "memo",
        "source",
    )
    append_values(parts, tender, keys)
    raw = tender.get("raw")
    if isinstance(raw, dict):
        append_values(parts, raw, keys)
        attachments = raw.get("attachments")
        if isinstance(attachments, list):
            for attachment in attachments:
                if isinstance(attachment, dict):
                    append_values(parts, attachment, ("fileName", "name", "title", "description"))
                elif attachment:
                    parts.append(str(attachment))
    return " ".join(parts)


def append_values(parts: list[str], mapping: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        value = mapping.get(key)
        if value:
            parts.append(str(value))


def find_terms(terms: Any, lower_text: str) -> list[str]:
    if not isinstance(terms, (list, tuple, set)):
        return []
    hits = []
    for term in terms:
        normalized = str(term).strip().lower()
        if normalized and contains_term(lower_text, normalized):
            hits.append(str(term))
    return sorted(set(hits), key=lambda item: (item.lower(), item))


def find_domain_hits(lower_text: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for domain, terms in DOMAIN_TERMS.items():
        matched = find_terms(terms, lower_text)
        if matched:
            hits[domain] = matched
    return hits


def contains_term(lower_text: str, lower_term: str) -> bool:
    if not lower_term:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(lower_term).replace(r"\\ ", r"\\s+") + r"(?![a-z0-9])"
    return re.search(pattern, lower_text) is not None


def format_domain_hits(domain_hits: dict[str, list[str]]) -> list[str]:
    formatted = []
    for domain in sorted(domain_hits):
        formatted.append(f"{domain} ({', '.join(domain_hits[domain][:4])})")
    return formatted


def is_urgent(closing_date: str, triaged_at: str) -> bool:
    if not closing_date:
        return False
    close = parse_date(closing_date)
    run = parse_date(triaged_at)
    if close is None or run is None:
        return False
    delta = close.date() - run.date()
    return 0 <= delta.days <= 3


def parse_date(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    candidates = [
        text,
        text.replace(" ", "T"),
        text.split(" ")[0],
    ]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    return None


def import_into_database(database_path: Path, triage_path: Path) -> None:
    try:
        from database_store import connect, import_triage

        schema_path = Path("db/schema.sql")
        with connect(database_path, schema_path) as connection:
            run_id, count = import_triage(connection, triage_path)
            connection.commit()
        print(f"Imported triage into {database_path}: run_id={run_id}, results={count}")
    except Exception as exc:
        raise RuntimeError(f"Could not import triage into SQLite: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
