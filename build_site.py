#!/usr/bin/env python3
"""Generate the Watcher HTML pages from one definition of the nav, sections and levels.

Run: python3 build_site.py
Edit the data below (not the generated *.html files); style.css is hand-edited.
"""
from pathlib import Path

OUT = Path(__file__).parent

# (slug, nav/title text, intro, placeholder shown in each level card)
SECTIONS = [
    ("report", "Weekly report", "Summary of the past week, built from the daily collections.", "No reports yet."),
    ("upcoming", "Upcoming", "Meetings and public comment deadlines coming up.", "Nothing scheduled yet."),
    ("interests", "Interests", "Topics, keywords and locations to track, and the items that match them.", "No interests defined yet."),
    ("history", "History", "Past reports in a standard, easy-to-read format.", "No history yet."),
    ("health", "Run health", "Status of the daily run and of the data sources at each level.", "The agent has not run yet."),
]

# Fixed order; every section page shows all four.
LEVELS = [
    ("City", "Municipal government: city council, mayor, planning and zoning boards, city departments."),
    ("County", "County government: board of commissioners or supervisors, sheriff, courts, county-wide services and districts."),
    ("State", "State government: legislature, governor, state agencies and courts."),
    ("Federal", "Federal government: Congress, the President, federal agencies and courts."),
]

# Chosen brand: watchtower logo, motto and couplet.
LOGO_SVG = '''<path d="M52 108 L58 50 L72 50 L78 108 Z"/><path d="M55 80H75M54 95H76"/><path d="M45 34 Q65 18 85 34 Q65 50 45 34 Z"/><circle class="f" cx="65" cy="34" r="5"/>
<path d="M65 12V6M42 18L37 13M88 18L93 13"/><path d="M30 108H100"/>'''
MOTTO = "Tower eyes, outward."
COUPLET = ("Let tower eyes look outward, wide and keen,", "And keep the halls of power plainly seen.")

TAGLINE = "Local government activity for your zipcode: city, county, state and federal."

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
"""

FOOT = "</body>\n</html>\n"


def nav(current):
    links = ['<a href="index.html">Home</a>']
    for slug, text, _, _ in SECTIONS:
        mark = ' aria-current="page"' if slug == current else ""
        links.append(f'<a href="{slug}.html"{mark}>{text}</a>')
    return '<nav aria-label="Sections">' + "".join(links) + "</nav>"


def level_cards(placeholder):
    return "\n".join(
        f"""    <div class="level">
      <h3>{name}</h3>
      <p class="def">{definition}</p>
      <p class="placeholder">{placeholder}</p>
    </div>"""
        for name, definition in LEVELS
    )


def section_page(slug, text, intro, placeholder):
    return (
        HEAD.format(title=f"Watcher: {text}")
        + f"""<header>
  {lockup(motto=False)}
  {nav(slug)}
  <p class="crumbs"><a href="index.html">Home</a> / {text}</p>
</header>
<main>
  <h2>{text}</h2>
  <p class="intro">{intro}</p>
  <span class="badge">Under construction</span>
  <div class="levels">
{level_cards(placeholder)}
  </div>
</main>
<footer><p>Watcher is under construction.</p></footer>
"""
        + FOOT
    )


def lockup(motto=True):
    sub = f'\n    <p class="motto">{MOTTO}</p>' if motto else ""
    return f"""<a class="lockup" href="index.html">
    <svg viewBox="0 0 120 120" role="img" aria-label="Watcher logo: watchtower with an outward-looking eye">{LOGO_SVG}</svg>
    <div><h1>Watcher</h1>{sub}</div>
  </a>"""


def index_page():
    cards = "\n".join(
        f"""    <a class="card" href="{slug}.html">
      <h2>{text}</h2>
      <p>{intro}</p>
      <span class="badge">Under construction</span>
    </a>"""
        for slug, text, intro, _ in SECTIONS
    )
    return (
        HEAD.format(title="Watcher")
        + f"""<header>
  {lockup()}
  <p class="tagline">{TAGLINE}</p>
  <div class="zip-bar">
    <label for="zip">Zipcode</label>
    <input id="zip" type="text" inputmode="numeric" maxlength="5" placeholder="e.g. 90210" disabled>
    <button type="button" disabled>Watch</button>
    <span class="badge">Under construction</span>
  </div>
</header>
<main>
  <div class="cards">
{cards}
  </div>
</main>
<footer>
  <p class="couplet">{COUPLET[0]}<br>{COUPLET[1]}</p>
  <p>Watcher is under construction. Open this file locally in your browser.</p>
</footer>
"""
        + FOOT
    )


def main():
    (OUT / "index.html").write_text(index_page())
    for section in SECTIONS:
        (OUT / f"{section[0]}.html").write_text(section_page(*section))
    print(f"Wrote {len(SECTIONS) + 1} pages to {OUT}")


if __name__ == "__main__":
    main()
