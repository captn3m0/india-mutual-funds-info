import calendar
import datetime
import re

from ..base import Disclosure, links, parse_period
from ..parse import parse_file

AMC = "IL&FS Mutual Fund"
SLUG = "ilfs"
SITE = "https://www.ilfsinfrafund.com"
PAGES = ["other.html", "financials.html"]


def _period(label, name):
    # Labels end with the upload date, so read the month-year at the front first
    head = re.split(r"portfolio", label, maxsplit=1, flags=re.I)[0]
    return parse_period(head) or parse_period(label) or parse_period(name)


def list_disclosures(session):
    best = {}
    for page in PAGES:
        html = session.get(f"{SITE}/{page}", timeout=60).text
        for url, label in links(html, f"{SITE}/{page}"):
            name = url.rsplit("/", 1)[-1]
            text = f"{label} {name}"
            if not re.search(r"\.xlsx?$", name, re.I) or not re.search(r"portfolio", text, re.I):
                continue
            if re.search(r"half.?yearly|dashboard.report.r1|^\d+ ?\w+ ?-?\d{4}.*\bportfolio -", text, re.I):
                continue
            period = _period(label, name)
            if period:
                best.setdefault(period, []).append((url, text))
    for period, items in best.items():
        # Several workbooks can cover one month; keep the combined report
        pick = next((u for u, t in items if re.search(r"transaction|fortnightly|nav", t, re.I)), items[0][0])
        yield Disclosure(amc=SLUG, period=period, url=pick)


def parse(path, amc="", period=""):
    rows = parse_file(path, amc=amc, period=period)
    keep = []
    for h in rows:
        if re.search(r"dash|transaction|annex|complaint", h.sheet, re.I):
            continue
        try:
            d = datetime.date.fromisoformat(h.as_on)
        except ValueError:
            continue
        # Workbooks also carry fortnightly (15th) sheets
        if d.day == calendar.monthrange(d.year, d.month)[1]:
            keep.append(h)
    return keep
