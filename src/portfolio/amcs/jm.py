import json
import re
from urllib.parse import quote

from ..base import Disclosure, aes_cbc, is_sheet, parse_period

AMC = "JM Financial Mutual Fund"
SLUG = "jm"
API = "https://jmmfapi.jmfinancialmf.com/api/GetDownloadNew"
BASE = "https://www.jmfinancialmf.com/"
# Category 2 / sub-category 4 is "Monthly Portfolio of Schemes"
QUERY = {"IICategoryID": "2", "IISubCategoryID": "4", "IVsearch": ""}
# Responses are AES-wrapped with REACT_APP_AES_KEY / REACT_APP_AES_IV from the site's main.js
KEY, IV = b"6fa979f20126cb08aa645a8f495f6d85", b"I8zyA4lVhMCaJ5Kg"


def _previous_month(date):
    y, m = int(date[:4]), int(date[5:7])
    return f"{y - (m == 1):04d}-{(m - 2) % 12 + 1:02d}"


def list_disclosures(session):
    r = session.post(API, json=QUERY, timeout=120)
    r.raise_for_status()
    seen = set()
    for f in json.loads(aes_cbc(KEY, IV, r.json()["data"])):
        url = BASE + quote(f["FileName"])
        if not is_sheet(url) or url in seen:
            continue
        seen.add(url)
        name = f["FileName"].rsplit("/", 1)[-1]
        # Files are uploaded the month after; fall back on that when the title has no date
        period = parse_period(f["Title"]) or parse_period(name) or _previous_month(f["DocumentDate"])
        scheme = re.search(r"JM .*?(Fund|Plan|Scheme)\b", f["Title"])
        yield Disclosure(amc=SLUG, period=period, url=url, filename=name, scheme=scheme.group(0) if scheme else "")
