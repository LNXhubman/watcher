import sqlite3
import unittest

from watcher import db, lookup

HEADER = ("OID_ZCTA5_20|GEOID_ZCTA5_20|NAMELSAD_ZCTA5_20|AREALAND_ZCTA5_20|AREAWATER_ZCTA5_20|MTFCC_ZCTA5_20|CLASSFP_ZCTA5_20|"
          "FUNCSTAT_ZCTA5_20|OID_PLACE_20|GEOID_PLACE_20|NAMELSAD_PLACE_20|AREALAND_PLACE_20|AREAWATER_PLACE_20|MTFCC_PLACE_20|"
          "CLASSFP_PLACE_20|FUNCSTAT_PLACE_20|AREALAND_PART|AREAWATER_PART")


def row(zipcode, geoid, name, land, water=0, zland=1000, zwater=0):
    return f"1|{zipcode}|ZCTA5 {zipcode}|{zland}|{zwater}|G6350|B5|S|2|{geoid}|{name}|9|9|G4110|C1|A|{land}|{water}"


REL_LINES = [
    HEADER,
    row("95050", "0669084", "Santa Clara city", 1000),
    "1|95051|ZCTA5 95051|1000|0|G6350|B5|S|||||||||20|0",  # the part outside any place
    row("95051", "0617610", "Cupertino city", 50),
    row("95051", "0668000", "San Jose city", 30),
    row("95051", "0669084", "Santa Clara city", 900),
    row("95052", "0669084", "Santa Clara city", 1000),
    row("95053", "0669084", "Santa Clara city", 1000),
]


def fake_json(url):
    if "zippopotam" in url:
        return {"places": [{"longitude": "-121.98", "latitude": "37.34"}]}
    return {"result": {"geographies": {
        "States": [{"NAME": "California", "GEOID": "06"}],
        "120th Congressional Districts": [{"NAME": "Congressional District 17", "GEOID": "0617"}],
        "2026 State Legislative Districts - Upper": [{"NAME": "State Senate District 15", "GEOID": "06015"}],
        "2026 State Legislative Districts - Lower": [{"NAME": "Assembly District 25", "GEOID": "06025"}],
    }}}


def fake_lines(url):
    if "county" in url:
        return iter([HEADER.replace("PLACE", "COUNTY"), row("95051", "06085", "Santa Clara County", 1000).replace("0669084", "")])
    return iter(REL_LINES)


class RelationshipTests(unittest.TestCase):
    def test_shares_sorted_and_empty_place_skipped(self):
        rows = lookup.relationship_rows("95051", "place", iter(REL_LINES))
        self.assertEqual([r["name"] for r in rows], ["Santa Clara city", "Cupertino city", "San Jose city"])
        self.assertAlmostEqual(rows[0]["share"], 0.9)

    def test_stops_after_the_zipcode_block(self):
        consumed = []

        def lines():
            for line in REL_LINES:
                consumed.append(line)
                yield line
        lookup.relationship_rows("95051", "place", lines())
        self.assertNotIn(REL_LINES[-1], consumed)  # one line past the block is read to see it ended; no more

    def test_unknown_zipcode(self):
        self.assertEqual(lookup.relationship_rows("00000", "place", iter(REL_LINES)), [])


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.cands = lookup.resolve("95051", fetch_json=fake_json, fetch_lines=fake_lines)

    def by_name(self, name):
        return next(c for c in self.cands if c["name"] == name)

    def test_levels_present(self):
        self.assertEqual({c["level"] for c in self.cands}, {"federal", "state", "county", "city"})
        self.assertEqual(self.by_name("California")["code"], "06")
        self.assertEqual(self.by_name("California Congressional District 17")["level"], "federal")
        self.assertEqual(self.by_name("California Assembly District 25")["level"], "state")

    def test_suggestions(self):
        self.assertTrue(self.by_name("Santa Clara city")["suggested"])
        self.assertFalse(self.by_name("Cupertino city")["suggested"])   # 5% of the area
        self.assertFalse(self.by_name("San Jose city")["suggested"])


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        db.init_db(self.conn)
        lookup.save(self.conn, "95051", lookup.resolve("95051", fetch_json=fake_json, fetch_lines=fake_lines))

    def confirmed(self):
        return {r["name"] for r in lookup.linked(self.conn, "95051") if r["confirmed"]}

    def test_saved_with_suggested_confirmation(self):
        self.assertIn("Santa Clara city", self.confirmed())
        self.assertNotIn("Cupertino city", self.confirmed())

    def test_parent_is_the_state(self):
        row = self.conn.execute("SELECT p.name FROM jurisdictions j JOIN jurisdictions p ON p.id = j.parent_id WHERE j.name = 'Santa Clara city'").fetchone()
        self.assertEqual(row[0], "California")

    def test_confirm_and_resave_keeps_choice(self):
        self.assertEqual(lookup.set_confirmed(self.conn, "95051", ["Cupertino city", "Nowhere"], True), ["Nowhere"])
        lookup.save(self.conn, "95051", lookup.resolve("95051", fetch_json=fake_json, fetch_lines=fake_lines))
        self.assertIn("Cupertino city", self.confirmed())
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM zipcode_jurisdictions").fetchone()[0], len(lookup.linked(self.conn, "95051")))

    def test_unconfirm(self):
        lookup.set_confirmed(self.conn, "95051", ["Santa Clara city"], False)
        self.assertNotIn("Santa Clara city", self.confirmed())


class MigrationTests(unittest.TestCase):
    def test_v1_database_is_upgraded(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE zipcode_jurisdictions (zipcode TEXT, jurisdiction_id INTEGER, confirmed INTEGER)")
        conn.execute("PRAGMA user_version = 1")
        db.init_db(conn)
        conn.execute("SELECT share FROM zipcode_jurisdictions")
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
