import re
from urllib.parse import quote

from ..base import Disclosure, is_sheet, parse_period

AMC = "Motilal Oswal Mutual Fund"
SLUG = "motilal"
BASE = "https://www.motilaloswalmf.com"
API = BASE + "/content/aem-cloud-dept-backend-motilal-oswal/api/search-documents.json"
SKIP = re.compile(r"fort\w*night|performance|hy.?portfolio|half.?year", re.I)


def list_disclosures(session):
    seen = set()
    for year in range(2012, 2028):
        r = session.get(API, params={"year": year, "category": "", "month": "", "type": "mf"}, timeout=120)
        for doc in r.json().get("results", []):
            path = doc["path"]
            title = (doc.get("title") or "").strip()
            if doc["category"] != "month end portfolio" or path in seen or not is_sheet(path):
                continue
            if SKIP.search(title) or SKIP.search(path.rsplit("/", 1)[-1]):
                continue
            seen.add(path)
            name = path.rsplit("/", 1)[-1]
            period = parse_period(title) or parse_period(name)
            if period:
                yield Disclosure(amc=SLUG, period=period, url=BASE + quote(path))
