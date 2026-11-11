"""scripts/check_paper.py - structural checks on Docs/paper/PAPER_DRAFT_IEEE.md (citations, figures, tables, numbers)."""
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
D = R / "Docs" / "paper"
t = (D / "PAPER_DRAFT_IEEE.md").read_text(encoding="utf-8")
body, refs = t.split("## References")
fails = []


def chk(ok, msg):
    print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    if not ok:
        fails.append(msg)


no_img = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)
cited = []
for m in re.finditer(r"\[(\d+(?:\s*,\s*\d+)*)\]", no_img):
    for part in re.split(r"\s*,\s*", m.group(1)):
        cited.append(int(part))
# adjacent citations written as "[3], [4]" are separate matches, handled by the loop above
entries = [int(x) for x in re.findall(r"^\[(\d+)\] ", refs, re.M)]
first = list(dict.fromkeys(cited))
chk(set(cited) <= set(entries), f"every cited number has an entry (missing: {sorted(set(cited) - set(entries))})")
chk(set(entries) <= set(cited), f"every entry is cited (uncited: {sorted(set(entries) - set(cited))})")
chk(entries == list(range(1, len(entries) + 1)), "entries numbered 1..N without gaps")
chk(first == sorted(first), f"numbered by first citation (first-appearance order: {first})")
figs = {int(x) for x in re.findall(r"!\[Fig\. (\d+)\.", body)}
chk(figs == set(range(1, 12)), f"11 figures embedded, numbered 1..11 ({sorted(figs)})")
for f in re.findall(r"\(figures/([^)]+\.png)\)", body):
    ok = (D / "figures" / f).exists() and (D / "figures" / f.replace(".png", ".pdf")).exists()
    chk(ok, f"figure files exist (png+pdf): {f}")
text_only = re.sub(r"!\[Fig[^\n]*\n|\*\*Fig\. \d+\.\*\*[^\n]*\n", "", body)
for n in sorted(figs):
    chk(re.search(rf"Fig\. {n}\b", text_only) is not None, f"Fig. {n} is cited in running text")
for tn in ("I", "II", "III", "IV", "V", "VI", "VII"):
    chk(re.search(rf"Table {tn}\b|TABLE {tn}\b", body) is not None, f"Table {tn} present/cited")
M = json.loads((D / "metrics.json").read_text())
s = M["split"]
checks = {"6,730": s["train"]["positives"], "1,397": s["val"]["positives"], "1,261": s["test"]["positives"],
          "7,407": M["disease_mapping_status"]["mapped"],
          "40,937": M["open_targets"]["pairs"]["clean_pairs_after_dedup"],
          "996": M["structure_coverage"]["drugs_no_smiles"], "997": M["structure_coverage"]["drugs_zero_fingerprint"]}
for k, v in checks.items():
    chk(k in body and f"{v:,}" == k, f"paper number {k} equals metrics.json ({v:,})")
chk("PENDING" in body, "pending sections are marked [PENDING]")
print("\n=== RESULT ===", "all paper checks passed" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
