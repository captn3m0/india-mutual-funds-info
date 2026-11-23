from ..base import MONTHS, Disclosure, parse_period
from ..parse import parse_sheet, workbooks

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
            out.extend(parse_sheet(rows, sheet, amc=amc, period=period, source=source))
    return out
