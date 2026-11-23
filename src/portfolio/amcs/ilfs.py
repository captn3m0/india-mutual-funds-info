import calendar
import datetime
import re

from ..base import Disclosure, links, parse_period
from ..parse import parse_sheet, text, workbooks

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
        pick = next((u for u, t in items if re.search(r"transaction|fortnightly|nav", t, re.I)), items[0][0])
        yield Disclosure(amc=SLUG, period=period, url=pick)


TITLE = re.compile(r"^(?:IL\d+\s*-\s*)?IL&FS\s+(?:IDF|Infrastructure\s+Debt\s+Fund)\s*-?\s*Series\s*(\d[A-C])\s*$", re.I)
SKIP = re.compile(r"dash|transaction|annex|complaint|note", re.I)


def norm(t):
    return " ".join(t.split())


def blocks(rows):
    idx = [i for i, r in enumerate(rows) if any(TITLE.match(norm(text(c))) for c in r)
           and any("name of" in text(c).lower() for r2 in rows[i + 1:i + 5] for c in r2)]
    if not idx:
        return [("", rows)]
    out = []
    for k, i in enumerate(idx):
        end = idx[k + 1] if k + 1 < len(idx) else len(rows)
        title = next(norm(text(c)) for c in rows[i] if TITLE.match(norm(text(c))))
        out.append(("IL&FS Infrastructure Debt Fund - Series " + TITLE.match(title).group(1).upper(), rows[:idx[0]] + rows[i:end]))
    return out


def refit(group):
    tot = sum(h.market_value_lakh or 0 for h in group)
    if tot <= 0 or 95 <= sum(h.pct_nav or 0 for h in group) <= 105:
        return
    fix = {}
    for h in group:
        if h.market_value_lakh is None or h.pct_nav is None:
            continue
        e = h.market_value_lakh / tot * 100
        if abs(h.pct_nav - e) > 1 and abs(h.pct_nav * 100 - e) <= 1:
            fix[id(h)] = h.pct_nav * 100
    if 95 <= sum(fix.get(id(h), h.pct_nav or 0) for h in group) <= 105:
        for h in group:
            h.pct_nav = fix.get(id(h), h.pct_nav)


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            if SKIP.search(sheet):
                continue
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            for title, part in blocks(rows):
                hs = [h for h in parse_sheet(part, sheet, amc=amc, period=period, source=source) if not h.name.lower().startswith("undrawn")]
                if not any(h.pct_nav for h in hs):
                    continue
                m = re.search(r"\b(\d[A-C])\b", sheet)
                name = title or (f"IL&FS Infrastructure Debt Fund - Series {m.group(1)}" if m else hs[0].scheme)
                for h in hs:
                    h.scheme = name
                refit(hs)
                out.extend(hs)
    dates = {}
    for h in out:
        dates.setdefault(h.scheme, set()).add(h.as_on)
    first, keep = {}, []
    for h in out:
        if len(dates[h.scheme]) > 1 and period and h.as_on[:7] != period:
            continue
        if first.setdefault((h.scheme, h.as_on), h.sheet) != h.sheet:
            continue
        try:
            d = datetime.date.fromisoformat(h.as_on)
        except ValueError:
            continue
        if d.day == calendar.monthrange(d.year, d.month)[1]:
            keep.append(h)
    return keep
