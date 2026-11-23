import json
import time

from ..base import Disclosure, aes_cbc, is_sheet, parse_period

AMC = "ITI Mutual Fund"
SLUG = "iti"
API = "https://itiamc.com/jeeth/api/v1/catalog/getPartnerDocumentByType"
# Request and response bodies are AES-wrapped with constants from the site's main.js
KEY, IV = b"aar6tzij8o1snaar", b"0123456789ABCDEF"


def list_disclosures(session):
    body = {"type": "Disclosure", "guid": "0" * 32, "timeStamp": int(time.time() * 1000)}
    r = session.post(API, json={"eData": aes_cbc(KEY, IV, json.dumps(body), decrypt=False)}, timeout=120)
    r.raise_for_status()
    data = json.loads(aes_cbc(KEY, IV, r.json()["eData"]))
    seen = set()
    for tab in data["data"]["typeList"]:
        if tab["subType"] != "Portfolio Disclosures":
            continue
        for topic in tab["subTypesList"]:
            if topic["topic"] != "Monthly":
                continue
            for f in topic["topicsList"]:
                url = f["url"]
                period = parse_period(f["fileName"]) or parse_period(url.rsplit("/", 1)[-1])
                if period and is_sheet(url) and url not in seen:
                    seen.add(url)
                    yield Disclosure(amc=SLUG, period=period, url=url)
