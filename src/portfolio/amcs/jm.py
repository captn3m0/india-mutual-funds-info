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
RENAMED = {
    "Template Portfolio Disclosure - March 20188 - Hybrid.xls": "Template Portfolio Disclosure - March 2018 - Hybrid.xls",
    "Template Portfolio Disclosure - March 20188 - Equity.xls": "Template Portfolio Disclosure - March 2018 - Equity.xls",
    "Template Portfolio Disclosure - March 20188 - Derivative.xls":
        "Template Portfolio Disclosure - March 2018 - Derivative.xls",
    "PortfolioDisclosure28022014.xls": "Portfolio Disclosure - 28.02.2014.xls",
    "Template Portfolio Disclosure - 30.06.2015555-EQUITY.xls": "Portfolio Disclosure - 30.06.2015-EQUITY.xls",
    "Portfolio Disclosure - 30.06.2015-HYBRID.xls": "Portfolio Disclosure - 30.06.20015-HYBRID2.xls",
    "Portfolio Disclosure - 30.06.2015-DEBT.xls": "Template Portfolio Disclosure - 30.06.2015-DEBT.xls",
}
GONE = {"March 2018 port..xlsx"}


def _previous_month(date):
    y, m = int(date[:4]), int(date[5:7])
    return f"{y - (m == 1):04d}-{(m - 2) % 12 + 1:02d}"


def list_disclosures(session):
    r = session.post(API, json=QUERY, timeout=120)
    r.raise_for_status()
    seen = set()
    for f in json.loads(aes_cbc(KEY, IV, r.json()["data"])):
        folder, _, name = f["FileName"].rpartition("/")
        name = RENAMED.get(name, name)
        url = BASE + quote(f"{folder}/{name}")
        if not is_sheet(url) or url in seen or name in GONE:
            continue
        seen.add(url)
        # Files are uploaded the month after; fall back on that when the title has no date
        period = parse_period(f["Title"]) or parse_period(name) or _previous_month(f["DocumentDate"])
        scheme = re.search(r"JM .*?(Fund|Plan|Scheme)\b", f["Title"])
        yield Disclosure(amc=SLUG, period=period, url=url, filename=name, scheme=scheme.group(0) if scheme else "")
