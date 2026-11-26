import re

from ..base import Disclosure, is_sheet, parse_date, parse_period
from ..parse import find_header, parse_sheet, text, workbooks

AMC = "Kotak Mahindra Mutual Fund"
SLUG = "kotak"
IMPERSONATE = "chrome"
API = "https://www.kotakmf.com/api/kotakapi/forms/user/v1/getsubheaderList/417"
FILES = "https://vatseelabs-s3.kotakmf.com/"
# Option 51 holds the consolidated and fortnightly workbooks; other options are overseas FoF top-10 sheets
CONSOLIDATED = 51


def list_disclosures(session):
    r = session.get(API, timeout=60)
    r.raise_for_status()
    found, fallback = {}, {}
    for row in r.json()["subHeaderList"]:
        title = (row.get("subHeaderTitle") or "").replace("Febuary", "February")
        path = row.get("content") or ""
        low = title.lower()
        if row.get("optionId") != CONSOLIDATED or not is_sheet(path) or "debt schemes" in low:
            continue
        period = parse_period(title)
        if not period:
            continue
        if low.startswith("fortnightly"):
            d = parse_date(title)
            if d and d.day >= 28:
                fallback.setdefault(period, path)
        else:
            found.setdefault(period, path)
    for period, path in sorted({**fallback, **found}.items(), reverse=True):
        yield Disclosure(amc=SLUG, period=period, url=FILES + path, filename=f"{period}_{path.rsplit('/', 1)[-1]}")


def realign(rows):
    """Move names and section labels into the column left of ISIN, where headers and data disagree."""
    hi = find_header(rows)
    if hi is None:
        return rows
    k = next(j for j, c in enumerate(rows[hi]) if re.match(r"isin", text(c), re.I))
    if k < 1:
        return rows
    out = [list(r) for r in rows]
    head = out[hi]
    j = next((j for j, c in enumerate(head[:k]) if re.search(r"name|instrument", text(c), re.I)), None)
    if j is not None and j != k - 1:
        head[k - 1], head[j] = head[j], head[k - 1]
    for r in out[hi + 1:]:
        if len(r) >= k and not text(r[k - 1]):
            i = next((i for i, c in enumerate(r[:k - 1]) if text(c)), None)
            if i is not None:
                r[k - 1], r[i] = r[i], ""
    return out


def titled(rows):
    """Rewrite 'Portfolio of X as on D' as a scheme-name line the shared parser recognises."""
    for r in rows[:6]:
        for i, c in enumerate(r):
            m = re.match(r"portfolio (?:of|for)\s+(.+)", text(c), re.I)
            if m:
                r[i] = f"Scheme Name: {m.group(1)}"
                return True
    return False


def holding(h):
    """False for derivative disclosure tables, numbered notes and footnote-only subtotal rows."""
    section = h.section.strip()
    return not (section.lower().startswith("underlying") or re.fullmatch(r"\d+\.?", section)
                or not re.search(r"[A-Za-z0-9]", h.name))


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = realign(wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False))
            if not titled(rows) and re.search(r"note|common|yield", sheet, re.I):
                continue
            hs = parse_sheet(rows, sheet, amc=amc, period=period, source=source)
            out.extend(h for h in hs if holding(h))
    return out
