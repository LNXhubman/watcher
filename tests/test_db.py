import sqlite3
import unittest

from watcher import db


def make_db():
    conn = db.connect(":memory:")
    db.init_db(conn)
    cur = conn.execute("INSERT INTO jurisdictions (level, name) VALUES ('federal', 'United States')")
    jid = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO sources (jurisdiction_id, name, kind, url, method) VALUES (?, 'Federal Register', 'notices', 'https://example.test', 'api')",
        (jid,),
    )
    return conn, jid, cur.lastrowid


class SchemaTests(unittest.TestCase):
    def test_init_sets_version_and_is_idempotent(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        db.init_db(conn)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)

    def test_newer_database_is_refused(self):
        conn = db.connect(":memory:")
        conn.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION + 1}")
        with self.assertRaises(RuntimeError):
            db.init_db(conn)

    def test_invalid_level_rejected(self):
        conn, _, _ = make_db()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO jurisdictions (level, name) VALUES ('galaxy', 'x')")

    def test_foreign_keys_enforced(self):
        conn, _, _ = make_db()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO sources (jurisdiction_id, name, kind, url, method) VALUES (999, 'x', 'k', 'u', 'api')")


class UpsertTests(unittest.TestCase):
    def setUp(self):
        self.conn, self.jid, self.sid = make_db()

    def upsert(self, **overrides):
        args = dict(source_id=self.sid, jurisdiction_id=self.jid, external_id="doc-1",
                    item_type="notice", title="Rule", summary="A rule", url="https://example.test/1")
        args.update(overrides)
        return db.upsert_item(self.conn, **args)

    def test_new_then_unchanged(self):
        item_id, status = self.upsert()
        self.assertEqual(status, db.NEW)
        again_id, status = self.upsert()
        self.assertEqual((again_id, status), (item_id, db.UNCHANGED))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM item_versions").fetchone()[0], 1)

    def test_edit_is_changed_and_versioned(self):
        item_id, _ = self.upsert()
        _, status = self.upsert(title="Rule (amended)")
        self.assertEqual(status, db.CHANGED)
        self.assertEqual(self.conn.execute("SELECT title FROM items WHERE id = ?", (item_id,)).fetchone()[0], "Rule (amended)")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM item_versions WHERE item_id = ?", (item_id,)).fetchone()[0], 2)

    def test_reschedule_counts_as_change(self):
        self.upsert(occurs_at="2026-11-10T18:00:00Z")
        _, status = self.upsert(occurs_at="2026-11-12T18:00:00Z")
        self.assertEqual(status, db.CHANGED)

    def test_same_external_id_in_different_sources_is_separate(self):
        other = self.conn.execute(
            "INSERT INTO sources (jurisdiction_id, name, kind, url, method) VALUES (?, 'Other', 'notices', 'u', 'api')", (self.jid,)
        ).lastrowid
        a, _ = self.upsert()
        b, status = self.upsert(source_id=other)
        self.assertNotEqual(a, b)
        self.assertEqual(status, db.NEW)

    def test_invalid_item_type_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.upsert(item_type="gossip")


if __name__ == "__main__":
    unittest.main()
