import re

from ..base import Disclosure, parse_period
from ..parse import find_header, map_columns, num, parse_sheet, text, workbooks

AMC = "Sundaram Mutual Fund"
SLUG = "sundaram"
BASE = "https://www.sundarammutual.com"
API = BASE + "/ajax/Modules_Disclosure_Monthly_Fortnightly_Adhoc_Portfolios,App_Web_00rybqzs.ashx"
LINK = re.compile(r"href=\\?'([^'\\]+)\\?'[^>]*>(?:<i[^>]*></i>)?([^<]+)</a>")


def list_disclosures(session):
    r = session.post(f"{API}?_method=GetCategory&_session=no", data={"Catid": "Monthly"}, timeout=120)
    seen = set()
    for href, label in LINK.findall(r.text):
        period = parse_period(label)
        if period and href not in seen and re.search(r"\.xlsx?$", href, re.I):
            seen.add(href)
            yield Disclosure(amc=SLUG, period=period, url=BASE + href, scheme=label.split(" - ")[0].replace("Monthly Portfolio Disclosure", "").strip())


JUNK_RE = re.compile(r"^(index|scheme riskometer|back to index|\(.*\))$", re.I)

LEAD_RE = re.compile(r"^[+*#\s]+(?=(grand|total|sub[\s-]*total)\b)", re.I)
SKIP_RE = re.compile(r"^(annexure|xdo_metadata)", re.I)
FUT_RE = re.compile(r"\bfut\b|\bfutures?\b", re.I)
DERIV_RE = re.compile(r"^\W*(\w\W+)?derivatives?\b", re.I)


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            if SKIP_RE.match(sheet):
                continue
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            hi = find_header(rows)
            if hi is None:
                continue
            # Navigation and descriptor cells above the header would otherwise be taken as the scheme name
            rows = [[("" if isinstance(c, str) and JUNK_RE.match(c.strip()) else c) for c in r] for r in rows[:hi]] + [[LEAD_RE.sub("", c) if isinstance(c, str) else c for c in r] for r in rows[hi:]]
            label_rows(rows, hi)
            out.extend(parse_sheet(rows, sheet, amc=amc, period=period, source=source))
    return out


def label_rows(rows, hi):
    cols = map_columns(rows, hi)[0]
    nj, pj, label = cols.get("name"), cols.get("pct_nav"), ""
    if nj is None or pj is None:
        return
    for r in rows[hi + 1:]:
        if nj < len(r) and text(r[nj]) and (pj >= len(r) or num(r[pj]) is None):
            label = text(r[nj])
        elif nj < len(r) and not text(r[nj]) and pj < len(r) and (num(r[pj]) or 0) != 0 and re.search(r"repo|cblo|treps", label, re.I) and not text(r[cols["isin"]] if cols["isin"] < len(r) else ""):
            r[nj] = label
