import re
from urllib.parse import unquote

from ..base import MONTHS, Disclosure, links, parse_date, parse_period

AMC = "Nippon India Mutual Fund"
SLUG = "nippon"
INDEX = "https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures"
SKIP = re.compile(r"(?<!\d)15(th)?[-. ]|fort|fornight|risk-?param|weblink|factsheet|portfolio-final|Riskometer-Jan-22|Debt-Portfolio-Nov-21", re.I)
MONTH_ONLY = re.compile(r"(?<![a-z])(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")(?![a-z])", re.I)


def shift(period, n):
    y, m = map(int, period.split("-"))
    k = y * 12 + m - 1 + n
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


def list_disclosures(session):
    html = session.get(INDEX, timeout=60).text
    seen, prev = set(), None
    # Page lists newest first; undated names borrow the month from their neighbour
    for url, _ in links(html, INDEX):
        if "/FactsheetsDocuments/" not in url or not re.search(r"\.xlsx?$", url, re.I):
            continue
        name = unquote(url.rsplit("/", 1)[-1])
        if url in seen or not re.search(r"portfolio", name, re.I):
            continue
        seen.add(url)
        if SKIP.search(name):
            continue
        d = parse_date(name)
        if d and d.day == 15:
            continue
        period = parse_period(name)
        if not period and prev:
            m = MONTH_ONLY.search(name)
            if m:
                period = shift(prev, 0)
                while int(period[5:]) != MONTHS[m.group(1).lower()]:
                    period = shift(period, -1)
            else:
                period = shift(prev, -1)
        if period:
            prev = period
            yield Disclosure(amc=SLUG, period=period, url=url)
