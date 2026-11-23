import json
import re

from ..base import MONTHS, Disclosure

AMC = "360 ONE Mutual Fund"
SLUG = "360one"
PAGE = "https://www.360.one/asset/mutual-funds/downloads/"
GROUP = re.compile(r'\{"year":"Monthly Portfolio (\d{4})","monthlyData":')


def list_disclosures(session):
    r = session.get(PAGE, timeout=60)
    r.raise_for_status()
    html = r.text.replace('\\"', '"')
    dec = json.JSONDecoder()
    seen = set()
    for m in GROUP.finditer(html):
        block, _ = dec.raw_decode(html[m.start():])
        for month in block["monthlyData"]:
            for group in month["documentGroups"]:
                for doc in group["documents"]:
                    url = doc["fileUrl"].strip()
                    name = doc["fileName"].strip().lower()
                    mon = MONTHS.get(name) or MONTHS.get(str(month["month"]).lower())
                    if not mon or url in seen or not re.search(r"\.xlsx?$", url, re.I):
                        continue
                    seen.add(url)
                    yield Disclosure(amc=SLUG, period=f"{m.group(1)}-{mon:02d}", url=url)
