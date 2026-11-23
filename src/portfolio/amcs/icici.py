import re
import time
from urllib.parse import quote

from ..base import Disclosure, parse_period
from ..parse import parse_file

AMC = "ICICI Prudential Mutual Fund"
SLUG = "icici"
HOST = "https://www.icicipruamc.com"
API = HOST + "/api/nms/v1/downloads/files"
CATEGORY = "26a073d7-08d2-4a95-95fa-f83a4ee51e40"
SKIP = re.compile(r"deviation|flexible income", re.I)
SCHEME = re.compile(r"monthly portfolio disclosure\s+([A-Za-z]+)\s+[A-Za-z]+\d\d\b", re.I)


def _files(session):
    for page in range(1, 100):
        body = {
            "categoryId": CATEGORY, "schemeCategory": "", "userType": "Investor",
            "fileType": "All", "page": str(page), "size": "50", "filter": [],
            "categoryName": "Monthly Portfolio Disclosures",
        }
        r = session.post(API, json=body, headers={"Referer": HOST + "/downloads/others/monthly-portfolio-disclosures"}, timeout=60)
        r.raise_for_status()
        data = (r.json().get("success") or {}).get("data") or {}
        yield from data.get("files") or []
        if not data.get("isNext"):
            return
        time.sleep(0.5)


def list_disclosures(session):
    rows = []
    for f in _files(session):
        title, path = f["title"]["text"], f["url"]
        if not re.search(r"\.(zip|xlsx?)$", path, re.I) or SKIP.search(title):
            continue
        if not re.match(r"monthly portfolio", title, re.I):
            continue
        period = parse_period(title)
        if period:
            rows.append((period, title, path))
    zipped = {p for p, _, u in rows if u.lower().endswith(".zip")}
    seen = set()
    for period, title, path in rows:
        if period in zipped and not path.lower().endswith(".zip"):
            continue
        if (period, path) in seen:
            continue
        seen.add((period, path))
        m = SCHEME.match(title)
        name = path.rsplit("/", 1)[-1]
        yield Disclosure(
            amc=SLUG, period=period, url=HOST + "/blob" + quote(path, safe="/()"),
            filename=name, scheme=m.group(1) if m and not path.lower().endswith(".zip") else "",
        )


def _drop_aggregates(rows):
    while True:
        kept = _drop_once(rows)
        if len(kept) == len(rows):
            return kept
        rows = kept


def _drop_once(rows):
    out = []
    for i, h in enumerate(rows):
        if not h.isin and h.quantity is None and h.pct_nav:
            acc = 0.0
            tail = rows[i + 1:i + 1500]
            shorts = sum(abs(n.pct_nav or 0) for n in tail if not n.isin and (n.quantity or 0) < 0)
            for nxt in tail:
                acc += nxt.pct_nav or 0.0
                if abs(acc - h.pct_nav) <= 1e-6 + abs(h.pct_nav) * 5e-3:
                    break
                if abs(acc) > abs(h.pct_nav) * 1.01 + shorts + 1e-6:
                    acc = None
                    break
            else:
                acc = None
            if acc is not None:
                continue
        out.append(h)
    return out


def parse(path, amc="", period=""):
    by_sheet = {}
    for h in parse_file(path, amc, period):
        by_sheet.setdefault((h.source, h.sheet), []).append(h)
    out = []
    for rows in by_sheet.values():
        rows = _drop_aggregates(rows)
        pcts = [abs(h.pct_nav) for h in rows if h.pct_nav is not None]
        if pcts and max(pcts) <= 1.05 and sum(pcts) <= 5:
            for h in rows:
                if h.pct_nav is not None:
                    h.pct_nav = round(h.pct_nav * 100, 6)
        out.extend(rows)
    return out
