import unittest
from datetime import date

from watcher import collect, db
from watcher.collectors import Skipped, openstates as osx

BILLS = [
    {"id": "ocd-bill/1", "identifier": "AB 1", "title": "Housing element", "subject": ["Housing", "Land use"],
     "latest_action_description": "Read second time", "latest_action_date": "2026-11-05", "openstates_url": "https://os/ab1"},
    {"id": "ocd-bill/2", "identifier": "SB 2", "title": "Water supply", "subject": [],
     "latest_action_description": "", "latest_action_date": "2026-11-06", "openstates_url": "https://os/sb2"},
]
EVENTS = [
    {"id": "ocd-event/1", "name": "Assembly Housing Committee", "description": "Regular hearing",
     "start_date": "2026-11-12T09:00:00-08:00", "location": {"name": "State Capitol, Room 126"},
     "links": [], "sources": [{"url": "https://assembly.ca.gov/h"}]},
]


def fake_fetch(url):
    results = BILLS if "/bills" in url else EVENTS
    return {"results": results, "pagination": {"page": 1, "max_page": 1, "total_items": len(results)}}


class ItemMappingTests(unittest.TestCase):
    def test_bill(self):
        item = osx.bill_to_item(BILLS[0])
        self.assertEqual(item["title"], "AB 1: Housing element")
        self.assertEqual(item["item_type"], "legislation")
        self.assertEqual(item["summary"], "Latest action: Read second time\nSubjects: Housing, Land use")
        self.assertEqual(osx.bill_to_item(BILLS[1])["summary"], "")

    def test_event(self):
        item = osx.event_to_item(EVENTS[0])
        self.assertEqual((item["item_type"], item["url"]), ("meeting", "https://assembly.ca.gov/h"))
        self.assertIn("Location: State Capitol, Room 126", item["summary"])


class PagingTests(unittest.TestCase):
    def test_follows_pages_until_max_page(self):
        calls = []

        def fetch(url):
            calls.append(url)
            n = len(calls)
            return {"results": [{"n": n}], "pagination": {"max_page": 3}}
        self.assertEqual(list(osx.pages("/bills", {}, fetch)), [{"n": 1}, {"n": 2}, {"n": 3}])
        self.assertIn("page=3", calls[-1])


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        db.init_db(self.conn)

    def test_stores_bills_and_hearings_at_state_level(self):
        counts = osx.collect(self.conn, date(2026, 11, 2), fake_fetch)
        self.assertEqual(counts[db.NEW], 3)
        levels = {r[0] for r in self.conn.execute("SELECT j.level FROM items i JOIN jurisdictions j ON j.id = i.jurisdiction_id")}
        self.assertEqual(levels, {"state"})
        again = osx.collect(self.conn, date(2026, 11, 2), fake_fetch)
        self.assertEqual(again[db.UNCHANGED], 3)

    def test_new_action_marks_bill_changed(self):
        osx.collect(self.conn, date(2026, 11, 2), fake_fetch)
        moved = [dict(BILLS[0], latest_action_description="Passed", latest_action_date="2026-11-09")] + BILLS[1:]
        counts = osx.collect(self.conn, date(2026, 11, 2), lambda u: {"results": moved if "/bills" in u else EVENTS, "pagination": {"max_page": 1}})
        self.assertEqual(counts[db.CHANGED], 1)

    def test_missing_key_is_skipped_not_failed(self):
        import os
        os.environ.pop("OPENSTATES_API_KEY", None)
        with self.assertRaises(Skipped):
            osx.collect(self.conn, date(2026, 11, 2))
        result = collect.run(self.conn, today=date(2026, 11, 9), collectors=[osx])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(self.conn.execute("SELECT status FROM source_runs").fetchone()[0], "skipped")


if __name__ == "__main__":
    unittest.main()
