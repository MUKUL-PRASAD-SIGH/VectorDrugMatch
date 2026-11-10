"""
scripts/render_paper.py - render Docs/paper/PAPER_DRAFT_IEEE.md to HTML and PDF (headless Edge/Chrome).

    python scripts/render_paper.py

Output: Docs/paper/PAPER_DRAFT_IEEE.html and .pdf (the PDF is a review copy, not the final IEEE-template typeset).
"""
import subprocess
import sys
from pathlib import Path

import markdown

D = Path(__file__).resolve().parents[1] / "Docs" / "paper"
CSS = """
body{font-family:'Times New Roman',serif;font-size:10pt;line-height:1.32;max-width:7.2in;margin:0 auto;color:#111}
h1{font-size:17pt;text-align:center;margin:0 0 6pt}
h2{font-size:10.5pt;text-transform:uppercase;margin:12pt 0 3pt;letter-spacing:.02em}
p{text-align:justify;margin:3pt 0}
table{border-collapse:collapse;margin:6pt auto;font-size:8.5pt}
th,td{border:1px solid #555;padding:2px 6px;vertical-align:top}
th{background:#eee}
img{display:block;margin:6pt auto 2pt;max-width:3.6in;max-height:3.4in;height:auto}
code{font-size:8.5pt;background:#f3f3f3;padding:0 2px}
em{font-style:italic}
@page{size:Letter;margin:0.75in}
"""


def main():
    src = (D / "PAPER_DRAFT_IEEE.md").read_text(encoding="utf-8")
    html_body = markdown.markdown(src, extensions=["tables", "sane_lists"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>VectorDrugMatch draft</title><style>{CSS}</style></head><body>{html_body}</body></html>"
    out_html, out_pdf = D / "PAPER_DRAFT_IEEE.html", D / "PAPER_DRAFT_IEEE.pdf"
    out_html.write_text(html, encoding="utf-8")
    for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if Path(exe).exists():
            r = subprocess.run([exe, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out_pdf}", out_html.as_uri()],
                               capture_output=True, text=True, timeout=120)
            if out_pdf.exists():
                print("wrote", out_pdf)
                return
            print(r.stderr[-300:])
    sys.exit("no headless browser produced a PDF")


if __name__ == "__main__":
    main()
