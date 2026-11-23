import re

from ..base import Disclosure, month_end, parse_period
from ..parse import parse_sheet, text, workbooks

AMC = "Zerodha CASE Mutual Fund"
SLUG = "zerodha"
INDEX = "https://www.zerodhafundhouse.com/resources/disclosures/"
FILE = re.compile(r'"url":"(https://assets\.zerodhafundhouse\.com/statutory-reports/portfolio-disclosures/[^"]+)"')
NAME = re.compile(r"\s*([A-Z0-9]+)\s*-?\s*Monthly Portfolio\s*-?\s*(.*)\.xlsx?$", re.I)


def list_disclosures(session):
    page = session.get(INDEX, timeout=60).text
    seen = set()
    for url in FILE.findall(page):
        m = NAME.match(url.rsplit("/", 1)[-1])
        period = m and parse_period(m.group(2))
        if period and (m.group(1), period) not in seen:
            seen.add((m.group(1), period))
            yield Disclosure(amc=SLUG, period=period, url=url, scheme=m.group(1))


TITLE = re.compile(r"STATEMENT OF (.+?)(?: FOR)? ([A-Za-z]+\.? ?\d{4})$", re.I)


def parse(path, amc="", period=""):
    out = []
    for _, wb in workbooks(path):
        for sheet in wb.sheet_names:
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            hs = parse_sheet(rows, sheet, amc=amc, period=period, source=path.rsplit("/", 1)[-1])
            for row in rows[:15]:
                m = next(filter(None, (TITLE.search(text(c)) for c in row)), None)
                if m:
                    p = parse_period(m.group(2)) or period
                    for h in hs:
                        h.scheme, h.as_on = m.group(1).title(), str(month_end(p))
                    break
            out.extend(hs)
    return out
