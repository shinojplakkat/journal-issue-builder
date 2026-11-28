# Journal Issue Builder

Offline desktop program (Windows and Ubuntu) that assembles a journal issue from submitted
articles in DOC, DOCX, ODT and PDF: an electronic issue PDF, per-article PDFs, print files for
stapled (saddle-stitch) or glued binding, covers with spine, and single-article offprints.

Status: first working version (0.1). Licence: AGPL-3.0. Planning document: BLUEPRINT.md.

## Requirements

- LibreOffice (installed separately) — converts DOC/ODT and lays out Word articles.
- Optional: Ghostscript — grayscale print interiors.
- Fonts: Liberation Serif/Sans (installed with LibreOffice) by default; Noto Serif Malayalam for
  Malayalam text.

The installers contain Python, Qt and all Python libraries.

## How it works

1. **Import** (`importers/`): the submitted file is copied into the issue folder (originals are never
   changed). DOC/ODT are converted to DOCX with LibreOffice; tracked changes are accepted and
   comments removed in a working copy. PDFs are checked (password, damage, scans) and their title,
   authors and abstract are suggested from font sizes.
2. **Analysis** (`analyzer/`): every paragraph of a Word article gets a label (title, author, ORCID,
   institution, abstract, keywords, headings, body, references, …) with a confidence score. Rules
   live in `analyzer/rules.py`. ORCID iDs are checksum-validated.
3. **Review** (GUI): the editor corrects labels; corrections are saved in `article.json`.
4. **Article layout** (`builder/word_layout.py`): a copy of the author's Word file is changed —
   page size, mirrored margins, journal fonts and sizes per label, images and tables fitted to the
   text width — and LibreOffice makes the PDF. Tables, footnotes, images and Indian scripts are kept.
   "Author's style" changes only page size and margins. PDF articles are inserted unchanged (scaled
   to the page size if needed, with a warning when body text would fall below 9 pt).
5. **Assembly** (`assembler/`): front matter (title page, imprint, editorial board, contents),
   articles and optional back matter, with blank-page balancing (each part starts on a set side),
   roman/arabic numbering and a contents page iterated until its page count is stable.
6. **Outputs** (`outputs/`, `cover/`, `pdfops/`):
   - electronic issue: page labels matching printed numbers, bookmarks, clickable contents and DOI
     links, metadata; blank pages removed by default;
   - per-article PDFs cut from the issue, so page numbers match;
   - print interior: glue mode in page order (even count), staple mode imposed two-up on A4 (A5
     journal) or A3 (A4 journal) in booklet order (multiple of 4); gutter shift; optional grayscale;
   - covers: staple fold sheet; glue wrap (back | spine | front) with bleed, crop and fold marks on
     A3, spine = sheets × paper thickness + glue allowance (or a measured stack);
   - calibration sheets (100 mm rulers, unprintable edge, duplex flip arrows);
   - offprints with cover, publication details, "how to cite", original page numbers and side.
7. **Checks** (`checks/validation.py`): missing journal/issue/article data, ISSN and ORCID check
   digits, DOI suffix warnings, duplicate articles across issues, abstract length, small scaled text.
   Every export writes `output/export_log.txt`.

Page numbers, running headers and the first-page citation line are drawn with ReportLab and laid
over the pages with pikepdf, so they look the same on Word-built and PDF articles.

## Data on disk

```
<Journal folder>/
  journal.json
  assets/                      logo
  issues/vol1-issue2/
    issue.json                 issue details, layout, print, cover and export settings
    assets/                    cover pictures
    originals/                 copies of the submitted files
    work/                      converted and laid-out files (can be deleted; rebuilt as needed)
    articles/<id>/article.json labels, details, review status
    output/                    PDFs and export_log.txt
```

## Book publishing (new)

The **Book Publishing** tab provides a separate workflow for edited volumes and authored monographs.
It stores books independently from journal issues, so existing journal data and workflows are not changed.

- Create a book library and individual book projects.
- Record title, subtitle, publisher, publication place/year, edition, language, subject, print/digital ISBN,
  copyright details, trim size and series information.
- Maintain editor, author and contributor records (affiliation, email, ORCID and biography fields in the data model).
- Import multiple DOC, DOCX, ODT, RTF and PDF chapter files. Submitted originals are copied unchanged.
- Edit chapter titles and author bylines, reorder chapters, and choose which chapters to include.
- Add dedication, epigraph, foreword, preface, acknowledgements, introduction, appendices, glossary,
  consolidated bibliography and index material.
- Generate a single PDF with title page, publication-details page, contents, contributor list, optional
  front/back matter, and the selected chapters in the saved order.
- Validate ISBN-13 check digits before saving book details. ISBNs are recorded, not assigned by the app;
  publishers must obtain them through the relevant ISBN agency.

The first implementation deliberately focuses on compiling edited volumes from supplied chapter files.
Chapter source formatting is retained rather than re-typeset. Printer-specific cover wraps/spine calculations,
full print-imposition controls, automated index generation, EPUB output, detailed page-numbering schemes,
and automatic chapter-reference consolidation are not yet included. The book workflow is separate from
journal publishing and does not alter existing journal folders.

## Development

```
python -m pip install -e ".[dev]"
python -m pytest                     # unit, pipeline (needs LibreOffice) and window tests
python -m issuebuilder doctor        # checks LibreOffice, Ghostscript and the libraries
python -m issuebuilder               # opens the program window
python samples/make_samples.py out/  # invented sample articles (DOCX, ODT, PDF, Malayalam)
```

## Building the installers

The workflow `.github/workflows/build.yml` runs when the version number in
`src/issuebuilder/__init__.py` changes (or when started from the Actions tab). It runs the
tests on Windows and Ubuntu, builds the program with PyInstaller (`packaging/build_app.py`), makes
the Windows installer with Inno Setup (`packaging/windows/installer.iss`, per-user install, no
administrator rights) and the Ubuntu package (`packaging/linux/build_deb.sh`), and publishes both
as a GitHub release tagged `v<version>`.

## Changes from the blueprint's technology choices

- pikepdf, ReportLab, pdfplumber and pypdfium2 are used instead of PyMuPDF, and LibreOffice lays out
  the articles instead of Pandoc and Typst. All PDF work stays in `pdfops/`, as the blueprint asks.
- Articles are restyled from the author's own Word file rather than rebuilt from extracted text,
  which keeps tables, footnotes, images and complex scripts.

See THIRD_PARTY_NOTICES.md for the components and their licences.
