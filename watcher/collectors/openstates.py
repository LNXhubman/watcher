"""California legislature via the Open States v3 API (bills and committee hearings).

Needs a free API key in the OPENSTATES_API_KEY environment variable (https://openstates.org/accounts/signup/).
Without one the collector is skipped. Written against the published OpenAPI spec and tested with fake
responses; it has not been run against the live API yet.
"""
import json
import os
import time
import urllib.request
from collections import Counter
from datetime import date
from urllib.parse import urlencode

from watcher import db
from watcher.collectors import Skipped

NAME = "Open States (California)"
API = "https://v3.openstates.org"
STATE_NAME, STATE_CODE = "California", "06"
PER_PAGE = 20
MAX_PAGES = 30  # a safety stop per endpoint per run
MIN_INTERVAL = 6.5  # seconds between requests; the free tier is rate limited (about 10 per minute)


def make_fetch(api_key: str, min_interval: float = MIN_INTERVAL):
    last = [0.0]

    def fetch(url: str) -> dict:
        wait = min_interval - (time.monotonic() - last[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"X-API-KEY": api_key, "User-Agent": "watcher/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        finally:
            last[0] = time.monotonic()
    return fetch


def pages(path: str, params: dict, fetch):
    """Yield results across pages of an Open States list endpoint."""
    for page in range(1, MAX_PAGES + 1):
        data = fetch(f"{API}{path}?" + urlencode({**params, "page": page, "per_page": PER_PAGE}))
        yield from data.get("results", [])
        if page >= data.get("pagination", {}).get("max_page", page):
            return


def bill_to_item(bill: dict) -> dict:
    action = bill.get("latest_action_description") or ""
    subjects = ", ".join(bill.get("subject") or [])
    summary = "\n".join(p for p in (f"Latest action: {action}" if action else "", f"Subjects: {subjects}" if subjects else "") if p)
    return {
        "external_id": bill["id"],
        "item_type": "legislation",
        "title": f"{bill['identifier']}: {bill['title']}",
        "summary": summary,
        "url": bill.get("openstates_url") or "",
        "occurs_at": bill.get("latest_action_date"),
    }


def event_to_item(event: dict) -> dict:
    location = (event.get("location") or {}).get("name") or ""
    link = next(iter(event.get("links") or event.get("sources") or []), {}).get("url", "")
    return {
        "external_id": event["id"],
        "item_type": "meeting",
        "title": event["name"],
        "summary": "\n".join(p for p in (event.get("description") or "", f"Location: {location}" if location else "") if p),
        "url": link,
        "occurs_at": event.get("start_date"),
    }


def register(conn) -> tuple[int, int]:
    jid = db.get_or_create_jurisdiction(conn, "state", STATE_NAME, STATE_CODE)
    return jid, db.get_or_create_source(conn, jid, NAME, "legislation", API, "api")


def collect(conn, since: date, fetch=None) -> Counter:
    if fetch is None:
        key = os.environ.get("OPENSTATES_API_KEY")
        if not key:
            raise Skipped("OPENSTATES_API_KEY is not set")
        fetch = make_fetch(key)
    jid, sid = register(conn)
    counts = Counter()
    bills = pages("/bills", {"jurisdiction": STATE_NAME, "updated_since": since.isoformat(), "sort": "updated_desc"}, fetch)
    events = pages("/events", {"jurisdiction": STATE_NAME, "after": since.isoformat()}, fetch)
    for item in [*map(bill_to_item, bills), *map(event_to_item, events)]:
        _, status = db.upsert_item(conn, source_id=sid, jurisdiction_id=jid, **item)
        counts[status] += 1
    return counts
