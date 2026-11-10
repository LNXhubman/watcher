import re
import unittest
from datetime import date

from watcher import collect, db
from watcher.collectors import federal_register as fr

DOCS = [
    {"document_number": "2026-1", "title": "A Final Rule", "abstract": "Does a thing.", "html_url": "https://x/1",
     "publication_date": "2026-11-09", "type": "Rule", "agency_names": ["Agency A", "Agency B"], "comments_close_on": None},
    {"document_number": "2026-2", "title": "A Proposed Rule", "abstract": None, "html_url": "https://x/2",
     "publication_date": "2026-11-09", "type": "Proposed Rule", "agency_names": [], "comments_close_on": "2026-12-09"},
    {"document_number": "2026-3", "title": "A Notice", "abstract": "Info.", "html_url": "https://x/3",
     "publication_date": "2026-11-08", "type": "Notice", "agency_names": ["Agency C"], "comments_close_on": None},
    {"document_number": "2026-4", "title": "An Order", "abstract": None, "html_url": "https://x/4",
     "publication_date": "2026-11-08", "type": "Presidential Document", "agency_names": None, "comments_close_on": None},
]


def fake_fetch(docs, page_size=2):
    """Serve docs in pages, like the real API's next_page_url."""
    def fetch(url):
        m = re.search(r"[?&]page=(\d+)", url)
        page = int(m.group(1)) if m else 0
        chunk = docs[page * page_size:(page + 1) * page_size]
        more = (page + 1) * page_size < len(docs)
        return {"results": chunk, "next_page_url": f"https://fake/?page={page + 1}" if more else None}
    return fetch


class ToItemTests(unittest.TestCase):
    def test_types_and_dates(self):
        items = [fr.to_item(d) for d in DOCS]
        self.assertEqual([i["item_type"] for i in items], ["legislation", "comment_deadline", "notice", "other"])
        self.assertEqual(items[1]["occurs_at"], "2026-12-09")
        self.assertEqual(items[0]["occurs_at"], "2026-11-09")

    def test_summary_includes_agencies_and_abstract(self):
        self.assertEqual(fr.to_item(DOCS[0])["summary"], "Agencies: Agency A; Agency B\nDoes a thing.")
        self.assertEqual(fr.to_item(DOCS[1])["summary"], "")


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        db.init_db(self.conn)

    def test_pagination_and_idempotence(self):
        docs = fr.fetch_documents(date(2026, 11, 2), fake_fetch(DOCS))
        self.assertEqual(len(docs), 4)
        first = fr.collect(self.conn, date(2026, 11, 2), fake_fetch(DOCS))
        self.assertEqual(first[db.NEW], 4)
        second = fr.collect(self.conn, date(2026, 11, 2), fake_fetch(DOCS))
        self.assertEqual((second[db.NEW], second[db.UNCHANGED]), (0, 4))

    def test_amended_document_is_changed(self):
        fr.collect(self.conn, date(2026, 11, 2), fake_fetch(DOCS))
        amended = [dict(DOCS[0], title="A Final Rule (corrected)")] + DOCS[1:]
        counts = fr.collect(self.conn, date(2026, 11, 2), fake_fetch(amended))
        self.assertEqual(counts[db.CHANGED], 1)

    def test_run_records_success(self):
        class Ok:
            NAME, API = fr.NAME, fr.API
            register = staticmethod(fr.register)
            collect = staticmethod(lambda conn, since: fr.collect(conn, since, fake_fetch(DOCS)))
        result = collect.run(self.conn, today=date(2026, 11, 9), collectors=[Ok])
        self.assertEqual((result["status"], result["new"]), ("ok", 4))
        self.assertEqual(self.conn.execute("SELECT status FROM source_runs").fetchone()[0], "ok")

    def test_run_survives_a_failing_source(self):
        class Broken:
            NAME, API = "Broken", "https://broken.test"
            @staticmethod
            def register(conn):
                jid = db.get_or_create_jurisdiction(conn, "federal", "United States")
                return jid, db.get_or_create_source(conn, jid, "Broken", "notices", "https://broken.test", "api")
            @staticmethod
            def collect(conn, since):
                raise OSError("boom")
        result = collect.run(self.conn, today=date(2026, 11, 9), collectors=[Broken])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.conn.execute("SELECT last_error FROM sources WHERE name = 'Broken'").fetchone()[0], "boom")


if __name__ == "__main__":
    unittest.main()
