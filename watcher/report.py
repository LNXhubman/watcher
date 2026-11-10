"""Build the weekly report from SQLite: Markdown and HTML files, plus a JS data file for the front page."""
import html
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from watcher import db

LEVELS = ["city", "county", "state", "federal"]
MAX_ITEMS_PER_LEVEL = 25  # items listed in the Markdown/HTML report; the front page data carries all of them
MAX_WORDS = 40
STOP_WORDS = set("""
a an and are as at be by for from has have in into is it its of on or that the their this to was were will with
not under over per via new other than such these those which who whose also may can any all each more most
rule rules final proposed notice notices amendment amendments amend act part parts code federal register united
states department agency agencies administration office regulation regulations request requests comment comments
information collection activities activity submission review approval public order orders application applications
program programs service services system systems national board committee meeting meetings certain related
llc inc ltd corp co company companies
""".split())
WORD_RE = re.compile(r"[a-z][a-z'-]{2,}")


def top_words(titles, limit=MAX_WORDS):
    """Word cloud data: how many item titles contain each word (stop words dropped, singletons dropped)."""
    counts = Counter()
    for title in titles:
        counts.update({w for w in WORD_RE.findall(title.lower()) if w not in STOP_WORDS})
    ranked = sorted(counts.items(), key=lambda wn: (-wn[1], wn[0]))  # ties alphabetical, so output is stable
    return [[w, n] for w, n in ranked[:limit] if n >= 2]
TYPE_LABELS = {
    "comment_deadline": "Comment deadline", "legislation": "Rule or legislation", "notice": "Notice",
    "meeting": "Meeting", "agenda_item": "Agenda item", "vote": "Vote", "budget": "Budget",
    "permit": "Permit", "election": "Election", "other": "Other",
}


def iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def build(conn, end: date) -> dict:
    """Report data for the 7 days ending on `end` (inclusive)."""
    start = end - timedelta(days=6)
    since = f"{start.isoformat()}T00:00:00Z"
    levels = {}
    for level in LEVELS:
        rows = conn.execute(
            """SELECT i.*, j.name AS jurisdiction FROM items i JOIN jurisdictions j ON j.id = i.jurisdiction_id
               WHERE j.level = ? AND i.last_changed_at >= ?""", (level, since)).fetchall()
        # comment deadlines still open come first (soonest first), then the newest items
        deadlines = sorted((r for r in rows if r["item_type"] == "comment_deadline" and (r["occurs_at"] or "") >= end.isoformat()),
                           key=lambda r: r["occurs_at"])
        open_ids = {r["id"] for r in deadlines}
        others = sorted((r for r in rows if r["id"] not in open_ids), key=lambda r: (r["occurs_at"] or "", r["id"]), reverse=True)
        ordered = deadlines + others
        counts = {}
        for r in rows:
            counts[r["item_type"]] = counts.get(r["item_type"], 0) + 1
        levels[level] = {
            "total": len(rows),
            "counts": counts,
            "words": top_words(r["title"] for r in rows),
            "items": [
                {"title": r["title"], "type": r["item_type"], "date": r["occurs_at"], "url": r["url"],
                 "changed": r["first_seen_at"] != r["last_changed_at"]}
                for r in ordered
            ],
        }
    health = conn.execute("SELECT status FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    return {
        "iso_week": iso_week(end),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "generated_at": db.now(),
        "last_run_status": health["status"] if health else "never run",
        "levels": levels,
    }


def to_markdown(rep: dict) -> str:
    lines = [f"# Watcher weekly report {rep['iso_week']}", "",
             f"{rep['start']} to {rep['end']}. Last run: {rep['last_run_status']}.", ""]
    for level in LEVELS:
        data = rep["levels"][level]
        lines += [f"## {level.capitalize()}", ""]
        if not data["total"]:
            lines += ["No activity collected yet.", ""]
            continue
        summary = ", ".join(f"{n} {TYPE_LABELS.get(t, t).lower()}" for t, n in sorted(data["counts"].items()))
        lines += [f"{data['total']} items ({summary}). Showing {min(data['total'], MAX_ITEMS_PER_LEVEL)}.", ""]
        for it in data["items"][:MAX_ITEMS_PER_LEVEL]:
            tag = "changed" if it["changed"] else TYPE_LABELS.get(it["type"], it["type"])
            lines.append(f"- [{it['title']}]({it['url']}) ({tag}, {it['date']})")
        lines.append("")
    return "\n".join(lines)


def to_html(rep: dict) -> str:
    e = html.escape
    body = []
    for level in LEVELS:
        data = rep["levels"][level]
        body.append(f'<section class="level"><h3>{level.capitalize()}</h3>')
        if not data["total"]:
            body.append('<p class="placeholder">No activity collected yet.</p></section>')
            continue
        summary = ", ".join(f"{n} {TYPE_LABELS.get(t, t).lower()}" for t, n in sorted(data["counts"].items()))
        body.append(f'<p class="def">{data["total"]} items ({e(summary)}). Showing {min(data["total"], MAX_ITEMS_PER_LEVEL)}.</p><ul class="items">')
        for it in data["items"][:MAX_ITEMS_PER_LEVEL]:
            tag = "changed" if it["changed"] else TYPE_LABELS.get(it["type"], it["type"])
            body.append(f'<li><a href="{e(it["url"])}">{e(it["title"])}</a> <span class="meta">{e(tag)}, {e(str(it["date"]))}</span></li>')
        body.append("</ul></section>")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Watcher weekly report {rep['iso_week']}</title>
<link rel="stylesheet" href="../style.css">
</head>
<body>
<header>
  <h1>Watcher weekly report {rep['iso_week']}</h1>
  <p class="crumbs"><a href="../index.html">Home</a> / {rep['iso_week']}</p>
  <p class="intro">{rep['start']} to {rep['end']}. Last run: {e(rep['last_run_status'])}.</p>
</header>
<main>
<div class="levels">
{chr(10).join(body)}
</div>
</main>
</body>
</html>
"""


def write(conn, rep: dict, root: Path, data_dir: Path) -> dict:
    """Write reports/<week>.md and .html, a row in `reports`, and data/site-data.js for the pages."""
    reports_dir = root / "reports"
    reports_dir.mkdir(exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    md_path = reports_dir / f"{rep['iso_week']}.md"
    html_path = reports_dir / f"{rep['iso_week']}.html"
    md_path.write_text(to_markdown(rep))
    html_path.write_text(to_html(rep))
    with conn:
        conn.execute(
            """INSERT INTO reports (iso_week, generated_at, html_path, md_path) VALUES (?, ?, ?, ?)
               ON CONFLICT (iso_week) DO UPDATE SET generated_at = excluded.generated_at,
                   html_path = excluded.html_path, md_path = excluded.md_path""",
            (rep["iso_week"], rep["generated_at"], str(html_path.relative_to(root)), str(md_path.relative_to(root))),
        )
    # file:// pages cannot fetch JSON, so the data ships as a script that sets a global
    (data_dir / "site-data.js").write_text("window.WATCHER_DATA = " + json.dumps(rep) + ";\n")
    return {"md": md_path, "html": html_path}
