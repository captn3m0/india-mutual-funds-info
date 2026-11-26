import re
import time

from ..base import MONTHS, Disclosure

AMC = "Axis Mutual Fund"
SLUG = "axis"
IMPERSONATE = "chrome"
API = "https://www.axismf.com/cms/"
BODY = {"sdType": "yearMonthSchemeDocs", "sdID": "sdMonthSchemePortfolio"}
SHEET = (".xls", ".xlsx", ".xlsb", ".zip")


def call(session, path, headers, **extra):
    for attempt in range(4):
        time.sleep(0.3 + attempt * 3)
        r = session.post(API + path, json={**BODY, **extra}, headers=headers, timeout=60)
        if r.status_code < 500:
            break
    r.raise_for_status()
    return r.json().get("data") or {}


def is_monthly(doc):
    name = doc["documentName"].strip()
    if not doc["docuementURL"].lower().endswith(SHEET):
        return False
    return bool(re.search(r"monthly", name, re.I) or re.fullmatch(r"(\d\d-)?[A-Za-z]{3,9}", name) and name.split("-")[-1].lower() in MONTHS)


def disclosure(doc, period):
    name = doc["docuementURL"].split("?")[0].rsplit("/", 1)[-1]
    return Disclosure(amc=SLUG, period=period, url=doc["docuementURL"], filename=f"{period}_{name}")


def list_disclosures(session):
    token = session.post(API + "token", json={}, timeout=60).json()["data"]["token"]
    headers = {"Authorization": token}
    meta = call(session, "get-scheme-documents", headers)
    codes = list(dict.fromkeys(s["schemeCode"] for s in meta["schemeCategories"]))
    seen = set()
    for year in sorted(meta["years"]):
        for month in meta["months"]:
            period = f"{year}-{MONTHS[month.lower()]:02d}"
            docs = call(session, "get-scheme-documents", headers, year=year, month=month, schemeCode="Consolidated").get("documentList", [])
            hits = [d for d in docs if is_monthly(d)]
            sheets = [d for d in docs if d["docuementURL"].lower().endswith(SHEET)]
            if not hits and len(sheets) == len(docs) == 1:
                hits = sheets
            # Months without a consolidated workbook only have per-scheme files
            if not hits and docs:
                for code in codes[1:]:
                    hits += [d for d in call(session, "get-scheme-documents", headers, year=year, month=month, schemeCode=code).get("documentList", []) if is_monthly(d)]
            for d in hits:
                if d["docuementURL"] not in seen:
                    seen.add(d["docuementURL"])
                    yield disclosure(d, period)
