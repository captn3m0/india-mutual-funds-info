import calendar
import datetime
import json
import re
import time

from ..base import Disclosure, parse_date
from ..parse import parse_file

AMC = "Jio BlackRock Mutual Fund"
SLUG = "jioblackrock"
BASE = "https://www.jioblackrockamc.com"
PAGE = BASE + "/statutory-disclosure/disclosures/monthly-portfolio-disclosure"
# Next.js server action id for getDisclosureL3Data; re-discovered from the page chunk when possible
ACTION = "7057edaeb87814854cbb16ef3b74ad43707e7b26df"
CHUNK = re.compile(r"/_next/static/chunks/app/[^\"\\ ]*statutory-disclosure[^\"\\ ]*\.js")
ACTION_RE = re.compile(r'createServerReference\)\("([0-9a-f]{40,})"[^)]*"getDisclosureL3Data"')


def action_id(session):
    try:
        html = session.get(PAGE, timeout=60).text
        for path in CHUNK.findall(html):
            m = ACTION_RE.search(session.get(BASE + path, timeout=60).text)
            if m:
                return m.group(1)
    except Exception:
        pass
    return ACTION


def fetch(session, action, year, month):
    headers = {"Next-Action": action, "Content-Type": "text/plain;charset=UTF-8", "Accept": "text/x-component"}
    body = json.dumps(["monthly-portfolio-disclosure", {"year": year, "month": month}, "MF"])
    r = session.post(PAGE, headers=headers, data=body, timeout=60)
    r.raise_for_status()
    for line in r.text.splitlines():
        if line.startswith("1:"):
            return json.loads(line[2:]).get("data") or []
    return []


def period_of(item):
    d = parse_date(item["title"])
    if not d:
        d = datetime.date.fromisoformat(item["date"])
    return f"{d.year}-{d.month:02d}"


def list_disclosures(session):
    action = action_id(session)
    this_year = datetime.date.today().year
    items = {}
    for start in range(2024, this_year + 1):
        for month in list(calendar.month_name)[1:]:
            for it in fetch(session, action, f"FI{start}-{start + 1}", month):
                f = it.get("file") or {}
                if f.get("url") and f.get("ext", "").lower() in (".xls", ".xlsx"):
                    items[f["url"]] = it
            time.sleep(0.2)
    by_period = {}
    for url, it in items.items():
        by_period.setdefault(period_of(it), []).append((url, it))
    for period, rows in by_period.items():
        cons = [r for r in rows if re.search(r"mutual[\s-]fund-?\s*monthly", r[1]["title"], re.I)]
        for url, it in cons or rows:
            scheme = "" if cons else re.sub(r"(?i)[\s-]*monthly[\s-]*portfolio.*$", "", it["title"])
            name = f"{it['uid'] or 'portfolio'}-{period}{it['file']['ext']}"
            yield Disclosure(amc=SLUG, period=period, url=url, filename=name, scheme=scheme)


HEADING = re.compile(r"^(debt instruments|money market instruments|equity( &| and)? equity related)$", re.I)


def parse(path, amc="", period=""):
    return [h for h in parse_file(path, amc=amc, period=period) if h.isin or not HEADING.match(h.name.strip())]
