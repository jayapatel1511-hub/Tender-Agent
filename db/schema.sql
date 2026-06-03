PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO schema_meta (key, value, updated_at)
VALUES ('schema_version', '2026-06-02.1', datetime('now'))
ON CONFLICT(key) DO UPDATE SET
    value = excluded.value,
    updated_at = excluded.updated_at;

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    source TEXT,
    command TEXT,
    snapshot_path TEXT,
    triage_path TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tenders (
    tender_id TEXT PRIMARY KEY,
    title TEXT,
    status TEXT,
    solicitation_type TEXT,
    procurement_entity TEXT,
    end_user_entity TEXT,
    post_date TEXT,
    closing_date TEXT,
    description TEXT,
    portal_url TEXT,
    source TEXT NOT NULL DEFAULT 'nova-scotia-procurement-portal',
    first_seen_at TEXT,
    last_seen_at TEXT,
    raw_json TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS open_tender_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tender_id TEXT NOT NULL,
    snapshot_path TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    raw_json TEXT,
    UNIQUE(run_id, tender_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_open_tender_snapshots_tender_id
    ON open_tender_snapshots(tender_id);

CREATE INDEX IF NOT EXISTS idx_open_tender_snapshots_seen_at
    ON open_tender_snapshots(seen_at);

CREATE TABLE IF NOT EXISTS triage_results (
    triage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tender_id TEXT NOT NULL,
    criteria_version TEXT,
    bucket TEXT NOT NULL,
    pursuit_type TEXT,
    bid_fit TEXT,
    confidence TEXT,
    reason TEXT,
    next_action TEXT,
    urgent INTEGER NOT NULL DEFAULT 0,
    triaged_at TEXT NOT NULL,
    raw_json TEXT,
    UNIQUE(run_id, tender_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_triage_results_tender_id
    ON triage_results(tender_id);

CREATE INDEX IF NOT EXISTS idx_triage_results_bucket
    ON triage_results(bucket);

CREATE TABLE IF NOT EXISTS notion_sync_log (
    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tender_id TEXT,
    notion_page_id TEXT,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    synced_at TEXT NOT NULL,
    error TEXT,
    raw_json TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS email_log (
    email_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tender_id TEXT,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL,
    sent_at TEXT,
    payload_path TEXT,
    error TEXT,
    raw_json TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE SET NULL
);
