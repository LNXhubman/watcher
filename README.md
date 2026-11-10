# Watcher

Watcher is an agent that collects local government activity for a given zipcode.

- **Jurisdiction levels:** activity is organized by city, county, state and federal. A zipcode resolves to the governing body at each level.
- **Schedule:** the agent runs once a day.
- **Reporting:** weekly reports are built from the daily collections, tracking specific information according to user-defined interests (to be defined).
- **History:** past results are kept and reported in an easy-to-read, standard format.

## Status

New project, no code yet. Nothing below is implemented.

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

MIT
