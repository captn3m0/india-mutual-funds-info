import argparse
import collections
import csv
import datetime
import hashlib
import os
import sys
import time

from .amcs import registry
from .base import month_end, session
from .parse import FIELDS, parse_file

RAW = "raw"
MANIFEST = "portfolio/manifest"
HOLDINGS = "portfolio/holdings"
MANIFEST_FIELDS = ["period", "filename", "url", "scheme", "sha256", "size", "fetched"]


def read_manifest(slug):
    path = f"{MANIFEST}/{slug}.csv"
    if not os.path.exists(path):
        return {}
    with open(path, newline="") as f:
        return {(r["period"], r["filename"]): r for r in csv.DictReader(f)}


def write_manifest(slug, rows):
    os.makedirs(MANIFEST, exist_ok=True)
    with open(f"{MANIFEST}/{slug}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        w.writeheader()
        for key in sorted(rows):
            w.writerow(rows[key])


def raw_path(d):
    return f"{RAW}/{d.amc}/{d.period}/{d.filename}"


def download(s, d):
    r = s.request(d.method, d.url, headers=d.headers, data=d.data, timeout=180)
    r.raise_for_status()
    body = r.content
    if len(body) < 512 or body[:1] == b"<" and b"<html" in body[:2048].lower():
        raise ValueError(f"not a spreadsheet ({len(body)} bytes)")
    path = raw_path(d)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(body)
    return body


def select(mod, args, s):
    items = list(mod.list_disclosures(s))
    if args.since:
        items = [d for d in items if d.period >= args.since]
    if args.until:
        items = [d for d in items if d.period <= args.until]
    items.sort(key=lambda d: (d.period, d.filename), reverse=True)
    if args.periods:
        keep = sorted({d.period for d in items}, reverse=True)[: args.periods]
        items = [d for d in items if d.period in keep]
    return items


def cmd_list(mod, args, s):
    items = select(mod, args, s)
    for d in items:
        print(d.period, d.filename, d.url, d.scheme, sep="\t")
    periods = sorted({d.period for d in items})
    span = f"{periods[0]}..{periods[-1]}" if periods else "none"
    print(f"# {mod.SLUG}: {len(items)} files, {len(periods)} periods, {span}", file=sys.stderr)


def cmd_fetch(mod, args, s):
    manifest = {} if args.no_manifest else read_manifest(mod.SLUG)
    failed = 0
    for d in select(mod, args, s):
        key = (d.period, d.filename)
        if key in manifest and not args.force:
            continue
        try:
            body = download(s, d)
        except Exception as e:
            failed += 1
            print(f"FAIL {d.period} {d.url}: {e}", file=sys.stderr)
            continue
        manifest[key] = {
            "period": d.period, "filename": d.filename, "url": d.url, "scheme": d.scheme,
            "sha256": hashlib.sha256(body).hexdigest(), "size": len(body),
            "fetched": datetime.date.today().isoformat(),
        }
        print(f"OK   {d.period} {d.filename} {len(body)}")
        time.sleep(args.delay)
    if not args.no_manifest:
        write_manifest(mod.SLUG, manifest)
    return 1 if failed else 0


def raw_files(slug):
    for period in sorted(os.listdir(f"{RAW}/{slug}")):
        pdir = f"{RAW}/{slug}/{period}"
        if os.path.isdir(pdir):
            for name in sorted(os.listdir(pdir)):
                yield period, f"{pdir}/{name}"


def cmd_parse(mod, args, s):
    parser = getattr(mod, "parse", parse_file)
    by_period = collections.defaultdict(list)
    for period, path in raw_files(mod.SLUG):
        try:
            rows = parser(path, amc=mod.SLUG, period=period)
            for h in rows:
                h.as_on = h.as_on or month_end(period).isoformat()
            by_period[period].extend(rows)
        except Exception as e:
            print(f"FAIL {path}: {e}", file=sys.stderr)
    for period, rows in by_period.items():
        if args.check:
            check(period, rows, args.verbose)
            continue
        os.makedirs(f"{HOLDINGS}/{mod.SLUG}", exist_ok=True)
        with open(f"{HOLDINGS}/{mod.SLUG}/{period}.csv", "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(FIELDS)
            w.writerows(h.row() for h in rows)
        print(f"{mod.SLUG} {period}: {len(rows)} holdings")


def check(period, rows, verbose):
    """Summarise parsed schemes; flag those whose % of NAV is not ~100."""
    groups = collections.defaultdict(list)
    for h in rows:
        groups[(h.source, h.sheet)].append(h)
    bad = 0
    for (source, sheet), hs in groups.items():
        pct = sum(h.pct_nav or 0 for h in hs)
        isins = sum(1 for h in hs if h.isin)
        ok = 98 <= pct <= 102 and hs[0].as_on
        bad += not ok
        if verbose or not ok:
            print(f"{period} {hs[0].as_on or '?':10} n={len(hs):4} isin={isins:4} pct={pct:7.2f} "
                  f"{source[-30:]}|{sheet[:20]} {hs[0].scheme[:50]}{'' if ok else '  <-- CHECK'}")
    print(f"# {period}: {len(groups)} schemes, {len(rows)} holdings, {bad} flagged")


def main():
    p = argparse.ArgumentParser(prog="portfolio")
    p.add_argument("command", choices=["amcs", "list", "fetch", "parse"])
    p.add_argument("amc", nargs="*", help="AMC slugs (default: all)")
    p.add_argument("--since", help="earliest period, YYYY-MM")
    p.add_argument("--until", help="latest period, YYYY-MM")
    p.add_argument("--periods", type=int, help="only the N most recent periods")
    p.add_argument("--force", action="store_true", help="re-download known files")
    p.add_argument("--no-manifest", action="store_true", help="do not read or write manifests")
    p.add_argument("--check", action="store_true", help="parse: print a summary, write nothing")
    p.add_argument("--verbose", action="store_true", help="check: print every scheme")
    p.add_argument("--delay", type=float, default=0.5, help="seconds between downloads")
    args = p.parse_args()

    mods = registry()
    if args.command == "amcs":
        for slug, mod in mods.items():
            print(slug, mod.AMC, sep="\t")
        return 0
    rc = 0
    for slug in args.amc or mods:
        try:
            s = session(getattr(mods[slug], "IMPERSONATE", None))
            rc |= globals()[f"cmd_{args.command}"](mods[slug], args, s) or 0
        except Exception as e:
            rc = 1
            print(f"ERROR {slug}: {e!r}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
