import calendar
import datetime
import time

from ..base import Disclosure, links

AMC = "SBI Mutual Fund"
SLUG = "sbi"
API = "https://www.sbimf.com/ajaxcall/CMS/GetSchemePortfolioSheets"
HEADERS = {"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json;charset=utf-8"}


def list_disclosures(session):
    today = datetime.date.today()
    for year in range(2010, today.year + 1):
        for month in range(1, 13):
            if (year, month) > (today.year, today.month):
                break
            period = f"{year}-{month:02d}"
            body = f'{{"FundId":0,"PSYear":"{year}","PSMonth":"{calendar.month_name[month]}","PSFrequency":"Monthly"}}'
            r = session.post(API, data=body, headers=HEADERS, timeout=60)
            time.sleep(0.3)
            if r.status_code != 200:
                continue
            found = [(u, t) for u, t in links(r.text, API) if "/scheme-portfolios/" in u and "download" not in t.lower()]
            found = list({u: (u, t) for u, t in found}.values())
            # Prefer the consolidated workbook; fall back to per-scheme files
            allsch = [x for x in found if "all scheme" in x[1].lower()]
            if allsch:
                yield Disclosure(amc=SLUG, period=period, url=allsch[0][0])
                continue
            for u, t in found:
                yield Disclosure(amc=SLUG, period=period, url=u, scheme=t)


def parse(path, amc="", period=""):
    from ..parse import parse_file

    # Old sheets carry subtotal rows such as "Money Market Instruments Total"
    return [h for h in parse_file(path, amc=amc, period=period) if not h.name.strip().lower().endswith("total")]
