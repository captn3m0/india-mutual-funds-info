"""Edelweiss: encrypted statutory-menu API (ECDH + AES-GCM session), monthly portfolio workbooks."""

import base64
import json
import re
import uuid
from urllib.parse import quote

from ..base import MONTHS, Disclosure, parse_period
from ..parse import parse_sheet, text, workbooks

AMC = "Edelweiss Mutual Fund"
SLUG = "edelweiss"
IMPERSONATE = "chrome"
SITE = "https://www.edelweissmf.com"
API = "https://api.edelweissmf.com/edelweissmf/api/v1/"
HEADERS = {"Origin": SITE, "Referer": SITE + "/"}
EXTRAS = re.compile(r"allocation|detailed investment", re.I)
SUBTOTAL = re.compile(r"(equity & equity related|debt instruments|money market instruments|others)$", re.I)
REVERSED = re.compile(r"derivatives\s*\(\s*reversed positions\s*\)", re.I)


def open_session(s):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    r = s.post(API + "analytics/init", json={"clientPublickey": base64.b64encode(pub).decode()}, headers=HEADERS, timeout=60)
    r.raise_for_status()
    j = r.json()
    server = serialization.load_der_public_key(base64.b64decode(j["serverPublicKey"]))
    secret = key.exchange(ec.ECDH(), server)
    aes = AESGCM(HKDF(hashes.SHA256(), 32, base64.b64decode(j["salt"]), b"aes-session-key").derive(secret))

    def get(path, **params):
        h = {**HEADERS, "x-app-context": j["sessionId"], "x-request-id": str(uuid.uuid4())}
        r = s.get(API + path, params=params, headers=h, timeout=60)
        r.raise_for_status()
        body = r.json()
        if "cipherText" in body:
            blob = base64.b64decode(body["cipherText"]) + base64.b64decode(body["authTag"])
            return json.loads(aes.decrypt(base64.b64decode(body["iv"]), blob, None))
        return body

    return get


def period_of(f):
    if f["filePath"].endswith("Factsheet_Normal-%20v1.xls") or f["filePath"].endswith("Factsheet_Normal- v1.xls"):
        return "2015-12"
    for label in (f["fileTitle"], f["filePath"].rsplit("/", 1)[-1]):
        found = parse_period(label or "")
        if found:
            return found
    mon = MONTHS.get((f["month"] or "").lower())
    return f"{int(f['year']):04d}-{mon:02d}" if mon else None


def list_disclosures(session):
    get = open_session(session)
    data = get("mf/statutory-menus/single", type="Statutory", fundType="MF", menuName="Portfolio of scheme(s)")
    seen = set()
    for f in data["files"]:
        path = f["filePath"] or ""
        if not f["subMenuName"].startswith("Monthly") or not path.lower().endswith((".xls", ".xlsx")):
            continue
        if EXTRAS.search(f["fileTitle"] or "") or path in seen:
            continue
        period = period_of(f)
        if period:
            seen.add(path)
            yield Disclosure(amc=SLUG, period=period, url=SITE + quote(path), filename=path.rsplit("/", 1)[-1])


def funds(wb):
    """Fund Id -> description from the Index sheet of the 2019+ workbooks."""
    if "Index" not in wb.sheet_names:
        return {}
    rows = wb.get_sheet_by_name("Index").to_python(skip_empty_area=False)
    return {text(r[0]): text(r[1]) for r in rows if len(r) > 1 and re.fullmatch(r"[A-Z0-9]{6}", text(r[0]))}


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        names = funds(wb)
        for sheet in wb.sheet_names:
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            hs = parse_sheet(rows, sheet, amc=amc, period=period, source=source)
            # Pre-2013 sheets carry section subtotals as rows, and the title in the first cell
            hs = [h for h in hs if h.isin or h.quantity or not (SUBTOTAL.match(h.name) or REVERSED.match(h.name))]
            title = next((text(c) for c in rows[0] if text(c)), "") if rows else ""
            for h in hs:
                if sheet in names:
                    h.scheme = names[sheet]
                elif re.match(r"edelweiss|e\.d\.g\.e", title, re.I):
                    h.scheme = title.rstrip(".*# ")
            pcts = [h.pct_nav for h in hs if h.pct_nav is not None]
            if pcts and abs(sum(pcts)) <= 1.5:
                for h in hs:
                    h.pct_nav = None if h.pct_nav is None else round(h.pct_nav * 100, 6)
            out.extend(hs)
    return out
