"""Fetch public MGNREGA (NREGASoft) reports for one Gram Panchayat.

Standard library only. Report links on NREGASoft carry session-bound
payloads, so we walk State -> District -> Block -> Panchayat in one cookie
session, exactly like a browser would, then open each report from there.
"""
import http.cookiejar
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

STATE_URL = ("https://mnregaweb2.dord.gov.in/netnrega/homestciti.aspx?"
             "state_code=17&state_name=MADHYA%20PRADESH&lflag=eng&labels=labels")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


class Page(HTMLParser):
    """Collects links, form fields and tables from one HTML page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.forms, self.tables = [], [], []
        self._a = None
        self._tstack = []          # stack of tables being built
        self._cell = None
        self._select = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            self._a = [a.get("href", ""), ""]
        elif tag == "form":
            self.forms.append({"action": a.get("action", ""), "fields": {}, "selects": {}})
        elif tag == "input" and self.forms and a.get("name"):
            if a.get("type", "text").lower() not in ("checkbox", "radio", "image") or "checked" in a:
                self.forms[-1]["fields"][a["name"]] = a.get("value", "")
        elif tag == "select" and self.forms and a.get("name"):
            self._select = a["name"]
            self.forms[-1]["selects"][self._select] = []
        elif tag == "option" and self._select:
            self.forms[-1]["selects"][self._select].append([a.get("value", ""), "selected" in a, ""])
        elif tag == "table":
            self._tstack.append([])
        elif tag == "tr" and self._tstack:
            self._tstack[-1].append([])
        elif tag in ("td", "th") and self._tstack and self._tstack[-1]:
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "a" and self._a:
            self.links.append((self._a[1].strip(), self._a[0]))
            self._a = None
        elif tag == "select":
            self._select = None
        elif tag in ("td", "th") and self._cell is not None and self._tstack and self._tstack[-1]:
            self._tstack[-1][-1].append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "table" and self._tstack:
            self.tables.append(self._tstack.pop())

    def handle_data(self, data):
        if self._a is not None:
            self._a[1] += data
        if self._cell is not None:
            self._cell.append(data)
        if self._select and self.forms and self.forms[-1]["selects"][self._select]:
            self.forms[-1]["selects"][self._select][-1][2] += data.strip()


class Session:
    def __init__(self):
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(self, url, data=None):
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
        if data is not None:
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with self.op.open(req, timeout=90) as r:
            final = r.geturl()
            html = r.read().decode("utf-8", "replace")
        p = Page()
        p.feed(html)
        p.url = final
        return p

    def submit(self, page, overrides):
        """Post the page's (last) ASP.NET form with some select values overridden."""
        f = page.forms[-1]
        data = dict(f["fields"])
        for name, opts in f["selects"].items():
            sel = next((o[0] for o in opts if o[1]), opts[0][0] if opts else "")
            data[name] = sel
        for key, want in overrides.items():
            name = next((n for n in f["selects"] if n.endswith(key)), None)
            if name is None:
                continue
            opts = f["selects"][name]
            val = next((o[0] for o in opts if o[2] == want or o[0] == want), None)
            data[name] = val if val is not None else want
        url = urllib.parse.urljoin(page.url, f["action"])
        return self.get(url, urllib.parse.urlencode(data).encode())


def find(page, text, exact=True):
    for label, href in page.links:
        if (label.upper() == text.upper()) if exact else (text.lower() in label.lower()):
            return urllib.parse.urljoin(page.url, href)
    raise LookupError(f"link not found: {text!r} on {page.url}")


def open_panchayat(s, district, block, panchayat):
    st = s.get(STATE_URL)
    d = s.get(find(st, district))
    b = s.get(find(d, block))
    return s.get(find(b, panchayat))


def biggest_table(page):
    return max(page.tables, key=len) if page.tables else []
