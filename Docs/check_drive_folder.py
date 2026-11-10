"""
Docs/check_drive_folder.py - check the VDM_Data folder against Docs/drive_upload_expected.json (PASS/FAIL per file).

    python Docs/check_drive_folder.py "<path to the VDM_Data folder>" [--no-hash]

Use it on your PC before uploading (point it at VDM_FINAL_FOLDER/UPLOAD_THIS/VDM_Data) and read the same PASS/FAIL in the
notebook (Step 3a) after the upload. Standard library only. Exit code 0 = no REQUIRED problem.
Levels: REQUIRED (the run must not start without it), RECOMMENDED (missing = that equity component is reported as missing, never 0).
"""
import hashlib
import json
import sys
from pathlib import Path

FORBIDDEN = ("primekg_kg.csv", "drugbank_vocabulary.csv", "full database.xml", "full_database.xml", ".env")   # never needed in Drive / restricted


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    root = Path(args[0])
    do_hash = "--no-hash" not in sys.argv
    exp = json.loads((Path(__file__).with_name("drive_upload_expected.json")).read_text(encoding="utf-8"))["files"]
    bad_req, bad_rec, ok = [], [], 0
    for e in exp:
        f = root / e["path"]
        why = None
        if not f.is_file():
            why = "MISSING"
        elif f.stat().st_size != e["size"]:
            why = f"SIZE {f.stat().st_size} != {e['size']}"
        elif do_hash and hashlib.sha256(f.read_bytes()).hexdigest() != e["sha256"]:
            why = "HASH DIFFERS"
        if why is None:
            ok += 1
        else:
            print(f"FAIL [{e['level']}] {e['path']}: {why}")
            (bad_req if e["level"] == "REQUIRED" else bad_rec).append(e["path"])
    known = {e["path"] for e in exp}
    extra = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.relative_to(root).as_posix() not in known]
    for p in extra:
        flag = "RESTRICTED/NOT NEEDED - remove" if Path(p).name in FORBIDDEN else "not read by the notebook (harmless, but not needed)"
        print(f"EXTRA {p}: {flag}")
    print(f"{ok}/{len(exp)} files OK; REQUIRED problems: {len(bad_req)}; RECOMMENDED problems: {len(bad_rec)}; extra files: {len(extra)}; hashes checked: {do_hash}")
    print("RESULT:", "PASS" if not bad_req and not [p for p in extra if Path(p).name in FORBIDDEN] else "FAIL")
    sys.exit(1 if bad_req else 0)


if __name__ == "__main__":
    main()
