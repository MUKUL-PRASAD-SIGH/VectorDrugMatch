"""
Docs/make_upload_folder.py - copy exactly the files listed in Docs/drive_upload_expected.json into one local folder, ready to upload to Drive.

    python Docs/make_upload_folder.py "<output folder>"          # run from the repository root; creates <output folder>/VDM_Data/...

Nothing is uploaded and nothing is deleted. Source of each file (relative to the repository root):
    frozen_processed/<v>/...  <- data/processed/<v>/...      downloads/...  <- data/external/downloads/...      anything else <- data/external/...
Afterwards run:  python Docs/check_drive_folder.py "<output folder>/VDM_Data"
"""
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def source(rel):
    if rel.startswith("frozen_processed/"):
        return REPO / "data" / "processed" / rel[len("frozen_processed/"):]
    return REPO / "data" / "external" / rel


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = Path(sys.argv[1]) / "VDM_Data"
    exp = json.loads((Path(__file__).with_name("drive_upload_expected.json")).read_text(encoding="utf-8"))["files"]
    missing = [e["path"] for e in exp if not source(e["path"]).is_file()]
    if missing:
        sys.exit("missing source files (build or restore them first):\n  " + "\n  ".join(missing))
    for e in exp:
        dest = out / e["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source(e["path"]), dest)
    print(f"copied {len(exp)} files to {out}")


if __name__ == "__main__":
    main()
