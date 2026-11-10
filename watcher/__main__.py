"""Command line: python3 -m watcher {collect,report,run,lookup,jurisdictions,confirm,unconfirm}."""
import argparse
from datetime import date

from watcher import collect, config, db, lookup, report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="watcher")
    parser.add_argument("command", choices=["collect", "report", "run", "lookup", "jurisdictions", "confirm", "unconfirm"],
                        help="collect = fetch sources; report = build the weekly report; run = both; "
                             "lookup = find the governments for the configured zipcode; jurisdictions = list them; "
                             "confirm/unconfirm NAME... = choose which to watch")
    parser.add_argument("names", nargs="*", help="exact jurisdiction names for confirm/unconfirm")
    parser.add_argument("--days", type=int, default=7, help="how many days back to collect (default 7)")
    parser.add_argument("--end", type=date.fromisoformat, default=None, help="report week ends on this date (default today)")
    parser.add_argument("--config", default=str(config.DEFAULT_PATH))
    args = parser.parse_args(argv)

    cfg = config.load(args.config)
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    root = cfg.data_dir.parent
    if args.command == "lookup":
        lookup.save(conn, cfg.zipcode, lookup.resolve(cfg.zipcode))
    if args.command in ("confirm", "unconfirm"):
        missing = lookup.set_confirmed(conn, cfg.zipcode, args.names, args.command == "confirm")
        if missing:
            parser.error("not found for this zipcode: " + ", ".join(missing))
    if args.command in ("lookup", "jurisdictions", "confirm", "unconfirm"):
        print(f"Governments for {cfg.zipcode} (watching = yes):")
        for r in lookup.linked(conn, cfg.zipcode):
            share = f"{r['share']:.0%}" if r["share"] is not None else ""
            print(f"  {'yes' if r['confirmed'] else 'no ':3}  {r['level']:8} {r['name']:45} {share}")
        return
    if args.command in ("collect", "run"):
        result = collect.run(conn, days=args.days)
        print(f"collect: {result['status']}, {result['new']} new, {result['changed']} changed, {result['unchanged']} unchanged")
    if args.command in ("report", "run"):
        rep = report.build(conn, args.end or date.today())
        paths = report.write(conn, rep, root, cfg.data_dir)
        print(f"report {rep['iso_week']}: {paths['html']}")


if __name__ == "__main__":
    main()
