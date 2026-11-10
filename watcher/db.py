"""SQLite access: connection, schema setup and the item upsert used by every collector."""
import hashlib
import sqlite3
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

SCHEMA_VERSION = 2
# Upgrades for existing databases, keyed by the version they produce. schema.sql always describes the latest.
MIGRATIONS = {
    2: "ALTER TABLE zipcode_jurisdictions ADD COLUMN share REAL",  # share of the zipcode's land area
}

NEW, CHANGED, UNCHANGED = "new", "changed", "unchanged"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the database with foreign keys on and WAL so a report build can read during a run."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the schema on a new database or migrate an older one; refuse a newer one."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(f"database schema v{version} is newer than this code (v{SCHEMA_VERSION})")
    if version == SCHEMA_VERSION:
        return
    with conn:
        if version == 0:
            conn.executescript(resources.files("watcher").joinpath("schema.sql").read_text())
        else:
            for target in range(version + 1, SCHEMA_VERSION + 1):
                conn.execute(MIGRATIONS[target])
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def content_hash(title: str, summary: str, url: str, occurs_at: str | None) -> str:
    """Hash of the fields whose change counts as an edit (amended agenda, reschedule)."""
    payload = "\x1f".join([title, summary, url, occurs_at or ""])
    return hashlib.sha256(payload.encode()).hexdigest()


def upsert_item(
    conn: sqlite3.Connection,
    *,
    source_id: int,
    jurisdiction_id: int,
    external_id: str,
    item_type: str,
    title: str,
    summary: str = "",
    url: str = "",
    occurs_at: str | None = None,
) -> tuple[int, str]:
    """Store an item and report whether it is new, changed or unchanged since the last run.

    Returns (item_id, status). A changed item also gets a row in item_versions.
    """
    seen = now()
    new_hash = content_hash(title, summary, url, occurs_at)
    with conn:
        row = conn.execute(
            "SELECT id, content_hash FROM items WHERE source_id = ? AND external_id = ?",
            (source_id, external_id),
        ).fetchone()
        if row is None:
            cur = conn.execute(
                """INSERT INTO items (source_id, jurisdiction_id, external_id, item_type, title, summary,
                       url, occurs_at, content_hash, first_seen_at, last_seen_at, last_changed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_id, jurisdiction_id, external_id, item_type, title, summary,
                 url, occurs_at, new_hash, seen, seen, seen),
            )
            item_id = cur.lastrowid
            _add_version(conn, item_id, new_hash, title, summary, seen)
            return item_id, NEW
        item_id = row["id"]
        if row["content_hash"] == new_hash:
            conn.execute("UPDATE items SET last_seen_at = ? WHERE id = ?", (seen, item_id))
            return item_id, UNCHANGED
        conn.execute(
            """UPDATE items SET item_type = ?, title = ?, summary = ?, url = ?, occurs_at = ?,
                   content_hash = ?, last_seen_at = ?, last_changed_at = ? WHERE id = ?""",
            (item_type, title, summary, url, occurs_at, new_hash, seen, seen, item_id),
        )
        _add_version(conn, item_id, new_hash, title, summary, seen)
        return item_id, CHANGED


def _add_version(conn, item_id, new_hash, title, summary, seen):
    conn.execute(
        "INSERT INTO item_versions (item_id, content_hash, title, summary, seen_at) VALUES (?, ?, ?, ?, ?)",
        (item_id, new_hash, title, summary, seen),
    )


def get_or_create_jurisdiction(conn: sqlite3.Connection, level: str, name: str, code: str = "") -> int:
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO jurisdictions (level, name, code) VALUES (?, ?, ?)", (level, name, code)
        )
        row = conn.execute(
            "SELECT id FROM jurisdictions WHERE level = ? AND name = ? AND code = ?", (level, name, code)
        ).fetchone()
    return row["id"]


def get_or_create_source(
    conn: sqlite3.Connection, jurisdiction_id: int, name: str, kind: str, url: str, method: str
) -> int:
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO sources (jurisdiction_id, name, kind, url, method) VALUES (?, ?, ?, ?, ?)",
            (jurisdiction_id, name, kind, url, method),
        )
        row = conn.execute(
            "SELECT id FROM sources WHERE jurisdiction_id = ? AND name = ?", (jurisdiction_id, name)
        ).fetchone()
    return row["id"]
