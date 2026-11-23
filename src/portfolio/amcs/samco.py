import re

from ..base import Disclosure, parse_period

AMC = "Samco Mutual Fund"
SLUG = "samco"
BASE = "https://www.samcomf.com"
CDN = "https://media.samcomf.com/scomamc/amc_documents/"
ROW = re.compile(r'<td data-th="Document Title">\s*(.*?)\s*</td>\s*<td data-th="Action">(.*?)</td>', re.S)


def list_disclosures(session):
    r = session.get(f"{BASE}/StatutoryDisclosure", timeout=120)
    r.raise_for_status()
    best = {}
    for title, actions in ROW.findall(r.text):
        m = re.search(r'href="(/amc-document-download/[^"]+)"', actions)
        if not m:
            continue
        url = CDN + m.group(1).rsplit("/", 1)[-1]
        name = m.group(1).rsplit("/", 1)[-1]
        label = title.replace("Apirl", "April")
        if not re.search(r"\.xlsx?$", name, re.I):
            continue
        # Month-end Overnight files are named "Monthly_Fortnightly"; 15th-of-month ones are skipped
        if not re.search(r"monthly", label, re.I) or re.search(r"half|hy_|overlap|dashboard", label, re.I):
            continue
        period = parse_period(label) or parse_period(name)
        if period:
            # Re-uploads carry a later timestamp suffix; keep only the newest per period and name
            key = (period, re.sub(r"_\d{9,}(?=\.\w+$)", "", name))
            if key not in best or name > best[key][0]:
                best[key] = (name, Disclosure(amc=SLUG, period=period, url=url, scheme=re.sub(r"\s+", " ", label)))
    for _, d in best.values():
        yield d
