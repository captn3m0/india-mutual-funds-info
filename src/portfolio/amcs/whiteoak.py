import datetime
import time

from ..base import Disclosure, parse_period

AMC = "WhiteOak Capital Mutual Fund"
SLUG = "whiteoak"
IMPERSONATE = "chrome"
API = "https://cms.whiteoakamc.com/api/"
FILE = "populate[{0}][fields][0]=ext&populate[{0}][fields][1]=url&"
# Pre-Sep-2021 months exist only as consolidated workbooks in the generic disclosures list
FIRST_PER_SCHEME = "2021-09"


def pages(session, route, query, key):
    page = 1
    while True:
        time.sleep(0.3)
        r = session.get(f"{API}{route}?{FILE.format(key)}{query}&pagination[pageSize]=100&pagination[page]={page}", timeout=60)
        r.raise_for_status()
        body = r.json()
        yield from body["data"]
        if page >= body["meta"]["pagination"]["pageCount"]:
            return
        page += 1


def period_of(title, published):
    found = parse_period(title or "")
    if found:
        return found
    if published:
        p = datetime.date.fromisoformat(published[:10]).replace(day=1) - datetime.timedelta(days=1)
        return f"{p.year:04d}-{p.month:02d}"


def file_url(a, key):
    data = (a.get(key) or {}).get("data") or {}
    return (data.get("attributes") or {}).get("url")


def list_disclosures(session):
    seen = set()
    q = "filters[period][$eq]=Monthly&fields[0]=scheme_name&fields[1]=doc_name&fields[2]=published_date"
    for row in pages(session, "scheme-portfolios", q, "doc_file"):
        a = row["attributes"]
        url = file_url(a, "doc_file") or a.get("doc_link")
        period = period_of(a["doc_name"], a["published_date"])
        if not url or not period or url in seen or not url.lower().split("?")[0].endswith((".xls", ".xlsx", ".zip")):
            continue
        seen.add(url)
        yield Disclosure(amc=SLUG, period=period, url=url, scheme=(a["scheme_name"] or "").strip())
    q = "filters[disclosure_category][slug][$eq]=monthly_portfolio&fields[0]=title&fields[1]=applicable_date"
    for row in pages(session, "regulatory-disclosures", q, "disclosure_media_file"):
        a = row["attributes"]
        url = file_url(a, "disclosure_media_file")
        period = period_of(a["title"], a["applicable_date"])
        if url and period and period < FIRST_PER_SCHEME and url not in seen:
            seen.add(url)
            yield Disclosure(amc=SLUG, period=period, url=url)
