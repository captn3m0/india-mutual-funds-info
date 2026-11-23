import json
import re

from ..base import Disclosure, parse_period
from ..parse import END_RE, SUBSECTION_RE, TOTAL_RE, find_header, map_columns, text

AMC = "Groww Mutual Fund"
SLUG = "groww"
PAGE = "https://www.growwmf.in/statutory-disclosure/portfolio"


def _files(node):
    for f in node.get("files", []):
        yield f
    for sub in node.get("folders", []):
        yield from _files(sub)


def list_disclosures(session):
    html = session.get(PAGE, timeout=60).text
    data = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S).group(1))
    root = data["props"]["pageProps"]["filesData"]
    seen = {}
    for folder in root["folders"]:
        if folder["name"].strip().lower() != "portfolio":
            continue
        for f in _files(folder):
            if not re.match(r"mon\w*\s+portfolio", f["name"], re.I):
                continue
            period = parse_period(f["name"])
            if period:
                seen[period] = f
    for period, f in seen.items():
        ext = f["name"].rsplit(".", 1)[-1].lower()
        yield Disclosure(amc=SLUG, period=period, url=f["publicUrl"], filename=f"monthly_portfolio_{period}.{ext}")


def parse(path, amc="", period=""):
    from ..parse import parse_sheet, workbooks

    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            fix(rows)
            out.extend(parse_sheet(rows, sheet, amc=amc, period=period, source=source))
    return out


def fix(rows):
    # Percent cells are fractions of 1 except sometimes in the derivatives block, which defeats the generic rescale
    hi = find_header(rows)
    if hi is None:
        return
    cols = map_columns(rows, hi)[0]
    nj, pj = cols.get("name", max(cols["isin"] - 1, 0)), cols.get("pct_nav")
    if pj is None:
        return
    main, der, body, in_d = [], [], [], False
    for r in rows[hi + 1:]:
        name = text(r[nj]) if nj < len(r) else ""
        v = r[pj] if pj < len(r) else None
        if not isinstance(v, float):
            if name and v in ("", None) and not SUBSECTION_RE.match(name):
                in_d = bool(re.search(r"deriv|futur", name, re.I))
            continue
        if END_RE.match(name):
            break
        if TOTAL_RE.match(name):
            continue
        (der if in_d else main).append(v)
        body.append((r, in_d))
    if not main:
        return
    m, d = sum(main), sum(der)
    da, db = abs(m + d - 1), abs(m + d / 100 - 1)
    if min(da, db) > 0.06:
        return
    for r, in_d in body:
        if da <= db or not in_d:
            r[pj] = r[pj] * 100
