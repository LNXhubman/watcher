# Watcher

Watcher is an agent that collects local government activity for a given zipcode.

- **Jurisdiction levels:** activity is organized by city, county, state and federal. A zipcode resolves to the governing body at each level.
- **Schedule:** the agent runs once a day.
- **Reporting:** weekly reports are built from the daily collections, tracking specific information according to user-defined interests (to be defined).
- **History:** past results are kept and reported in an easy-to-read, standard format.

## Status

Early development. Built so far:

- SQLite storage with deduplication and change detection (`watcher/db.py`, `watcher/schema.sql`).
- Zipcode lookup from free Census data: cities, counties, state, congressional and legislative districts.
- Federal Register collector (no key needed).
- California legislature collector via Open States, skipped until `OPENSTATES_API_KEY` is set (not yet verified against the live API).
- Weekly report (Markdown and HTML) and a dark-theme front page with level tabs and a word cloud.

Not built yet: interests and LLM scoring, the daily scheduler, county and city collectors, alerts, report history.

## Usage

Requires Python 3.11 or newer and no third-party packages. Settings are in `config.toml` (zipcode, models, daily cost cap).

```
python3 -m watcher lookup          # find the governments for the configured zipcode
python3 -m watcher confirm "Sunnyvale city"   # choose which places to watch
python3 -m watcher run             # collect, then build the weekly report
python3 build_site.py              # regenerate the HTML pages
python3 -m unittest discover -s tests -t .    # run the tests
```

Open `index.html` in a browser after a run. Runtime data goes in `data/` and `reports/`, which are not committed.

## Planned features

- Source registry: per-jurisdiction data sources (agendas and minutes, legislation feeds, permit and zoning portals, court dockets, public notices) with their scrape or API method.
- Zipcode to jurisdiction mapping, including special districts (school boards, water districts).
- Item types: meetings, agenda items, votes, ordinances and bills, budgets, permits and rezoning, elections and ballot measures, public comment deadlines.
- Deduplication and change detection: store only new or changed items and flag amendments.
- Source links and citations for every item.
- Upcoming calendar: look ahead at meetings and comment deadlines.
- Interest matching: keyword, topic and location matches, plus LLM relevance scoring and short summaries.
- Alerts: immediate notification for high-priority matches.
- Run health: log failures, flag broken or stale sources, retry.
- Multiple zipcodes, each with its own interests.
- Report formats: Markdown or HTML weekly reports, searchable history, optional digest per level.
- Storage: SQLite to start, with raw documents archived for re-parsing.

## License

Released under the MIT License.

```
MIT License

Copyright (c) 2026 thinker

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
