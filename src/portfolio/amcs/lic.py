import re
import time
from urllib.parse import quote, unquote

from ..base import Disclosure, links, parse_date
from ..parse import parse_file

AMC = "LIC Mutual Fund"
SLUG = "lic"
BASE = "https://www.licmf.com/downloads/"
MONTHLY = "639"


def options(session, path, **data):
    html = session.post(BASE + path, data=data, timeout=60).text
    return [v for v in re.findall(r"<option value='(\d+)'", html)]


def list_disclosures(session):
    for year in options(session, "consolidated-portfolio-filters", id=MONTHLY, filter="year"):
        for month in options(session, "consolidated-portfolio-filters", id=MONTHLY, filter="month", year=year):
            html = session.post(
                BASE + "consolidated-portfolio-files", data={"id": MONTHLY, "month": month, "year": year}, timeout=60
            ).text
            time.sleep(0.2)
            seen = set()
            for url, label in links(html, BASE):
                if url in seen or not re.search(r"\.xlsx?$", url, re.I):
                    continue
                seen.add(url)
                d = parse_date(label)
                period = f"{d.year}-{d.month:02d}" if d else f"{int(year)}-{int(month):02d}"
                yield Disclosure(amc=SLUG, period=period, url=quote(url, safe=":/%"), filename=unquote(url.rsplit("/", 1)[-1]))


def parse(path, amc="", period=""):
    out = parse_file(path, amc=amc, period=period)
    groups = {}
    for h in out:
        groups.setdefault((h.source, h.sheet), []).append(h)
    # A scheme holding ~100% in one line escapes the fraction heuristic
    for hs in groups.values():
        pcts = [h.pct_nav or 0 for h in hs]
        if 0.97 <= sum(pcts) <= 1.03 and max(map(abs, pcts)) <= 1.1:
            for h in hs:
                if h.pct_nav is not None:
                    h.pct_nav = round(h.pct_nav * 100, 6)
    return out
