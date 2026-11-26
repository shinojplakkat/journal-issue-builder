"""Make invented sample articles for testing (no real author's work).

    python samples/make_samples.py [output folder]

Writes DOCX files; with LibreOffice installed it also makes ODT, DOC and PDF copies.
"""

from __future__ import annotations

import random
import struct
import sys
import zlib
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt

WORDS = ("performance tradition rhythm gesture text audience archive memory form training "
         "lineage interpretation body voice stage manuscript repertoire aesthetic practice "
         "community narrative composition movement teacher student culture history method").split()


def sentence(rng: random.Random, n: int = 14) -> str:
    words = [rng.choice(WORDS) for _ in range(n)]
    return " ".join(words).capitalize() + "."


def paragraph(rng: random.Random, sentences: int = 5) -> str:
    return " ".join(sentence(rng, rng.randint(9, 18)) for _ in range(sentences))


def tiny_png(path: Path, width: int = 600, height: int = 300) -> Path:
    """A plain grey picture, written without any imaging library."""
    rows = b"".join(b"\x00" + bytes([180, 180, 200]) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)
    return path


def make_article(path: Path, seed: int, title: str, authors: list[str], sections: int,
                 malayalam: bool = False, table: bool = False, image: Path | None = None) -> Path:
    rng = random.Random(seed)
    doc = Document()
    for section in doc.sections:  # authors usually send A4
        section.page_width, section.page_height = Mm(210), Mm(297)
    doc.styles["Normal"].font.name = "Times New Roman"
    doc.styles["Normal"].font.size = Pt(12)

    p = doc.add_paragraph()
    run = p.add_run(title)
    run.bold, run.font.size = True, Pt(16)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for k, name in enumerate(authors, 1):
        p.add_run(name)
        sup = p.add_run(str(k) + ("*" if k == 1 else ""))
        sup.font.superscript = True
        if k < len(authors):
            p.add_run(", ")
    for k, _ in enumerate(authors, 1):
        q = doc.add_paragraph()
        q.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sup = q.add_run(str(k))
        sup.font.superscript = True
        q.add_run(f"Department of Performing Arts, Sample University {k}, Kerala, India")
    doc.add_paragraph("ORCID: 0000-0002-1825-0097").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("Email: first.author@example.org").alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.add_run("Abstract: ").bold = True
    p.add_run(paragraph(rng, 6))
    p = doc.add_paragraph()
    p.add_run("Keywords: ").bold = True
    p.add_run(", ".join(rng.sample(WORDS, 5)))

    for s in range(1, sections + 1):
        doc.add_heading(f"{s}. {sentence(rng, 3)[:-1]}", level=1)
        for _ in range(rng.randint(2, 4)):
            p = doc.add_paragraph(paragraph(rng, rng.randint(4, 8)))
            if rng.random() < 0.5:
                p.add_run(" The text ")
                p.add_run("Natyashastra").italic = True
                p.add_run(" is cited here.")
        if s == 2:
            doc.add_heading(f"{s}.1 {sentence(rng, 3)[:-1]}", level=2)
            doc.add_paragraph(paragraph(rng, 5))
        if malayalam and s == 1:
            doc.add_paragraph("കേരളത്തിലെ ക്ലാസിക്കൽ കലകളുടെ പഠനവും പരിശീലനവും ഗുരുകുല സമ്പ്രദായത്തിലൂടെയാണ് "
                              "തലമുറകളിലേക്ക് കൈമാറിയത്. ഈ ഭാഗം മലയാളം അക്ഷരങ്ങൾ ശരിയായി കാണുന്നുണ്ടോ "
                              "എന്ന് പരിശോധിക്കാനുള്ളതാണ്.")
        if table and s == 2:
            t = doc.add_table(rows=4, cols=3)
            t.style = "Table Grid"
            for r, row in enumerate(t.rows):
                for c, cell in enumerate(row.cells):
                    cell.text = ["Form", "Region", "Period"][c] if r == 0 else rng.choice(WORDS).capitalize()
            doc.add_paragraph("Table 1: " + sentence(rng, 6))
        if image is not None and s == 1:
            doc.add_picture(str(image), width=Mm(160))
            doc.add_paragraph("Figure 1: " + sentence(rng, 5))

    doc.add_heading("Acknowledgements", level=1)
    doc.add_paragraph(sentence(rng, 15))
    doc.add_heading("References", level=1)
    for k in range(8):
        p = doc.add_paragraph(f"{rng.choice(['Nair', 'Menon', 'Rao', 'Smith', 'Iyer'])}, "
                              f"{rng.choice('ABCKPRS')}. ({2000 + k}). ")
        p.add_run(sentence(rng, 6)[:-1]).italic = True
        p.add_run(". Sample Press.")
    doc.save(str(path))
    return path


def main(folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    image = tiny_png(folder / "figure.png")
    files = [
        make_article(folder / "article_rhythm.docx", 1, "Rhythm and Memory in Classical Performance Training",
                     ["Priya Nair", "Rahul Menon"], 4, table=True, image=image),
        make_article(folder / "article_lineage.docx", 2, "Teaching Lineages: A Study of the Gurukula Method",
                     ["Anitha K. Rao"], 3, malayalam=True),
        make_article(folder / "article_archive.docx", 3, "Archiving the Stage: Manuscripts, Notation and Practice",
                     ["S. Iyer", "M. Smith", "K. Varma"], 5),
        make_article(folder / "review_book.docx", 4, "Book Review: Movement and Meaning", ["T. George"], 1),
    ]
    image.unlink()
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from issuebuilder.tools import libreoffice

        libreoffice.convert([files[1]], "pdf", folder)          # a PDF submission
        odt = folder / "odt"
        libreoffice.LIBREOFFICE.run(["--headless", "--convert-to", "odt", "--outdir", str(odt), str(files[2])])
        for f in odt.glob("*.odt"):
            f.rename(folder / f.name)
        odt.rmdir()
        files[2].unlink()   # keep the ODT version of this one
    except Exception as error:
        print("LibreOffice copies skipped:", error)
    return sorted(folder.iterdir())


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "generated"
    for f in main(out):
        print(f)
