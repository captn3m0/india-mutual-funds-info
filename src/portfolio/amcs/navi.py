import calendar
import html
import re
import time
from urllib.parse import unquote

from ..base import Disclosure, parse_period

AMC = "Navi Mutual Fund"
SLUG = "navi"
IMPERSONATE = "chrome"
PAGE = "https://navi.com/mutual-fund/downloads/portfolio/"
API = "https://navi.com/wp-json/nv/v1/documents"
MONTHLY = "884"


def list_disclosures(session):
    page = session.get(PAGE, timeout=60).text
    nonce = re.search(r'"rest_url":"[^"]+","nonce":"([0-9a-f]+)"', page)
    if not nonce:
        raise RuntimeError(f"portfolio page has no REST nonce ({len(page)} bytes, likely blocked)")
    block = page[page.find(f'data-category="{MONTHLY}"'):]
    years = re.findall(r'<option[^>]*value="(\d{4}-\d{4})"', block.split("</select>")[0])
    headers = {"WP-NONCE": nonce.group(1), "Referer": PAGE}
    seen = set()
    for fy in sorted(years, reverse=True):
        start = int(fy[:4])
        for month in range(1, 13):
            time.sleep(1)
            data = {"financial_year": fy, "value": calendar.month_name[month], "category": MONTHLY, "type": "Monthly", "order": "DESC"}
            r = session.post(API, data=data, headers=headers, timeout=60)
            if r.status_code != 200:
                continue
            for doc in r.json().get("data") or []:
                urls = doc["url"] if isinstance(doc["url"], list) else [{"link": doc["url"]}]
                for u in urls:
                    url = html.unescape(u.get("link") or "")
                    name = unquote(url.rsplit("/", 1)[-1])
                    # 2022-2025 files are xlsx served without an extension
                    bare = "." not in name
                    if url in seen or not (bare or re.search(r"\.xlsx?$", name, re.I)):
                        continue
                    seen.add(url)
                    title = html.unescape(doc.get("title") or "")
                    period = parse_period(title) or f"{start if month >= 4 else start + 1}-{month:02d}"
                    yield Disclosure(amc=SLUG, period=period, url=url, filename=name + ".xlsx" if bare else name,
                                     scheme=re.sub(r"\s+\d{1,2}(st|nd|rd|th)\b.*$", "", title))
