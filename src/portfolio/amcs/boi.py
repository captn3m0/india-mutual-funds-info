import json
import re

from ..base import Disclosure, is_sheet, parse_date, parse_period

AMC = "Bank of India Mutual Fund"
SLUG = "boi"
API = "https://www.boimf.in/AjaxService.asmx/GetDocuments"


def list_disclosures(session):
    body = {"pagno": 1, "category": None, "fromDate": None, "toDate": None,
            "LibraryName": "InvestorCorner", "folderName": "MONTHLY PORTFOLIO", "CategoryValue": "no"}
    r = session.post(API, json=body, timeout=120)
    r.raise_for_status()
    seen = set()
    # the endpoint ignores pagno and returns every document in one response
    for doc in json.loads(r.json()["d"]).get("Documents") or []:
        url = doc["FolderUrl"]
        bare = url.split("?")[0]
        label = doc["DocName"] + " " + bare.rsplit("/", 1)[-1]
        d = parse_date(label)
        period = parse_period(doc["DocName"]) or parse_period(bare.rsplit("/", 1)[-1])
        # mid-month (fortnightly) files carry a day before the 28th
        if (d and d.day < 28) or "fortnight" in label.lower():
            continue
        key = (period, re.sub(r"[^a-z0-9]", "", bare.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()))
        if period and is_sheet(bare) and key not in seen:
            seen.add(key)
            yield Disclosure(amc=SLUG, period=period, url=url)
