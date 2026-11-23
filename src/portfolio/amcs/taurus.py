import re
import time

from ..base import Disclosure, is_sheet, parse_period
from urllib.parse import urljoin

AMC = "Taurus Mutual Fund"
SLUG = "taurus"
PAGE = "https://www.taurusmutualfund.com/monthly-portfolio"
_A = re.compile(r"<a\s+href=\s*[\"']\s*([^\"']+?\.(?:xlsx?|zip))\s*[\"'][^>]*>.*?<span>(.*?)</span>", re.S)


def _options(html, name):
    sel = re.search(rf'<select[^>]*name="{name}".*?</select>', html, re.S).group(0)
    return re.findall(r'<option\s+value="(\d+)"[^>]*>\s*([^<]+?)\s*</option>', sel)


def list_disclosures(session):
    html = session.get(PAGE, timeout=60).text
    years = _options(html, "field_monthly_portfolio_target_id")
    months = _options(html, "field_month_target_id")
    seen = set()
    for yid, year in years:
        for mid, month in months:
            params = {"field_monthly_portfolio_target_id": yid, "field_month_target_id": mid}
            page = session.get(PAGE, params=params, timeout=60).text
            time.sleep(0.3)
            for href, label in _A.findall(page):
                url = urljoin(PAGE, href)
                if not is_sheet(url) or url in seen:
                    continue
                seen.add(url)
                period = parse_period(f"{month} {year}")
                yield Disclosure(amc=SLUG, period=period, url=url, scheme=" ".join(label.split()))
