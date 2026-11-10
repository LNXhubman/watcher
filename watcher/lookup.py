"""Resolve a zipcode to the governments that cover it, using free Census Bureau data.

- Places (cities) and counties come from the Census ZCTA relationship files, which give the share of the
  zipcode's land area in each. A zipcode often touches several places; the user confirms which to watch.
- State, congressional district and state legislative districts come from the Census geocoder at the
  zipcode's centroid (from zippopotam.us), so they describe the centroid, not every part of the zipcode.
"""
import json
import urllib.request
from urllib.parse import urlencode

from watcher import db

REL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_{kind}20_natl.txt"
ZIP_API = "https://api.zippopotam.us/us/{zipcode}"
GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
SUGGEST_MIN_SHARE = 0.10  # places and counties with at least this share of the area are suggested for watching


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "watcher/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def http_get_lines(url: str):
    """Stream a large text file line by line without holding it in memory."""
    req = urllib.request.Request(url, headers={"User-Agent": "watcher/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        for raw in resp:
            yield raw.decode("utf-8-sig").rstrip("\r\n")


def relationship_rows(zipcode: str, kind: str, lines) -> list[dict]:
    """Rows of a Census relationship file for one zipcode, as {geoid, name, share}.

    The file is sorted by zipcode, so reading stops after the zipcode's block.
    """
    header = None
    seen = False
    out = []
    for line in lines:
        if header is None:
            header = line.split("|")
            continue
        cols = dict(zip(header, line.split("|")))
        if cols["GEOID_ZCTA5_20"] != zipcode:
            if seen:
                break
            continue
        seen = True
        geoid = cols.get(f"GEOID_{kind.upper()}_20", "")
        if not geoid:
            continue  # the part of the zipcode outside any place
        zcta_area = int(cols["AREALAND_ZCTA5_20"]) + int(cols["AREAWATER_ZCTA5_20"]) or 1
        part = int(cols["AREALAND_PART"]) + int(cols["AREAWATER_PART"])
        out.append({"geoid": geoid, "name": cols[f"NAMELSAD_{kind.upper()}_20"], "share": part / zcta_area})
    return sorted(out, key=lambda r: -r["share"])


def resolve(zipcode: str, fetch_json=http_get_json, fetch_lines=http_get_lines) -> list[dict]:
    """Candidate jurisdictions for a zipcode: dicts with level, name, code, share, suggested."""
    zinfo = fetch_json(ZIP_API.format(zipcode=zipcode))["places"][0]
    geo = fetch_json(f"{GEOCODER}?" + urlencode({
        "x": zinfo["longitude"], "y": zinfo["latitude"], "benchmark": "Public_AR_Current",
        "vintage": "Current_Current", "format": "json"}))["result"]["geographies"]
    state = geo["States"][0]
    state_name, state_code = state["NAME"], state["GEOID"]
    out = [{"level": "federal", "name": "United States", "code": "", "share": None, "suggested": True}]
    for layer in geo:
        for g in geo[layer]:
            if "Congressional District" in g["NAME"]:
                out.append({"level": "federal", "name": f"{state_name} {g['NAME']}", "code": g["GEOID"], "share": None, "suggested": True})
            elif "State Legislative Districts" in layer:
                out.append({"level": "state", "name": f"{state_name} {g['NAME']}", "code": g["GEOID"], "share": None, "suggested": True})
    out.append({"level": "state", "name": state_name, "code": state_code, "share": None, "suggested": True})
    for kind, level in (("county", "county"), ("place", "city")):
        rows = relationship_rows(zipcode, kind, fetch_lines(REL.format(kind=kind)))
        for i, r in enumerate(rows):
            out.append({"level": level, "name": r["name"], "code": r["geoid"], "share": r["share"],
                        "suggested": i == 0 or r["share"] >= SUGGEST_MIN_SHARE})
    return out


def save(conn, zipcode: str, candidates: list[dict]) -> None:
    """Store candidates. New links get the suggested confirmation; existing confirmations are kept."""
    state_id = None
    for c in candidates:
        if c["level"] == "state" and "District" not in c["name"]:
            state_id = db.get_or_create_jurisdiction(conn, "state", c["name"], c["code"])
    for c in candidates:
        is_part_of_state = c["level"] in ("county", "city") or (c["level"] == "state" and "District" in c["name"])
        parent = state_id if is_part_of_state else None
        jid = db.get_or_create_jurisdiction(conn, c["level"], c["name"], c["code"])
        with conn:
            if parent and parent != jid:
                conn.execute("UPDATE jurisdictions SET parent_id = ? WHERE id = ?", (parent, jid))
            conn.execute(
                "INSERT OR IGNORE INTO zipcode_jurisdictions (zipcode, jurisdiction_id, confirmed, share) VALUES (?, ?, ?, ?)",
                (zipcode, jid, int(c["suggested"]), c["share"]))
            conn.execute("UPDATE zipcode_jurisdictions SET share = ? WHERE zipcode = ? AND jurisdiction_id = ?",
                         (c["share"], zipcode, jid))


def linked(conn, zipcode: str) -> list:
    return conn.execute(
        """SELECT j.id, j.level, j.name, j.code, zj.confirmed, zj.share FROM zipcode_jurisdictions zj
           JOIN jurisdictions j ON j.id = zj.jurisdiction_id WHERE zj.zipcode = ?
           ORDER BY CASE j.level WHEN 'federal' THEN 0 WHEN 'state' THEN 1 WHEN 'county' THEN 2 ELSE 3 END,
                    zj.share DESC, j.name""", (zipcode,)).fetchall()


def set_confirmed(conn, zipcode: str, names: list[str], confirmed: bool) -> list[str]:
    """Confirm or unconfirm jurisdictions by exact name; returns the names that were not found."""
    missing = []
    for name in names:
        with conn:
            cur = conn.execute(
                """UPDATE zipcode_jurisdictions SET confirmed = ? WHERE zipcode = ? AND jurisdiction_id IN
                   (SELECT id FROM jurisdictions WHERE name = ?)""", (int(confirmed), zipcode, name))
        if cur.rowcount == 0:
            missing.append(name)
    return missing
