import re
import time

from ..base import MONTHS, Disclosure
from ..parse import parse_sheet, text, workbooks

AMC = "UTI Mutual Fund"
SLUG = "uti"
SITE = "https://www.utimf.com"
KEY = "consolidate-all-portfolio-disclosure"


def _filters(node):
    if isinstance(node, dict):
        if node.get("document_category_key") == KEY:
            yield from node["filters"]
        else:
            for v in node.values():
                yield from _filters(v)
    elif isinstance(node, list):
        for v in node:
            yield from _filters(v)


def _rank(d):
    m = re.search(r"(\d{8})-(\d{6})", d.filename)
    if not m:
        return ("", d.filename)
    # 20180407 is the bulk migration stamp, so fall back to the name
    return (m[1], d.filename if m[1] == "20180407" else m[2])


def list_disclosures(session):
    best = {}
    for d in _scan(session):
        if re.match(r"(futexposure|div_rate)", d.filename, re.I):
            continue
        # Re-uploads of a month appear as extra rows; keep the newest
        if d.period not in best or _rank(d) > _rank(best[d.period]):
            best[d.period] = d
    yield from best.values()


def _scan(session):
    cfg = session.get(f"{SITE}/api/page/forms-and-downloads-downloads", timeout=60).json()
    seen = set()
    for f in _filters(cfg):
        for ym in f.get("filter_year_month") or []:
            for month in ym["months"]:
                url = f"{SITE}/api/get-consolidate-portfolio-disclosure"
                r = session.get(url, params={"year": ym["year"], "month": month}, timeout=60)
                time.sleep(0.3)
                if r.status_code != 200:
                    continue
                for row in r.json().get("rows", []):
                    link = row.get("url") or row.get("doc")
                    period = f"{int(ym['year']):04d}-{MONTHS[month.lower()]:02d}"
                    if link and (period, link) not in seen:
                        seen.add((period, link))
                        name = link.split("?")[0].rsplit("/", 1)[-1]
                        yield Disclosure(amc=SLUG, period=period, url=link, filename=name)


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        base = member.rsplit("/", 1)[-1]
        if member and not re.search(r"expos", base, re.I) or re.match(r"(fut|div)", base, re.I):
            continue
        rows = []
        for sheet in wb.sheet_names:
            rows += wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
        # One long sheet holds every scheme; each block starts at its SCHEME: line
        starts = [i for i, r in enumerate(rows) if r and re.match(r"scheme\s*:", text(r[0]), re.I)]
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for a, b in zip(starts, starts[1:] + [len(rows)]):
            name = re.sub(r"^scheme\s*:\s*", "", text(rows[a][0]), flags=re.I)
            block = rows[a:b]
            for k, r in enumerate(block):
                if r and re.match(r"name of the security", text(r[0]), re.I):
                    block = block[:k]
                    break
            out += parse_sheet(block, name or "scheme", amc=amc, period=period, source=source)
    return out
