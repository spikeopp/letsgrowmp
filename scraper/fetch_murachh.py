"""Refresh data/murachh.json from public NREGASoft reports.

Run from the repo root:  python3 scraper/fetch_murachh.py
"""
import datetime
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nrega import Session, biggest_table, find, open_panchayat  # noqa: E402

DISTRICT, BLOCK, GP = "PANNA", "PAWAI", "MURACHH"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "murachh.json")
SRC_DIR = os.path.join(os.path.dirname(OUT), "sources")
ENTRY = "https://nrega.dord.gov.in/stHome.aspx"
PATH = ["MADHYA PRADESH", "PANNA", "PAWAI", "MURACHH"]
SOURCES = {}


def keep(key, title, steps, page, archive=True):
    """Record where a dataset came from; optionally archive the raw page."""
    src = {"title": title, "steps": PATH + steps, "official_entry": ENTRY,
           "report_url_at_fetch": page.url,
           "sha256": hashlib.sha256(page.raw.encode("utf-8")).hexdigest()}
    if archive:
        os.makedirs(SRC_DIR, exist_ok=True)
        name = key + ".html"
        with open(os.path.join(SRC_DIR, name), "w", encoding="utf-8") as f:
            f.write(page.raw)
        src["snapshot"] = "data/sources/" + name
    SOURCES[key] = src


def num(x):
    try:
        return float(str(x).replace(",", "").replace("%", "").strip() or 0)
    except ValueError:
        return 0.0


def split_work(cell):
    m = re.match(r"^(.*)\(([^()]*)\)\s*$", cell or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else (cell.strip(), "")


def works(s, gp):
    page = s.get(find(gp, "Work Expenditure"))
    page = s.submit(page, {"ddfin": "ALL", "ddamt": "All", "workcat": "ALL", "workcattype": "ALL"})
    keep("works", "Work Expenditure", ["R3. Work", "Work Expenditure", "Financial year: ALL", "View Report"], page)
    out = []
    for r in biggest_table(page):
        if len(r) < 21 or not r[0].isdigit():
            continue
        name, code = split_work(r[1])
        out.append({
            "code": code, "name": name, "status": r[2], "fy": r[3], "agency": r[4], "category": r[5],
            "mandays": int(num(r[8])),
            "est_total": num(r[14]), "est_material": num(r[12]),
            "exp_unskilled": num(r[15]), "exp_semiskilled": num(r[16]), "exp_skilled": num(r[17]),
            "exp_material": num(r[18]), "exp_total": num(r[20]),
        })
    return out


def register(s, gp):
    """Register IV (Work Register): sanction and start/finish dates for open works."""
    page = s.get(find(gp, "Work Register"))
    keep("register", "Work Register (Register IV)", ["R6. Registers", "Work Register"], page)
    out = {}
    for r in biggest_table(page):
        if len(r) < 11 or not r[0].isdigit() or "1709004049/" not in r[1]:
            continue
        m = re.match(r"^(1709004049/[A-Z]+/[\w/]+?)([^\w/].*|[A-Za-z\u0900-\u097f].*)$", r[1])
        code = m.group(1) if m else r[1].split()[0]
        out[code] = {"ts_date": r[3], "as_date": r[4], "agency": r[5], "start_date": r[6],
                     "expected_end": r[7], "actual_end": r[8],
                     "sanctioned_unskilled": num(r[9]), "sanctioned_material": num(r[10])}
    return out


def bills(s, gp):
    page = s.get(find(gp, "Material Procured Report"))
    keep("bills", "Material Procured Report", ["R2. Demand, Allocation & Musteroll", "Material Procured Report"], page)
    seen, out, cur, section = set(), [], None, ""
    rows = [r for t in page.tables for r in t]

    def val(c):
        return c.split(":", 1)[1].strip() if ":" in c else c.strip()

    for r in rows:
        line = " | ".join(r)
        if len(r) == 1 and line.startswith("Expenditure on Material"):
            section = line
        if len(r) == 1 and re.search(r"\(\d{10}/[^()]*\)\s*$", r[0]):
            name, code = split_work(val(r[0]) if r[0].lstrip().startswith(("Work", ":")) else r[0])
            cur = {"work_code": code, "work_name": name, "items": [], "note": section}
        elif cur is not None and len(r) == 4 and re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", val(r[2])):
            cur.update(bill_no=val(r[0]), amount=num(val(r[1])), bill_date=val(r[2]), paid_date=val(r[3]))
        elif cur is not None and len(r) == 2 and re.match(r"^\d{4}-\d{4}$", val(r[1])):
            cur["vendor"], cur["fy"] = val(r[0]), val(r[1])
            key = (cur["work_code"], cur.get("bill_no"), cur.get("bill_date"))
            if key not in seen:
                seen.add(key)
                out.append(cur)
        elif cur is not None and len(r) == 4 and r[0] not in ("Material", "") and re.match(r"^[\d.,]+$", r[3] or ""):
            item = {"material": r[0], "unit_price": num(r[1]), "qty": num(r[2]), "amount": num(r[3])}
            if item not in cur["items"]:
                cur["items"].append(item)
    return out


def wage_material(s, gp):
    page = s.get(find(gp, "Wage Material Ratio Analysis"))
    keep("wage_material", "Wage Material Ratio Analysis", ["R4. Irregularities / Analysis", "Wage Material Ratio Analysis"], page)
    t = biggest_table(page)
    fy = next((re.search(r"(\d{4}-\d{4})", r[0]).group(1) for r in t if r and re.search(r"\d{4}-\d{4}", r[0])), "")
    for r in t:
        if len(r) >= 5 and r[1].upper() == GP:
            return {"fy": fy, "total_lakh": num(r[2]),
                    "wage_lakh": num(r[3].split("(")[0]), "material_lakh": num(r[4].split("(")[0])}
    return None


def jobcards(s, gp):
    page = s.get(find(gp, "Job card/Employment Register"))
    # Not archived: the register lists every worker by name; we publish counts only.
    keep("jobcards", "Job card/Employment Register", ["R1. Job Card/Registration", "Job card/Employment Register"], page, archive=False)
    t = biggest_table(page)
    rows = [r for r in t if r and r[0].isdigit()]
    households = {re.sub(r"[-\s]*[A-Z]?\s*\*?$", "", r[1]).strip() for r in rows if len(r) > 1}
    return {"registered_people": len(rows), "households": len(households)}


def main():
    s = Session()
    gp = open_panchayat(s, DISTRICT, BLOCK, GP)
    data = {
        "meta": {
            "gram_panchayat": "Murachh", "block": "Pawai", "district": "Panna", "state": "Madhya Pradesh",
            "gp_code": "1709004049",
            "source": "NREGASoft public reports (mnregaweb2.dord.gov.in)",
            "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        },
        "works": works(s, gp),
        "bills": bills(s, gp),
        "register": register(s, gp),
        "wage_material_current": wage_material(s, gp),
        "jobcards": jobcards(s, gp),
    }
    data["sources"] = SOURCES
    if len(data["works"]) < 50:
        sys.exit(f"Only {len(data['works'])} works parsed; refusing to overwrite data file.")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"works={len(data['works'])} bills={len(data['bills'])} "
          f"wmr={data['wage_material_current']} jobcards={data['jobcards']}")


if __name__ == "__main__":
    main()
