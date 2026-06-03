PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS result_runs (
    run_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS result_notices (
    notice_id TEXT PRIMARY KEY,
    result_type TEXT NOT NULL,
    title TEXT,
    buyer TEXT,
    location TEXT,
    published_date TEXT,
    result_date TEXT,
    detail_url TEXT,
    solicitation_id TEXT,
    summary_text TEXT,
    source TEXT NOT NULL DEFAULT 'merx-public-results',
    first_seen_at TEXT,
    last_seen_at TEXT,
    raw_json TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_result_notices_type
    ON result_notices(result_type);

CREATE INDEX IF NOT EXISTS idx_result_notices_result_date
    ON result_notices(result_date);

CREATE INDEX IF NOT EXISTS idx_result_notices_buyer
    ON result_notices(buyer);

CREATE TABLE IF NOT EXISTS award_details (
    award_id INTEGER PRIMARY KEY AUTOINCREMENT,
    notice_id TEXT NOT NULL,
    supplier_name TEXT,
    awarded_value TEXT,
    award_date TEXT,
    contract_dates TEXT,
    confidence TEXT NOT NULL DEFAULT 'summary-only',
    raw_text TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(notice_id, supplier_name, awarded_value, award_date),
    FOREIGN KEY (notice_id) REFERENCES result_notices(notice_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_award_details_notice_id
    ON award_details(notice_id);

CREATE INDEX IF NOT EXISTS idx_award_details_supplier
    ON award_details(supplier_name);

CREATE TABLE IF NOT EXISTS bidder_results (
    bid_id INTEGER PRIMARY KEY AUTOINCREMENT,
    notice_id TEXT NOT NULL,
    bidder_name TEXT,
    bid_amount TEXT,
    is_awarded INTEGER NOT NULL DEFAULT 0,
    rank INTEGER,
    confidence TEXT NOT NULL DEFAULT 'parsed',
    raw_text TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(notice_id, bidder_name, bid_amount, rank),
    FOREIGN KEY (notice_id) REFERENCES result_notices(notice_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bidder_results_notice_id
    ON bidder_results(notice_id);

CREATE INDEX IF NOT EXISTS idx_bidder_results_bidder
    ON bidder_results(bidder_name);
