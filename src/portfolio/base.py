import base64
import calendar
import datetime
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9

_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
_SEP = r"[\s_\-.,/']*"
_MONTH_YEAR = re.compile(rf"(?<![a-z])({_MON})(?:\d{{0,2}}(?:st|nd|rd|th)?)?{_SEP}((?:19|20)\d\d|\d\d)(?!\d)", re.I)
_YEAR_MONTH = re.compile(rf"((?:19|20)\d\d){_SEP}({_MON})(?![a-z])", re.I)
_DMY = re.compile(r"(?<!\d)(\d{1,2})[\-/.](\d{1,2})[\-/.]((?:19|20)\d\d)(?!\d)")
_YMD = re.compile(r"(?<!\d)((?:19|20)\d\d)[\-/.]?(\d\d)[\-/.]?(\d\d)(?!\d)")
_DMY8 = re.compile(r"(?<!\d)(\d\d)(\d\d)((?:19|20)\d\d)(?!\d)")
_DMONY = re.compile(
    rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th)?{_SEP}({_MON}){_SEP}((?:19|20)\d\d|\d\d)(?!\d)", re.I
)
_MONDY = re.compile(
    rf"(?<![a-z])({_MON}){_SEP}(\d{{1,2}})(?:st|nd|rd|th)?{_SEP}((?:19|20)\d\d)(?!\d)", re.I
)


@dataclass
class Disclosure:
    amc: str
    period: str
    url: str
    filename: str = ""
    scheme: str = ""
    method: str = "GET"
    headers: dict = field(default_factory=dict)
    data: dict | None = None

    def __post_init__(self):
        if not self.filename:
            self.filename = self.url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
        self.filename = re.sub(r"[^\w.\-]+", "_", self.filename)[-150:]


def session(impersonate: str | None = None):
    """requests session; pass impersonate='chrome' for sites that reject plain clients."""
    if impersonate:
        from curl_cffi import requests as cffi

        s = cffi.Session(impersonate=impersonate)
        s.headers.update({"Accept-Language": "en-IN,en;q=0.9"})
        return s
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"})
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def aes_cbc(key: bytes, iv: bytes, data: str, decrypt: bool = True) -> str:
    """CryptoJS-compatible AES-CBC/PKCS7 over base64 text, for sites that wrap their JSON."""
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    if decrypt:
        op, pad = cipher.decryptor(), padding.PKCS7(128).unpadder()
        raw = op.update(base64.b64decode(data)) + op.finalize()
        return (pad.update(raw) + pad.finalize()).decode()
    op, pad = cipher.encryptor(), padding.PKCS7(128).padder()
    raw = pad.update(data.encode()) + pad.finalize()
    return base64.b64encode(op.update(raw) + op.finalize()).decode()


def _year(y: str) -> int:
    y = int(y)
    return y + 2000 if y < 100 else y


def parse_period(text: str) -> str | None:
    """Best-effort YYYY-MM from a filename, link text or title."""
    text = text.replace("%20", " ")
    d = parse_date(text)
    if d:
        return f"{d.year:04d}-{d.month:02d}"
    for rx, order in ((_MONTH_YEAR, "my"), (_YEAR_MONTH, "ym")):
        m = rx.search(text)
        if m:
            a, b = m.groups()
            mon, yr = (a, b) if order == "my" else (b, a)
            return f"{_year(yr):04d}-{MONTHS[mon.lower()]:02d}"
    return None


def parse_date(text: str) -> datetime.date | None:
    """Best-effort full date from free text such as 'as on 31st July 2020'."""
    try:
        m = _DMONY.search(text)
        if m:
            return datetime.date(_year(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
        m = _MONDY.search(text)
        if m:
            return datetime.date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
        m = _DMY.search(text)
        if m:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = _YMD.search(text)
        if m and 1 <= int(m.group(2)) <= 12:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = _DMY8.search(text)
        if m:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    return None


def month_end(period: str) -> datetime.date:
    y, m = map(int, period.split("-"))
    return datetime.date(y, m, calendar.monthrange(y, m)[1])


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def links(html: str, base: str) -> list[tuple[str, str]]:
    """(absolute_url, link_text) for every anchor in the page."""
    p = _Links()
    p.feed(html)
    return [(urljoin(base, h.strip()), t) for h, t in p.links if h]


def is_sheet(url: str) -> bool:
    return bool(re.search(r"\.(xlsx?|xlsb|xlsm|zip|ods)(\?|$)", url, re.I))
