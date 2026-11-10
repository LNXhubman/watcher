-- Watcher schema. SQLite is the system of record; raw documents live on disk and are referenced here.
-- Applied by watcher.db.init_db; the version is tracked in PRAGMA user_version.

CREATE TABLE jurisdictions (
    id         INTEGER PRIMARY KEY,
    level      TEXT NOT NULL CHECK (level IN ('city', 'county', 'state', 'federal', 'district')),
    name       TEXT NOT NULL,
    code       TEXT NOT NULL DEFAULT '',            -- e.g. FIPS or district id
    parent_id  INTEGER REFERENCES jurisdictions(id),
    UNIQUE (level, name, code)
);

-- A zipcode can touch several jurisdictions; confirmed = the user chose to watch it.
CREATE TABLE zipcode_jurisdictions (
    zipcode          TEXT NOT NULL,
    jurisdiction_id  INTEGER NOT NULL REFERENCES jurisdictions(id),
    confirmed        INTEGER NOT NULL DEFAULT 0 CHECK (confirmed IN (0, 1)),
    share            REAL,                           -- share of the zipcode's land area, when known
    PRIMARY KEY (zipcode, jurisdiction_id)
);

CREATE TABLE sources (
    id               INTEGER PRIMARY KEY,
    jurisdiction_id  INTEGER NOT NULL REFERENCES jurisdictions(id),
    name             TEXT NOT NULL,
    kind             TEXT NOT NULL,                  -- agenda, legislation, permits, notices, ...
    url              TEXT NOT NULL,
    method           TEXT NOT NULL CHECK (method IN ('api', 'feed', 'scrape', 'llm')),
    enabled          INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    last_success_at  TEXT,
    last_error       TEXT,
    UNIQUE (jurisdiction_id, name)
);

CREATE TABLE items (
    id               INTEGER PRIMARY KEY,
    source_id        INTEGER NOT NULL REFERENCES sources(id),
    jurisdiction_id  INTEGER NOT NULL REFERENCES jurisdictions(id),
    external_id      TEXT NOT NULL,                  -- stable id from the source, or a hash of its URL
    item_type        TEXT NOT NULL CHECK (item_type IN (
                         'meeting', 'agenda_item', 'vote', 'legislation', 'budget',
                         'permit', 'election', 'comment_deadline', 'notice', 'other')),
    title            TEXT NOT NULL,
    summary          TEXT NOT NULL DEFAULT '',
    url              TEXT NOT NULL DEFAULT '',
    occurs_at        TEXT,                           -- when the event happens or happened (ISO 8601)
    content_hash     TEXT NOT NULL,
    first_seen_at    TEXT NOT NULL,
    last_seen_at     TEXT NOT NULL,
    last_changed_at  TEXT NOT NULL,
    UNIQUE (source_id, external_id)
);
CREATE INDEX items_jurisdiction_occurs ON items (jurisdiction_id, occurs_at);
CREATE INDEX items_first_seen ON items (first_seen_at);

-- One row per observed version of an item, so edits (amended agendas, reschedules) are visible.
CREATE TABLE item_versions (
    id            INTEGER PRIMARY KEY,
    item_id       INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    content_hash  TEXT NOT NULL,
    title         TEXT NOT NULL,
    summary       TEXT NOT NULL,
    seen_at       TEXT NOT NULL
);

-- Raw documents archived on disk so items can be re-parsed later.
CREATE TABLE documents (
    id          INTEGER PRIMARY KEY,
    item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    path        TEXT NOT NULL,                       -- relative to the data directory
    sha256      TEXT NOT NULL,
    mime_type   TEXT NOT NULL DEFAULT '',
    fetched_at  TEXT NOT NULL,
    UNIQUE (item_id, sha256)
);

CREATE TABLE interests (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,
    keywords  TEXT NOT NULL DEFAULT '[]',            -- JSON array
    levels    TEXT NOT NULL DEFAULT '[]',            -- JSON array; empty means all levels
    priority  INTEGER NOT NULL DEFAULT 0,
    active    INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE matches (
    id           INTEGER PRIMARY KEY,
    item_id      INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    interest_id  INTEGER NOT NULL REFERENCES interests(id) ON DELETE CASCADE,
    score        REAL NOT NULL,
    reason       TEXT NOT NULL DEFAULT '',
    matched_at   TEXT NOT NULL,
    UNIQUE (item_id, interest_id)
);

CREATE TABLE runs (
    id             INTEGER PRIMARY KEY,
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    status         TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'ok', 'partial', 'failed', 'capped')),
    items_new      INTEGER NOT NULL DEFAULT 0,
    items_changed  INTEGER NOT NULL DEFAULT 0,
    tokens_in      INTEGER NOT NULL DEFAULT 0,
    tokens_out     INTEGER NOT NULL DEFAULT 0,
    cost_usd       REAL NOT NULL DEFAULT 0,
    error          TEXT
);

CREATE TABLE source_runs (
    id           INTEGER PRIMARY KEY,
    run_id       INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    source_id    INTEGER NOT NULL REFERENCES sources(id),
    status       TEXT NOT NULL CHECK (status IN ('ok', 'failed', 'skipped')),
    items_found  INTEGER NOT NULL DEFAULT 0,
    error        TEXT
);

CREATE TABLE reports (
    id            INTEGER PRIMARY KEY,
    iso_week      TEXT NOT NULL UNIQUE,              -- e.g. 2026-W46
    generated_at  TEXT NOT NULL,
    html_path     TEXT NOT NULL,
    md_path       TEXT NOT NULL,
    summary       TEXT NOT NULL DEFAULT ''
);
