"""Run all collectors once and record the run and per-source results."""
from datetime import date, timedelta

from watcher import db
from watcher.collectors import Skipped, federal_register, openstates

COLLECTORS = [federal_register, openstates]


def run(conn, days: int = 7, today: date | None = None, collectors=None) -> dict:
    since = (today or date.today()) - timedelta(days=days)
    started = db.now()
    run_id = conn.execute("INSERT INTO runs (started_at) VALUES (?)", (started,)).lastrowid
    conn.commit()
    totals = {db.NEW: 0, db.CHANGED: 0, db.UNCHANGED: 0}
    failures = skipped = 0
    for collector in collectors or COLLECTORS:
        _, sid = collector.register(conn)
        try:
            counts = collector.collect(conn, since)
        except Skipped as e:
            with conn:
                conn.execute("INSERT INTO source_runs (run_id, source_id, status, error) VALUES (?, ?, 'skipped', ?)",
                             (run_id, sid, str(e)))
            skipped += 1
            continue
        except Exception as e:  # a broken source must not stop the others
            failures += 1
            with conn:
                conn.execute("INSERT INTO source_runs (run_id, source_id, status, error) VALUES (?, ?, 'failed', ?)",
                             (run_id, sid, str(e)))
                conn.execute("UPDATE sources SET last_error = ? WHERE id = ?", (str(e), sid))
            continue
        found = sum(counts.values())
        with conn:
            conn.execute("INSERT INTO source_runs (run_id, source_id, status, items_found) VALUES (?, ?, 'ok', ?)",
                         (run_id, sid, found))
            conn.execute("UPDATE sources SET last_success_at = ?, last_error = NULL WHERE id = ?", (db.now(), sid))
        for key in totals:
            totals[key] += counts.get(key, 0)
    ran = len(collectors or COLLECTORS) - skipped
    status = "ok" if not failures else ("failed" if failures == ran else "partial")
    with conn:
        conn.execute("UPDATE runs SET finished_at = ?, status = ?, items_new = ?, items_changed = ? WHERE id = ?",
                     (db.now(), status, totals[db.NEW], totals[db.CHANGED], run_id))
    return {"run_id": run_id, "status": status, **totals}
