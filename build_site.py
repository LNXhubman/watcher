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

# data/site-data.js is written by `python3 -m watcher report`; it may not exist yet, so pages must cope.
DATA_SCRIPT = '<script src="data/site-data.js"></script>'

REPORT_JS = """<script>
(function () {
  var d = window.WATCHER_DATA;
  if (!d) return;
  var PAGE = 25;
  document.querySelector(".intro").textContent += " Report " + d.iso_week + ": " + d.start + " to " + d.end + ".";

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  Object.keys(d.levels).forEach(function (level) {
    var data = d.levels[level];
    var tab = document.querySelector('.tabs button[data-level="' + level + '"]');
    if (tab) tab.textContent += " (" + data.total + ")";
    var card = document.querySelector('.level[data-level="' + level + '"]');
    if (!card || !data.total) return;
    if (!window.WATCHER_START) window.WATCHER_START = level;
    var summary = card.querySelector(".placeholder");
    summary.textContent = data.total + " items this week. Click a word to filter the list.";
    summary.className = "count";

    var cloud = el("div", "cloud"), chip = el("p", "filter"), list = el("ul", "items"), more = el("button", "more");
    chip.hidden = true;
    card.appendChild(cloud); card.appendChild(chip); card.appendChild(list); card.appendChild(more);
    var state = { word: null, limit: PAGE };

    var counts = data.words.map(function (w) { return w[1]; });
    var lo = Math.min.apply(null, counts), hi = Math.max.apply(null, counts);
    var buttons = {};
    data.words.slice().sort().forEach(function (w) {
      var b = el("button", "word", w[0]);
      b.type = "button";
      b.title = w[1] + " items";
      b.style.fontSize = (0.95 + 1.8 * (w[1] - lo) / ((hi - lo) || 1)).toFixed(2) + "rem";
      b.addEventListener("click", function () {
        state.word = state.word === w[0] ? null : w[0];
        state.limit = PAGE;
        draw();
      });
      buttons[w[0]] = b;
      cloud.appendChild(b);
    });
    if (!data.words.length) cloud.hidden = true;
    more.addEventListener("click", function () { state.limit += PAGE; draw(); });

    function draw() {
      var items = data.items.filter(function (it) {
        return !state.word || it.title.toLowerCase().split(/[^a-z'-]+/).indexOf(state.word) !== -1;
      });
      Object.keys(buttons).forEach(function (w) { buttons[w].setAttribute("aria-pressed", String(w === state.word)); });
      chip.hidden = !state.word;
      chip.textContent = "";
      if (state.word) {
        chip.appendChild(document.createTextNode(items.length + " items with \u201c" + state.word + "\u201d "));
        var clear = el("button", "clear", "Clear filter");
        clear.type = "button";
        clear.addEventListener("click", function () { state.word = null; state.limit = PAGE; draw(); });
        chip.appendChild(clear);
      }
      list.textContent = "";
      items.slice(0, state.limit).forEach(function (it) {
        var li = el("li");
        var a = el("a", null, it.title);
        a.href = it.url;
        li.appendChild(a);
        li.appendChild(el("span", "meta", (it.changed ? "changed" : it.type.replace("_", " ")) + ", " + it.date));
        list.appendChild(li);
      });
      var left = items.length - state.limit;
      more.hidden = left <= 0;
      more.textContent = "Show " + Math.min(PAGE, left) + " more (" + left + " left)";
    }
    draw();
  });
})();
</script>
"""

TABS_JS = """<script>
(function () {
  var tabs = [].slice.call(document.querySelectorAll(".tabs button"));
  var cards = [].slice.call(document.querySelectorAll(".level"));
  function select(level) {
    tabs.forEach(function (b) { b.setAttribute("aria-selected", String(b.dataset.level === level)); });
    cards.forEach(function (c) { c.hidden = c.dataset.level !== level; });
  }
  tabs.forEach(function (b) {
    b.addEventListener("click", function () {
      select(b.dataset.level);
      history.replaceState(null, "", "#" + b.dataset.level);
    });
  });
  var want = location.hash.slice(1);
  var known = tabs.some(function (b) { return b.dataset.level === want; });
  select(known ? want : (window.WATCHER_START || "city"));
})();
</script>
"""

INDEX_JS = """<script>
(function () {
  var d = window.WATCHER_DATA;
  if (!d) return;
  var total = 0;
  Object.keys(d.levels).forEach(function (k) { total += d.levels[k].total; });
  var el = document.getElementById("latest");
  el.textContent = "Latest report " + d.iso_week + ": " + total + " items collected. Last run: " + d.last_run_status + ".";
})();
</script>
"""


def nav(current):
    links = ['<a href="index.html">Home</a>']
    for slug, text, _, _ in SECTIONS:
        mark = ' aria-current="page"' if slug == current else ""
        links.append(f'<a href="{slug}.html"{mark}>{text}</a>')
    return '<nav aria-label="Sections">' + "".join(links) + "</nav>"


def tabs():
    return "\n".join(
        f'    <button type="button" role="tab" data-level="{name.lower()}" aria-selected="false">{name}</button>'
        for name, _ in LEVELS
    )


def level_cards(placeholder):
    return "\n".join(
        f"""    <div class="level" data-level="{name.lower()}">
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
  <div class="tabs" role="tablist" aria-label="Level of government">
{tabs()}
  </div>
  <div class="levels">
{level_cards(placeholder)}
  </div>
</main>
<footer><p>Watcher is under construction.</p></footer>
"""
        + (DATA_SCRIPT + "\n" + REPORT_JS if slug == "report" else "")
        + TABS_JS
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
  <p class="tagline" id="latest"></p>
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
        + DATA_SCRIPT + "\n" + INDEX_JS
        + FOOT
    )


def main():
    (OUT / "index.html").write_text(index_page())
    for section in SECTIONS:
        (OUT / f"{section[0]}.html").write_text(section_page(*section))
    print(f"Wrote {len(SECTIONS) + 1} pages to {OUT}")


if __name__ == "__main__":
    main()
