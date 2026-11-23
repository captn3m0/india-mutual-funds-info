import re

from ..base import Disclosure, is_sheet, links, parse_period

AMC = "Unifi Mutual Fund"
SLUG = "unifi"
INDEX = "https://www.unifimf.com/statutory/"
BOX = re.compile(r'<a href="([^"]+)"[^>]*>.*?<span>([^<]*)</span>', re.S)


def list_disclosures(session):
    html = session.get(INDEX, timeout=60).text
    start = html.index("<h3>Monthly Portfolio Disclosure")
    seg = html[start : html.index("<h3>Half Yearly Portfolio Disclosure", start)]
    names = [re.sub(r"\s+", " ", n).strip() for n in re.findall(r'role="tab"[^>]*>([^<]*)</a>', seg)]
    panels = seg.split('class="tab_citem"')[1:]
    seen = set()
    for scheme, panel in zip(names, panels):
        for href, label in BOX.findall(panel):
            url = links(f'<a href="{href}">x</a>', INDEX)[0][0]
            period = parse_period(label) or parse_period(url.rsplit("/", 1)[-1])
            if is_sheet(url) and period and url not in seen:
                seen.add(url)
                yield Disclosure(amc=SLUG, period=period, url=url, scheme=scheme)
