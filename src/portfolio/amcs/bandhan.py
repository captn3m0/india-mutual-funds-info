import re

from ..base import MONTHS, Disclosure, parse_date, parse_period
from ..parse import SCHEME_HINT, Holding, find_header, num, parse_sheet, text, workbooks

AMC = "Bandhan Mutual Fund"
SLUG = "bandhan"
API = "https://cmsnew.bandhanmutual.com/wp-json/finance-api/v1/posts/monthly-portfolio?bypass_pagination=true"


def list_disclosures(session):
    r = session.get(API, timeout=120)
    r.raise_for_status()
    seen = set()
    for post in r.json()["data"]:
        year = post["acf_fields"].get("financial_year") or ""
        for f in post["acf_fields"].get("disclosure_files") or []:
            link = f.get("document_link")
            if not link or not link.get("url") or link["url"] in seen:
                continue
            seen.add(link["url"])
            name = f.get("document_name") or ""
            period = parse_period(link["filename"]) or parse_period(name)
            if not period and f.get("month") and year.isdigit():
                period = f"{year}-{MONTHS[f['month'].lower()]:02d}"
            if period:
                yield Disclosure(amc=SLUG, period=period, url=link["url"], scheme=name)


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            # The "INDEX" back-link cell is mistaken for the scheme name
            rows = [["" if str(c).strip() == "INDEX" else c for c in r] for r in rows[:15]] + rows[15:]
            if find_header(rows) is None:
                out.extend(_summary(rows, sheet, amc=amc, period=period, source=source))
            else:
                out.extend(parse_sheet(rows, sheet, amc=amc, period=period, source=source))
    return out


def _summary(rows, sheet, **common):
    """Older files list only names and weights, with no ISIN column."""
    for hi, row in enumerate(rows[:15]):
        cells = [text(c).lower() for c in row]
        ni = next((j for j, c in enumerate(cells) if c in ("name", "company")), None)
        if ni is not None:
            break
    else:
        return []
    pi = next((j for j in range(ni + 1, len(cells)) if re.search(r"total|nav", cells[j])), None)
    if pi is None:
        return []
    top = [text(c) for r in rows[:hi] for c in r if text(c)]
    scheme = next((t for t in top if SCHEME_HINT.search(t) and not re.match(r"portfolio|net assets", t, re.I)), sheet)
    as_on = next((d for d in map(parse_date, top) if d), "")
    out = []
    for row in rows[hi + 1:]:
        name, pct = text(row[ni]) if ni < len(row) else "", num(row[pi]) if pi < len(row) else None
        if name.lower().startswith("grand total"):
            break
        if not name or pct is None or name.lower().endswith(" total"):
            continue
        rating = text(row[ni + 1]) if pi > ni + 1 else ""
        out.append(Holding(as_on=str(as_on), scheme=re.sub(r"\s*\(\d.*$", "", scheme), sheet=sheet,
                           name=name, industry_rating=rating, pct_nav=round(pct * 100, 6), **common))
    # Top-holdings sheets and ones with unlabelled subtotals are not full portfolios
    return out if 95 <= sum(h.pct_nav for h in out) <= 105 else []
