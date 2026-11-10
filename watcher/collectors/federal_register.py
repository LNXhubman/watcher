"""Federal Register collector (https://www.federalregister.gov/developers/documentation/api/v1).

The API is public and needs no key. Everything it returns is stored at the federal level;
deciding what is relevant is the job of interest matching (M3), not this collector.
"""
import json
import urllib.request
from collections import Counter
from datetime import date
from urllib.parse import urlencode

from watcher import db

NAME = "Federal Register"
API = "https://www.federalregister.gov/api/v1/documents.json"
FIELDS = ["document_number", "title", "abstract", "html_url", "publication_date", "type",
          "agency_names", "comments_close_on"]


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "watcher/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_documents(since: date, fetch=http_get_json) -> list[dict]:
    """All documents published on or after `since`, following pagination."""
    params = [("conditions[publication_date][gte]", since.isoformat()), ("per_page", "1000"),
              ("order", "newest")] + [("fields[]", f) for f in FIELDS]
    url = f"{API}?{urlencode(params)}"
    docs = []
    while url:
        page = fetch(url)
        docs.extend(page.get("results", []))
        url = page.get("next_page_url")
    return docs


def to_item(doc: dict) -> dict:
    """Map a Federal Register document to the arguments of db.upsert_item (minus ids)."""
    kind = doc.get("type") or ""
    deadline = doc.get("comments_close_on")
    if kind == "Proposed Rule" and deadline:
        item_type, occurs_at = "comment_deadline", deadline
    elif kind in ("Rule", "Proposed Rule"):
        item_type, occurs_at = "legislation", doc["publication_date"]
    elif kind == "Notice":
        item_type, occurs_at = "notice", doc["publication_date"]
    else:  # Presidential Document and anything new
        item_type, occurs_at = "other", doc["publication_date"]
    agencies = "; ".join(doc.get("agency_names") or [])
    summary = "\n".join(part for part in (f"Agencies: {agencies}" if agencies else "", doc.get("abstract") or "") if part)
    return {
        "external_id": doc["document_number"],
        "item_type": item_type,
        "title": doc["title"],
        "summary": summary,
        "url": doc.get("html_url") or "",
        "occurs_at": occurs_at,
    }


def register(conn) -> tuple[int, int]:
    """Ensure the jurisdiction and source rows exist; returns (jurisdiction_id, source_id)."""
    jid = db.get_or_create_jurisdiction(conn, "federal", "United States")
    return jid, db.get_or_create_source(conn, jid, NAME, "notices", API, "api")


def collect(conn, since: date, fetch=http_get_json) -> Counter:
    jid, sid = register(conn)
    counts = Counter()
    for doc in fetch_documents(since, fetch):
        _, status = db.upsert_item(conn, source_id=sid, jurisdiction_id=jid, **to_item(doc))
        counts[status] += 1
    return counts
