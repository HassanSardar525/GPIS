"""Print pages in the AGP report that mention prototype districts.

This is a small source-inspection utility, not an automated ingestion pipeline.
"""

from pathlib import Path

import pdfplumber


PDF_PATH = Path("data/raw/agp_punjab_south_dha_2024-25.pdf")
DISTRICTS = (
    "Multan",
    "Bahawalpur",
    "Rahim Yar Khan",
    "Muzaffargarh",
    "Dera Ghazi Khan",
)


def main() -> None:
    with pdfplumber.open(PDF_PATH) as report:
        print(f"pages={len(report.pages)}")
        for page_number, page in enumerate(report.pages, start=1):
            text = page.extract_text() or ""
            matches = [name for name in DISTRICTS if name.casefold() in text.casefold()]
            if matches:
                preview = " ".join(text.split())[:260]
                print(f"page={page_number} districts={','.join(matches)} :: {preview}")


if __name__ == "__main__":
    main()
