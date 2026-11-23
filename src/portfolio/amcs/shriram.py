import re

from ..base import Disclosure, parse_period

AMC = "Shriram Mutual Fund"
SLUG = "shriram"
INDEX = "https://www.shriramamc.in/investor-statutory-disclosures"
_URL = re.compile(r"https://cdn\.shriramamc\.in/[^\"\\\s<>]*Monthly-Portfolio-for-the-Financial-Year/[^\"\\\s<>]+\.xlsx?", re.I)


def list_disclosures(session):
    html = session.get(INDEX, timeout=120).text.replace("\\/", "/")
    for url in sorted(set(_URL.findall(html))):
        name = url.rsplit("/", 1)[-1]
        if re.match(r"Quarter", name):
            continue
        period = parse_period(name.replace("Febuary", "February"))
        if period:
            yield Disclosure(amc=SLUG, period=period, url=url)


def parse(path, amc="", period=""):
    from ..parse import SCHEME_HINT, find_header, parse_sheet, workbooks, text

    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = [list(r) for r in wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)]
            hi = find_header(rows)
            if hi is None:
                continue
            # Coupon column header collides with "%" matching; multi-scheme index row confuses scheme name
            rows[hi] = ["" if "coupon" in text(c).lower() else c for c in rows[hi]]
            nc = next((j for j, c in enumerate(rows[hi]) if "name of" in text(c).lower()), None)
            for row in rows[hi + 1:]:
                if nc and not text(row[nc]) and not text(row[0]):
                    lab = next((c for c in row[:nc] if text(c)), "")
                    if lab:
                        row[nc] = lab
            for i in range(hi):
                if sum(1 for c in rows[i] if SCHEME_HINT.search(text(c))) > 1:
                    rows[i] = []
            out.extend(parse_sheet(rows, sheet, amc=amc, period=period, source=source))
    return out
