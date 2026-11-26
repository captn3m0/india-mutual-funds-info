import csv
import glob
import io
import os
import re
import sqlite3
import subprocess
import sys

from .parse import FIELDS

HOLDINGS = "portfolio/holdings"
MANIFEST = "portfolio/manifest"

SCHEMA = """
CREATE TABLE schemes (scheme_id INTEGER PRIMARY KEY, amc TEXT, name TEXT, UNIQUE (amc, name));
CREATE TABLE holdings (
    scheme_id INTEGER REFERENCES schemes(scheme_id), period TEXT, as_on TEXT,
    section TEXT, subsection TEXT, name TEXT, isin TEXT, industry_rating TEXT,
    quantity REAL, market_value_lakh REAL, pct_nav REAL, ytm REAL);
CREATE TABLE files (amc TEXT, period TEXT, filename TEXT, url TEXT, scheme TEXT,
    sha256 TEXT, size INTEGER, fetched TEXT);
"""


def read_rows(path):
    """Rows of a holdings CSV, plain or zstd-compressed."""
    if path.endswith(".zst"):
        raw = subprocess.run(["zstd", "-dc", path], check=True, capture_output=True).stdout
        f = io.StringIO(raw.decode())
    else:
        f = open(path, newline="")
    with f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"bad header in {path}: {reader.fieldnames}")
        yield from reader


def merge(slug, previous, out):
    """Combine an AMC's earlier holdings with freshly parsed periods, new ones winning."""
    fresh = sorted(glob.glob(f"{HOLDINGS}/{slug}/*.csv"))
    periods = {os.path.basename(p)[:-4] for p in fresh}
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        kept = 0
        if previous and os.path.exists(previous):
            for row in read_rows(previous):
                if row["period"] not in periods:
                    w.writerow(row)
                    kept += 1
        added = 0
        for path in fresh:
            for row in read_rows(path):
                w.writerow(row)
                added += 1
    print(f"{slug}: kept {kept} rows, added {added} rows from {len(periods)} periods")


def number(v):
    return float(v) if v != "" else None


def scheme_key(amc, name):
    return amc, " ".join(re.findall(r"[a-z0-9]+", name.lower()))


def db(out, inputs):
    """Build the SQLite dataset from per-AMC holdings CSVs and the manifests."""
    if os.path.exists(out):
        os.remove(out)
    conn = sqlite3.connect(out)
    conn.executescript(SCHEMA)
    schemes, names = {}, {}
    for path in inputs:
        batch = []
        for r in read_rows(path):
            # Case and punctuation changes in a printed name keep the same scheme_id
            key = scheme_key(r["amc"], r["scheme"])
            if key not in schemes:
                schemes[key] = len(schemes) + 1
                names[key] = r["scheme"]
            batch.append((
                schemes[key], r["period"], r["as_on"], r["section"], r["subsection"], r["name"],
                r["isin"] or None, r["industry_rating"], number(r["quantity"]),
                number(r["market_value_lakh"]), number(r["pct_nav"]), number(r["ytm"]),
            ))
        conn.executemany("INSERT INTO holdings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", batch)
        print(f"{path}: {len(batch)} holdings")
    conn.executemany("INSERT INTO schemes VALUES (?,?,?)", [(i, k[0], names[k]) for k, i in schemes.items()])
    for path in sorted(glob.glob(f"{MANIFEST}/*.csv")):
        amc = os.path.basename(path)[:-4]
        with open(path, newline="") as f:
            conn.executemany(
                "INSERT INTO files VALUES (?,?,?,?,?,?,?,?)",
                [(amc, r["period"], r["filename"], r["url"], r["scheme"], r["sha256"],
                  r["size"], r["fetched"]) for r in csv.DictReader(f)],
            )
    conn.commit()
    conn.execute("VACUUM")
    conn.close()


def main(argv):
    if argv[:1] == ["merge"] and len(argv) == 4:
        merge(argv[1], argv[2], argv[3])
    elif argv[:1] == ["db"] and len(argv) >= 3:
        db(argv[1], argv[2:])
    else:
        print("usage: build merge <slug> <previous.csv[.zst]> <out.csv> | build db <out.db> <csv>...")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
