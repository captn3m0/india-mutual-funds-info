import html as htmllib
import json
import re
import time

from ..base import MONTHS, Disclosure, links, parse_date

AMC = "Bajaj Finserv Mutual Fund"
SLUG = "bajaj"
IMPERSONATE = "chrome"
PAGE = "https://www.bajajamc.com/downloads?statutory-disclosure="
SECTION = "757"


def list_disclosures(session):
    page = session.get(PAGE, timeout=60).text
    cfg = json.loads(re.search(r"var bajajDownloads = (\{.*?\});", page).group(1))

    def call(**data):
        r = session.post(cfg["ajaxUrl"], data={"nonce": cfg["nonce"], **data}, timeout=60)
        time.sleep(0.2)
        return r.json()["data"]

    seen = set()
    for fy in call(action="bajaj_get_filter_options", filter_for="years", section_id=SECTION)["options"]:
        opts = call(action="bajaj_get_filter_options", filter_for="months", section_id=SECTION, year=fy["value"])
        for month in opts["options"]:
            body = call(action="bajaj_get_downloads", section_id=SECTION, year=fy["value"], month=month["value"])
            for url, _ in links(body["html"], PAGE):
                if url in seen or not re.search(r"\.(xlsx?|zip)$", url, re.I):
                    continue
                seen.add(url)
                title = htmllib.unescape(re.sub(r"<[^>]+>", " ", body["html"]))
                d = parse_date(url.rsplit("/", 1)[-1]) or parse_date(title)
                if d is None:
                    start = int(fy["value"][:4])
                    mon = MONTHS[month["value"].lower()]
                    period = f"{start if mon >= 4 else start + 1}-{mon:02d}"
                else:
                    period = f"{d.year}-{d.month:02d}"
                yield Disclosure(amc=SLUG, period=period, url=url)
