import json
import re
import time

from ..base import Disclosure, parse_period

AMC = "The Wealth Company Mutual Fund"
SLUG = "wealthcompany"
SITE = "https://www.wealthcompanyamc.in"
PAGE = SITE + "/literature-forms/portfolio-documents/monthly/"
SCHEME = re.compile(r"monthly\s*-\s*(.*?)\s*-\s*[A-Za-z]+\s+\d", re.I)


def _items(html):
    # Rows are embedded in the Next.js flight payload as escaped JSON objects
    html = html.replace('\\"', '"').replace("\\\\n", " ")
    dec = json.JSONDecoder()
    for m in re.finditer(r'\{"uploadDate"', html):
        try:
            obj, _ = dec.raw_decode(html, m.start())
        except ValueError:
            continue
        if obj.get("attachment", {}).get("url"):
            yield obj


def list_disclosures(session):
    best, page, pages = {}, 1, 1
    while page <= pages:
        r = session.get(PAGE, params={"limit": 100, "page": page}, timeout=90)
        r.raise_for_status()
        pages = max([int(x) for x in re.findall(r'"pageCount\\?":(\d+)', r.text)] or [1])
        for o in _items(r.text):
            name = " ".join(o["name"].split())
            m = SCHEME.match(name)
            scheme = m.group(1) if m else ""
            period = parse_period(name) or o["uploadDate"][:7]
            key = (scheme or name, period)
            if key not in best or o["createdAt"] > best[key][0]:
                best[key] = (o["createdAt"], o["attachment"]["url"], scheme)
        page += 1
        time.sleep(0.5)
    for (_, period), (_, url, scheme) in best.items():
        yield Disclosure(amc=SLUG, period=period, url=SITE + url if url.startswith("/") else url, scheme=scheme)
