import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from watcher import db, report
from watcher.collectors import federal_register as fr
from tests.test_federal_register import DOCS, fake_fetch


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        db.init_db(self.conn)
        fr.collect(self.conn, date(2026, 11, 2), fake_fetch(DOCS))
        self.rep = report.build(self.conn, date.today())

    def test_iso_week(self):
        self.assertEqual(report.iso_week(date(2026, 11, 9)), "2026-W46")

    def test_levels_always_present(self):
        self.assertEqual(list(self.rep["levels"]), ["city", "county", "state", "federal"])
        self.assertEqual(self.rep["levels"]["city"]["total"], 0)
        self.assertEqual(self.rep["levels"]["federal"]["total"], 4)

    def test_open_comment_deadline_listed_first(self):
        soon = (date.today() + timedelta(days=1)).isoformat()
        fr.collect(self.conn, date(2026, 11, 2), fake_fetch([dict(DOCS[1], document_number="open", comments_close_on=soon)]))
        first = report.build(self.conn, date.today())["levels"]["federal"]["items"][0]
        self.assertEqual((first["type"], first["date"]), ("comment_deadline", soon))

    def test_window_excludes_items_not_changed_in_it(self):
        old = report.build(self.conn, date.today() - timedelta(days=30))
        self.assertEqual(old["levels"]["federal"]["total"], 4)  # window start is before now, so rows still qualify
        self.conn.execute("UPDATE items SET last_changed_at = '2020-01-01T00:00:00Z'")
        self.assertEqual(report.build(self.conn, date.today())["levels"]["federal"]["total"], 0)

    def test_data_has_all_items_but_documents_are_capped(self):
        for i in range(report.MAX_ITEMS_PER_LEVEL + 5):
            fr.collect(self.conn, date(2026, 11, 2), fake_fetch([dict(DOCS[2], document_number=f"n{i}")]))
        rep = report.build(self.conn, date.today())
        fed = rep["levels"]["federal"]
        self.assertEqual(len(fed["items"]), fed["total"])
        self.assertEqual(report.to_markdown(rep).count("\n- ["), report.MAX_ITEMS_PER_LEVEL)

    def test_top_words(self):
        titles = ["Zoning variance for housing", "Housing element update", "Zoning code", "The rule of the act"]
        self.assertEqual(report.top_words(titles), [["housing", 2], ["zoning", 2]])
        self.assertEqual(report.top_words(["Housing housing housing"]), [])  # counted once per title, singletons dropped

    def test_words_in_report_data(self):
        for i in range(3):
            fr.collect(self.conn, date(2026, 11, 2), fake_fetch([dict(DOCS[2], document_number=f"w{i}", title="Wildfire safety plan")]))
        words = dict(report.build(self.conn, date.today())["levels"]["federal"]["words"])
        self.assertEqual(words["wildfire"], 3)

    def test_write_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = report.write(self.conn, self.rep, root, root / "data")
            self.assertIn("A Final Rule", paths["md"].read_text())
            self.assertIn("A Final Rule", paths["html"].read_text())
            js = (root / "data" / "site-data.js").read_text()
            self.assertTrue(js.startswith("window.WATCHER_DATA = "))
            data = json.loads(js[len("window.WATCHER_DATA = "):].rstrip(";\n"))
            self.assertEqual(data["iso_week"], self.rep["iso_week"])
            report.write(self.conn, self.rep, root, root / "data")  # rewriting the same week is fine
            self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0], 1)

    def test_html_escapes_titles(self):
        fr.collect(self.conn, date(2026, 11, 2), fake_fetch([dict(DOCS[2], document_number="x", title="<script>alert(1)</script>")]))
        self.assertNotIn("<script>alert", report.to_html(report.build(self.conn, date.today())))


if __name__ == "__main__":
    unittest.main()
