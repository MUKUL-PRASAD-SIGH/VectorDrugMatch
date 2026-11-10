"""
scripts/extract_who_eml_pdf.py - extract the WHO Model List of Essential Medicines (24th list, 2025) from the official PDF.

    python scripts/extract_who_eml_pdf.py [--pdf data/external/B09474-eng.pdf]

Output (data/external/, git-ignored: WHO text is CC BY-NC-SA 3.0 IGO, see Docs/LICENCE_AUDIT.md):
    who_eml.csv           one row per listed medicine entry: name (WHO spelling; footnote marks and the paediatric [c] marker removed
                          from the name), entry_type (single | combination), section_code/section/subsection/subsubsection (therapeutic
                          category), list (core | complementary), paediatric_marker_on_name, therapeutic_alternative_box
                          (WHO square-box symbol), pdf_page, edition, source_pdf_sha256. Formulation text is NOT extracted: in tall table rows
                          the name is vertically centred, so a formulation can precede its name in reading order and cannot be attached reliably. drugbank_id and atc_code are EMPTY: the list does
                          not print them and none are invented here.
    who_eml_extraction_report.json   counts, parse warnings, names flagged for manual review.
Layout rules (verified on this PDF): list pages are 6-67 (page 68 starts the annexes: dosage-form table, AWaRe text, vaccines, contacts, and
extraction stops there); medicine names are size-10 text at x<100, a name can continue on the same line (x 100-200) or, when it ends with '+',
on the next line (the formulation can be printed in between); formulations are in the right column (x>=200); size-9 text is therapeutic
alternatives / footnotes and is NOT a listed medicine; numbered headings give the section path; an italic 'Complementary List' marker switches the
list until the next heading. Corrigenda on PDF pages 3-4 change formulation text only, not names.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

import fitz
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
BOX = ""
HEAD = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")
SUBHEAD = re.compile(r"^\d+(\.\d+)+\s")


def spans_of(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                t = s["text"].replace("\xa0", " ").strip()
                if t:
                    out.append({"y": s["bbox"][1], "x": s["bbox"][0], "size": round(s["size"], 1), "italic": bool(s["flags"] & 2), "font": s["font"], "text": t})
    return sorted(out, key=lambda r: (round(r["y"] / 3), r["x"]))


COPACK = re.compile(r"(?<=[A-Za-z)])\s+–\s+(?=[A-Za-z(])")


def clean_name(raw):
    # The WHO list joins CO-PACKAGED products with an en dash (U+2013), e.g. 'mifepristone – misoprostol' (p.60), 'oral rehydration salts –
    # zinc sulfate' (p.53), 'artesunate – sulfadoxine + pyrimethamine' (p.29). Read it as '+' (a combination) BEFORE non-ASCII glyphs are stripped.
    raw = COPACK.sub(" + ", raw)
    name = re.sub(r"\[c\]", "", raw)
    name = re.sub(r"[^\x20-\x7e]+", " ", name)            # dagger/glyph footnote marks
    name = name.replace("*", " ")
    name = re.sub(r"\s+", " ", name).strip()
    while re.search(r"\s[a-z]$", name):                     # superscript footnote letter(s), e.g. 'ibuprofen a', 'ceftriaxone*a a'
        name = re.sub(r"\s[a-z]$", "", name)
    if name.count("(") > name.count(")"):                   # wrapped qualifier cut by the layout: keep only the text before the open '('
        name = name[:name.rfind("(")].strip()
    return name.strip(" ,")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default="data/external/B09474-eng.pdf")
    a = ap.parse_args()
    pdf = REPO / a.pdf
    doc = fitz.open(pdf)
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    entries, warn = [], []
    sec = {1: "", 2: "", 3: ""}
    lst, box, cur, started, stop, prefix = "core", False, None, False, False, None
    for pno in range(len(doc)):
        if stop:
            break
        for sp in spans_of(doc[pno]):
            t, x, sz = sp["text"], sp["x"], sp["size"]
            if "Explanation of dosage forms" in t:
                stop = True
                break
            if sz >= 13.5 or t.startswith("WHO Model List of Essential Medicines") or re.fullmatch(r"page \d+", t):
                continue
            if "Wingdings" in sp["font"] or "Symbol" in sp["font"]:
                box = box or (t == BOX)
                continue
            if re.fullmatch(r"[-?–—*]+", t):
                continue
            if re.fullmatch(r"\d+(\.\d+)+", t):
                continue
            m = HEAD.match(t)
            if m and (sz >= 10.9 or (SUBHEAD.match(t) and x < 60)):          # numbered heading (any level)
                if not started:
                    if not t.startswith("1"):
                        continue
                    started = True
                lvl = min(m.group(1).count(".") + 1, 3)
                sec[lvl] = t
                for k in range(lvl + 1, 4):
                    sec[k] = ""
                lst, cur, box = "core", None, False
                continue
            if not started:
                continue
            if t.lower() in ("complementary list", "core list"):
                lst = "complementary" if t.lower().startswith("comp") else "core"
                cur = None
                continue
            if 9.5 <= sz <= 10.5 and x < 100 and (len(t) > 70 or t.isupper() or (t[0].isupper() and len(t.split()) >= 4 and not t.startswith("("))):
                continue                                                        # explanatory paragraph / all-caps heading, not a medicine
            if 5.0 <= sz < 6.5 and x < 70 and re.fullmatch(r"[a-z]{1,3}", t):
                continue                                                        # 5.5pt superscript footnote mark (e.g. "th"), never part of a name
            if 8.0 <= sz < 9.5 and x < 70 and re.fullmatch(r"[a-z]{1,3}", t):
                if cur is not None and abs(sp["y"] - cur["_y"]) < 3 and x < cur["_x"] - 2:
                    cur["_raw"] = t + cur["_raw"]                               # prefix printed (and sorted) after its name span
                else:
                    prefix = (t, sp["y"])
                continue
            if prefix and 9.5 <= sz <= 10.5 and x < 100 and abs(sp["y"] - prefix[1]) < 3 and t[0].islower():
                t = prefix[0] + t
                prefix = None
            if 9.5 <= sz <= 10.5 and x < 100 and t.startswith("(") and cur is not None and cur["_y"] is not None and sp["y"] - cur["_y"] < 40:
                cur["_raw"] += " " + t                                          # '(alias)' line continuing the previous name
                continue
            if 9.5 <= sz <= 10.5 and x < 260 and cur is not None and cur["_open"] and abs(sp["y"] - cur["_y"]) < 2.5 and x >= 100:
                cur["_raw"] += " " + t                                          # polypill names spread over one line at several x positions
                cur["_open"] = cur["_raw"].rstrip().endswith("+")
                continue
            if 9.5 <= sz <= 10.5 and x < 100:                                  # start (or wrapped continuation) of a medicine name
                wrapped = cur is not None and 0 < sp["y"] - cur["_y"] < 13.5 and t[0].islower() and not cur["_raw"].rstrip().endswith(")")
                if cur is not None and (cur["_open"] or wrapped):               # previous name ended with '+' (or wraps just below): continuation
                    cur["_raw"] += " " + t
                    cur["_open"] = cur["_raw"].rstrip().endswith("+")
                    cur["_y"] = sp["y"]
                    continue
                cur = {"_raw": t, "_open": t.rstrip().endswith("+"), "_y": sp["y"], "_x": x, "section_code": (sec[1].split()[0].rstrip(".") if sec[1] else ""),
                       "section": sec[1], "subsection": sec[2], "subsubsection": sec[3], "list": lst,
                       "therapeutic_alternative_box": int(box), "pdf_page": pno + 1}
                entries.append(cur)
                box = False
                continue
            if 9.5 <= sz <= 10.5 and 100 <= x < 200 and cur is not None and abs(sp["y"] - cur["_y"]) < 2.5 and t[0].islower():   # same-line name continuation
                cur["_raw"] += " " + t
                cur["_open"] = cur["_raw"].rstrip().endswith("+")
                continue
    rows = []
    for e in entries:
        raw = e.pop("_raw")
        e.pop("_open")
        e.pop("_y")
        e.pop("_x")
        e["name"] = clean_name(raw)
        e["paediatric_marker_on_name"] = int("[c]" in raw)
        e["extraction_note"] = "co-packaged products joined by U+2013 in the PDF; read as '+' (combination)" if COPACK.search(raw) else ""
        rows.append(e)
    df = pd.DataFrame(rows)
    df = df[df.name.str.len() > 1]
    df["entry_type"] = df.name.map(lambda n: "combination" if re.search(r"\s\+\s", n) else "single")
    df["edition"] = "WHO Model List of Essential Medicines, 24th list (2025)"
    df["source_pdf"] = a.pdf
    df["source_pdf_sha256"] = sha
    df["drugbank_id"] = ""
    df["atc_code"] = ""
    df["name_key"] = df.name.str.lower()
    dup = df.duplicated(["name_key", "section_code", "subsection", "list"], keep="first")
    if dup.any():
        warn.append(f"{int(dup.sum())} exact duplicate entries dropped (same name + section + subsection + list)")
        df = df[~dup]
    df = df.drop(columns="name_key")
    review = df[(df.name.str.len() > 60) | df.name.str.contains(r"\d{3,}") | df.name.str.contains(r"[^A-Za-z0-9 ()+,./'%\-\[\]]")]
    out = REPO / "data" / "external" / "who_eml.csv"
    df.to_csv(out, index=False)
    rep = {"pdf": a.pdf, "pdf_sha256": sha, "pdf_pages": len(doc), "pages_with_entries": [int(df.pdf_page.min()), int(df.pdf_page.max())], "entries": int(len(df)),
           "distinct_names": int(df.name.str.lower().nunique()), "by_type": df.entry_type.value_counts().to_dict(), "by_list": df.list.value_counts().to_dict(),
           "entries_by_top_section": {k: int(v) for k, v in df.groupby("section").size().items()}, "box_marked": int(df.therapeutic_alternative_box.sum()),
           "warnings": warn, "names_to_review": review.name.tolist()[:60]}
    (REPO / "data" / "external" / "who_eml_extraction_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("pages_with_entries", "entries", "distinct_names", "by_type", "by_list", "box_marked", "warnings")}, indent=1))
    print("names to review:", [n.encode("ascii", "replace").decode() for n in rep["names_to_review"]])


if __name__ == "__main__":
    main()
