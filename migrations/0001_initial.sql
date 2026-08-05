CREATE TABLE IF NOT EXISTS ingestion_runs (
    id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL CHECK (length(trim(source_name)) > 0),
    source_url TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('started', 'succeeded', 'failed')),
    row_count INTEGER NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    error_message TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS fuel_prices (
    id INTEGER PRIMARY KEY,
    summary_month TEXT NOT NULL UNIQUE CHECK (
        length(summary_month) = 10
        AND summary_month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-01'
        AND date(summary_month) = summary_month
    ),
    petrol_news TEXT NOT NULL CHECK (length(trim(petrol_news)) > 0),
    diesel_news TEXT NOT NULL CHECK (length(trim(diesel_news)) > 0),
    unleaded93_inland REAL NOT NULL CHECK (unleaded93_inland >= 0.01 AND unleaded93_inland <= 100.00),
    unleaded93_coast REAL NOT NULL CHECK (unleaded93_coast >= 0.01 AND unleaded93_coast <= 100.00),
    unleaded95_inland REAL NOT NULL CHECK (unleaded95_inland >= 0.01 AND unleaded95_inland <= 100.00),
    unleaded95_coast REAL NOT NULL CHECK (unleaded95_coast >= 0.01 AND unleaded95_coast <= 100.00),
    diesel500_inland REAL NOT NULL CHECK (diesel500_inland >= 0.01 AND diesel500_inland <= 100.00),
    diesel500_coast REAL NOT NULL CHECK (diesel500_coast >= 0.01 AND diesel500_coast <= 100.00),
    diesel50_inland REAL NOT NULL CHECK (diesel50_inland >= 0.01 AND diesel50_inland <= 100.00),
    diesel50_coast REAL NOT NULL CHECK (diesel50_coast >= 0.01 AND diesel50_coast <= 100.00),
    lrp93_inland REAL NOT NULL CHECK (lrp93_inland >= 0.01 AND lrp93_inland <= 100.00),
    lrp93_coast REAL NOT NULL CHECK (lrp93_coast >= 0.01 AND lrp93_coast <= 100.00),
    source_name TEXT NOT NULL DEFAULT 'legacy-supabase-export'
        CHECK (length(trim(source_name)) > 0),
    source_url TEXT,
    source_updated_on TEXT NOT NULL DEFAULT '1970-01-01'
        CHECK (length(trim(source_updated_on)) > 0),
    source_row_id TEXT NOT NULL DEFAULT 'legacy'
        CHECK (length(trim(source_row_id)) > 0),
    source_hash TEXT NOT NULL DEFAULT 'legacy'
        CHECK (
            source_hash = 'legacy'
            OR (
                length(source_hash) = 64
                AND source_hash NOT GLOB '*[^0-9a-f]*'
            )
        ),
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        source_name = 'legacy-supabase-export'
        OR (
            source_url IS NOT NULL
            AND source_updated_on <> '1970-01-01'
            AND source_row_id <> 'legacy'
            AND source_hash <> 'legacy'
        )
    )
) STRICT;
