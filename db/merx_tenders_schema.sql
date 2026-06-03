PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO schema_meta (key, value, updated_at)
VALUES ('merx_tenders_schema_version', '2026-06-03.1', datetime('now'))
ON CONFLICT(key) DO UPDATE SET
    value = excluded.value,
    updated_at = excluded.updated_at;

CREATE TABLE IF NOT EXISTS scrape_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    command TEXT,
    since_date TEXT,
    until_date TEXT,
    province TEXT,
    category TEXT,
    pages_seen INTEGER NOT NULL DEFAULT 0,
    tenders_seen INTEGER NOT NULL DEFAULT 0,
    inserted INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scrape_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    url TEXT,
    error_type TEXT,
    message TEXT,
    seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    raw_json TEXT,
    FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS organizations (
    organization_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    source_url TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS companies (
    company_id INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    province TEXT,
    country TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tenders (
    tender_id TEXT PRIMARY KEY,
    merx_reference TEXT UNIQUE,
    solicitation_number TEXT,
    source_id TEXT,
    source_url TEXT NOT NULL UNIQUE,
    title TEXT,
    status TEXT,
    project_type TEXT,
    issuing_organization_id INTEGER,
    owner_organization_id INTEGER,
    issuing_organization TEXT,
    owner_organization TEXT,
    location_text TEXT,
    province TEXT,
    country TEXT,
    description TEXT,
    publication_datetime TEXT,
    publication_date_raw TEXT,
    closing_datetime TEXT,
    closing_date_raw TEXT,
    bid_intent TEXT,
    bid_intent_deadline TEXT,
    bid_intent_deadline_raw TEXT,
    question_acceptance_deadline TEXT,
    question_acceptance_deadline_raw TEXT,
    questions_submitted_online TEXT,
    bid_submission_type TEXT,
    pricing_type TEXT,
    raw_text TEXT,
    raw_html_hash TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    raw_json TEXT,
    FOREIGN KEY (issuing_organization_id) REFERENCES organizations(organization_id) ON DELETE SET NULL,
    FOREIGN KEY (owner_organization_id) REFERENCES organizations(organization_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_merx_tenders_publication
    ON tenders(publication_datetime);

CREATE INDEX IF NOT EXISTS idx_merx_tenders_closing
    ON tenders(closing_datetime);

CREATE INDEX IF NOT EXISTS idx_merx_tenders_status
    ON tenders(status);

CREATE INDEX IF NOT EXISTS idx_merx_tenders_province
    ON tenders(province);

CREATE INDEX IF NOT EXISTS idx_merx_tenders_issuing_org
    ON tenders(issuing_organization_id);

CREATE TABLE IF NOT EXISTS tender_categories (
    tender_id TEXT NOT NULL,
    category_code TEXT,
    category_name TEXT NOT NULL,
    category_path TEXT,
    PRIMARY KEY (tender_id, category_name),
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tender_categories_name
    ON tender_categories(category_name);

CREATE TABLE IF NOT EXISTS contacts (
    contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id TEXT NOT NULL,
    name TEXT,
    role TEXT,
    phone TEXT,
    email TEXT,
    raw_text TEXT,
    UNIQUE(tender_id, name, role, phone, email),
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_contacts_tender
    ON contacts(tender_id);

CREATE TABLE IF NOT EXISTS documents (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id TEXT NOT NULL,
    title TEXT,
    document_type TEXT,
    source_url TEXT,
    filename TEXT,
    size_text TEXT,
    publication_date TEXT,
    publication_date_raw TEXT,
    access_level TEXT NOT NULL DEFAULT 'public',
    raw_text TEXT,
    raw_html_hash TEXT,
    UNIQUE(tender_id, title, source_url, filename),
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_tender
    ON documents(tender_id);

CREATE TABLE IF NOT EXISTS amendments (
    amendment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id TEXT NOT NULL,
    amendment_number TEXT,
    title TEXT,
    publication_date TEXT,
    publication_date_raw TEXT,
    description TEXT,
    raw_text TEXT,
    UNIQUE(tender_id, amendment_number, title, publication_date),
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_amendments_tender
    ON amendments(tender_id);

CREATE TABLE IF NOT EXISTS plan_holders (
    plan_holder_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id TEXT NOT NULL,
    company_id INTEGER,
    company_name TEXT,
    address TEXT,
    city TEXT,
    province TEXT,
    country TEXT,
    list_type TEXT,
    raw_text TEXT,
    UNIQUE(tender_id, company_name, list_type),
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_plan_holders_company
    ON plan_holders(company_id);

CREATE TABLE IF NOT EXISTS bids (
    bid_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id TEXT NOT NULL,
    bidder_company_id INTEGER,
    bidder_name TEXT,
    address TEXT,
    bid_amount REAL,
    bid_amount_text TEXT,
    currency TEXT,
    bid_rank INTEGER,
    bid_status TEXT,
    raw_text TEXT,
    UNIQUE(tender_id, bidder_name, bid_amount_text, bid_rank),
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE,
    FOREIGN KEY (bidder_company_id) REFERENCES companies(company_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_bids_tender
    ON bids(tender_id);

CREATE INDEX IF NOT EXISTS idx_bids_bidder
    ON bids(bidder_company_id);

CREATE TABLE IF NOT EXISTS awards (
    award_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id TEXT NOT NULL,
    supplier_company_id INTEGER,
    awarded_supplier TEXT,
    awarded_value REAL,
    awarded_value_text TEXT,
    currency TEXT,
    award_date TEXT,
    award_date_raw TEXT,
    contract_number TEXT,
    contract_dates TEXT,
    description TEXT,
    raw_text TEXT,
    UNIQUE(tender_id, awarded_supplier, awarded_value_text, award_date),
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_company_id) REFERENCES companies(company_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_awards_tender
    ON awards(tender_id);

CREATE INDEX IF NOT EXISTS idx_awards_supplier
    ON awards(supplier_company_id);

CREATE INDEX IF NOT EXISTS idx_awards_date
    ON awards(award_date);

CREATE TABLE IF NOT EXISTS raw_pages (
    raw_page_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id TEXT,
    run_id TEXT,
    url TEXT NOT NULL,
    section TEXT,
    access_level TEXT NOT NULL DEFAULT 'public',
    fetched_at TEXT NOT NULL,
    http_status INTEGER,
    raw_html_hash TEXT,
    raw_text TEXT,
    raw_json TEXT,
    UNIQUE(tender_id, url, section, raw_html_hash),
    FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_pages_tender
    ON raw_pages(tender_id);
