import html
import re
import time

from ..base import Disclosure, is_sheet, parse_period

AMC = "Baroda BNP Paribas Mutual Fund"
SLUG = "barodabnp"
IMPERSONATE = "chrome"
SITE = "https://www.barodabnpparibasmf.in/"
# Live listing since the 2022 merger, then the pre-merger BNP Paribas and Baroda archives
SOURCES = [
    ("downloads/monthly-portfolio-scheme", "ajax-load-more-documents"),
    ("archivedownload/monthly-portfolio-scheme", "archive-ajax-load-more-documents"),
    ("baroda-archivedownload/monthly-portfolio-scheme", "baroda-archive-ajax-load-more-documents"),
]
ITEMS = [
    re.compile(r'file-name">\s*<a href="([^"]+)"[^>]*>([^<]*)</a>'),
    re.compile(r'<a href="([^"]+)"[^>]*class="excelLink">\s*<div class="left">\s*<span>[^<]*</span>\s*<p>([^<]*)</p>'),
]
DOC = re.compile(r"/view-document/(\d+)$")
ARCHIVE = SITE + "assetsarchive/baroda_download_documents/"
MISLINKED = {
    ARCHIVE + "BMF%20Factsheet%20Apr2020.xls": ARCHIVE + "BMF_Factsheet_Apr2020.xls",
    ARCHIVE + "Baroda_Factsheet_Nov_2016.xls": ARCHIVE + "Factsheet%20Nov%2716.xls",
}


def hidden(page, name):
    m = re.search(rf'name="{name}"[^>]*value="([^"]*)"', page)
    return m.group(1) if m else ""


def items(session, path, ajax):
    page = session.get(SITE + path, timeout=60).text
    csrf, category = hidden(page, "csrf_test_name"), hidden(page, "category")
    if not csrf:
        raise RuntimeError(f"{path} has no CSRF token ({len(page)} bytes, likely blocked)")
    for year in re.findall(r'class="onptionMenu[^"]*" id="(\d{4})"', page):
        cnt, pagination, remaining = "0", "0", "0"
        while True:
            time.sleep(0.5)
            data = dict(csrf_test_name=csrf, cnt=cnt, pagination=pagination, send_category=category,
                        send_year=year, remaining_cnt=remaining)
            r = session.post(SITE + ajax, data=data, timeout=60)
            r.raise_for_status()
            body = r.json()
            for item in ITEMS:
                for url, title in item.findall(body.get("data") or ""):
                    yield url, html.unescape(title).strip()
            if body.get("status") != "Y":
                break
            cnt, pagination, remaining = str(body["total_row"]), str(body["pagination"]), str(body["remaining_cnt"])


def list_disclosures(session):
    found = {}
    for path, ajax in SOURCES:
        for url, title in items(session, path, ajax):
            url = MISLINKED.get(url, url)
            if not (is_sheet(url) or DOC.search(url)) or re.search(r"fortnight|mid[- ]?month", title + url, re.I):
                continue
            period = parse_period(title) or parse_period(url.rsplit("/", 1)[-1])
            if period:
                found.setdefault(url, (period, title))
    whole = {p for p, t in found.values() if "all funds" in t.lower()}
    for url, (period, title) in found.items():
        consolidated = "all funds" in title.lower()
        if period in whole and not consolidated:
            continue
        doc = DOC.search(url)
        name = f"{re.sub(r'[^A-Za-z0-9]+', '_', title).strip('_')}_{doc[1]}.xls" if doc else ""
        yield Disclosure(amc=SLUG, period=period, url=url, filename=name, scheme="" if consolidated else title)
