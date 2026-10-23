#!/usr/bin/env python3
"""
Genereaza baza de date guests.json din Excel-ul cu invitati (o singura data,
lista e statica). Se citesc doar coloanele A (nume) si B (numar de invitati).

    python3 import_excel.py "Lista Invitati.xlsx"          -> scrie guests.json

- randul de antet ("NUME") si randul "total" sunt sarite
- numerele de telefon scrise in coloana A sunt eliminate (nu ajung pe tablete)
- textul din paranteze, ex. "(OLD JACK - P-TA SFATULUI)", devine un detaliu
  afisat sub nume
Doar biblioteca standard Python 3.8+.
"""
import hashlib
import io
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def col_index(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def first_sheet_rows(path):
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.get("Id"): r.get("Target") for r in rels}
    sh = wb.find("m:sheets", NS)[0]
    target = relmap[sh.get("{%s}id" % NS["r"])].lstrip("/")
    root = ET.fromstring(z.read(target if target.startswith("xl/") else "xl/" + target))
    rows = []
    for row in root.iter("{%s}row" % NS["m"]):
        vals = {}
        for c in row.findall("m:c", NS):
            t, v = c.get("t"), c.find("m:v", NS)
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter("{%s}t" % NS["m"]))
            elif v is not None:
                val = v.text
            else:
                val = None
            vals[col_index(c.get("r"))] = val
        rows.append((int(row.get("r")), vals.get(0), vals.get(1)))
    return rows


def clean_name(raw):
    s = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", str(raw or ""))   # caractere invizibile
    s = re.sub(r"\s+", " ", s).strip()
    details = [d.strip(" -") for d in re.findall(r"\(([^)]*)\)", s)]
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\+?\d[\d .\-]{5,}\d", " ", s)        # telefoane
    s = re.sub(r"\s+", " ", s).strip(" -,")
    detail = " · ".join(re.sub(r"\s+-\s*|\s*-\s+", " - ", d).strip() for d in details if d)
    return s, detail


def to_int(v):
    try:
        return max(1, int(float(str(v).strip())))
    except Exception:
        return 1


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "lista.xlsx"
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "guests.json")
    guests = []
    for rownum, a, b in first_sheet_rows(src):
        name, detail = clean_name(a)
        low = name.lower()
        if not name or low in ("nume", "total", "nume si prenume"):
            continue
        gid = hashlib.sha1(("%d|%s" % (rownum, name)).encode("utf-8")).hexdigest()[:10]
        guests.append({"id": gid, "row": rownum, "name": name, "detail": detail, "count": to_int(b)})
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"title": "Radisson Blu Brașov",
                   "subtitle": "23 octombrie 2026",
                   "guests": guests}, f, ensure_ascii=False, indent=1)
    print("%d intrari, %d persoane -> %s" % (len(guests), sum(g["count"] for g in guests), out))


if __name__ == "__main__":
    main()
