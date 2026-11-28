# Journal Issue Builder — Project Blueprint

Offline desktop software (Windows and Linux) that turns submitted articles in mixed formats into a finished journal issue: one electronic PDF, print-ready files, and single-article offprints.

Version: 0.2.0 (implementation status updated 2026-11-28). The software is a working first version;
the original plan below has been reconciled with the implementation and remaining validation work.

## Current implementation status

The repository contains a working journal workflow, GUI, export pipeline, Linux and Windows
packaging, and a separate book workflow. The module requirements below describe the intended
product; the status here records what has actually been implemented and what still needs evidence.

| Area | Software status | Still needed |
|---|---|---|
| Journal and issue setup, import, analysis and review (M1–M5) | Implemented; tracked changes/comments are cleaned in working copies; review supports label, merge, edit and split with a correction log. | Validate analyzer quality on 10–20 real anonymised manuscripts; synthetic samples do not meet this criterion. |
| Article layout and issue assembly (M6–M8) | Implemented with LibreOffice restyling of a copy of the submitted Word file; assembly, contents, page balancing, font profiles and inside-cover matter are present. A 31-page synthetic issue PDF now serves as a regression baseline for page count, contents entries/page numbers, bookmarks and links. | Visual fidelity across author files and multilingual scripts needs real samples. The planned Pandoc/Typst rebuild is a documented technology change. |
| Covers (M9) | Image and generated covers, editable solid/pattern backgrounds, cover text overlays, back-cover details, spine and mark controls are implemented. | Confirm trim, bleed, fold, and binder measurements using printed samples and the intended binder. |
| Print outputs (M10) | Staple/glue output, imposition, grayscale choice, per-paper duplex/flip/color profiles, 100% scale guidance, crop/fold marks, calibration sheets and thickness warning are implemented. | Print calibration and booklet/fold checks on the actual A5/A4/A3 printer are outstanding. |
| Electronic PDF (M11) | Bookmarks, contents/DOI/site/email links, page labels, metadata, optional proof watermark, Ghostscript PDF/A-2b conversion, and an unembedded-font report are implemented. A 31-page, five-article synthetic issue passed veraPDF 1.30.4 PDF/A-2b validation (144 rules, 249,153 checks, no failures); its contents page was visually compared before and after conversion. The check also found and fixed missing flags on restored links. | Repeat PDF/A validation on an author-approved real issue and inspect its visual fidelity and links after conversion. |
| Offprints (M12) | Single and batch electronic/print offprints preserve article numbering/parity and include publication details and the editorial masthead. | Confirm sample page ranges and booklet output on a printer. |
| Validation (M13) | Journal/issue/article, DOI, ISSN/ORCID, duplicates, abstract, scaled text, image resolution and script-font checks are implemented. | Automated visual checks for dark grayscale images and physical page-count/print behavior still need print samples. |
| GUI and packaging (M14–M15) | Workflow screens, screen-fitted resizable window, explicit minimize/maximize/restore menu, refreshed light theme, click-only type-size fields with a restore-defaults action, and Windows/Linux package build/install self-check steps are implemented. The existing release workflow builds on versioned main pushes or a manual run. | Perform a clean-machine install check before release. |

The owner-provided sample issue contains nine original PDF files. A local read check accepted seven
as text-readable and correctly flagged two scans; four of the readable PDFs exposed unmapped-glyph
placeholders, so PDF import now suppresses unreliable metadata suggestions and asks the editor to
enter them manually. These meeting-minute PDFs do not satisfy the 10–20 anonymised academic
manuscript gate. Validation on an author-approved journal article and physical print/binding checks
remain open and require approved files and printer/binder access. A synthetic golden issue and
independent veraPDF validation are now present.

---

## 0. How to use this document with an AI coding assistant

This file is the single source of truth. Give it to any AI assistant (for example the one inside VS Code) together with the prompt below.

**Starter prompt**

> Read BLUEPRINT.md fully, including the current implementation status. Work on the incomplete item I name. Before writing code, restate the acceptance criteria and list the files you will change. Do not claim real-sample or print acceptance until those checks have actually happened. If something is unclear, ask or propose a small experiment instead of guessing.

**Rules for the assistant**

1. Python 3.11 or newer. Cross-platform: no Linux-only or Windows-only paths or commands. Use `pathlib`.
2. Every external program (LibreOffice, Ghostscript) is called through one wrapper module, with a clear error if it is missing.
3. All measurements are in millimetres in the settings and code. Convert to points only inside layout code.
4. Never modify the author's original files. Work on copies in the issue project folder.
5. Every number in section 7 is a **default setting**, not a constant. Put them in a settings file.
6. Anything marked **VERIFY** must be tested on a real sample before being trusted.
7. Keep the code simple enough for a beginner to read. Comment the why, not the what.
8. Target architecture: keep low-level PDF operations in the `pdfops` module. Cover, output, and book-export modules use the shared PDF helpers.

**For the project owner (new to coding):** work in VS Code, commit to Git after every working milestone, and test with real articles from your authors as early as possible.

---

## 1. Purpose and scope

### 1.1 Goals

- Accept articles in DOC, DOCX, ODT and readable PDF.
- Detect the parts of each article (title, authors, ORCID, institution, abstract, keywords, headings, body, references), suggest labels, and let the editor correct them.
- Rebuild Word-type articles in one journal template; pass PDFs through unchanged.
- Assemble one issue: cover, front matter, contents page, articles, back matter, with continuous page numbers and balanced left/right pages.
- Produce an electronic PDF and, when needed, print files for A5 or A4, stapled or glue-bound.
- Produce a single-article print or PDF (offprint) carrying the issue's cover and editorial details.
- Run offline on Windows and Linux.

### 1.2 Non-goals (first versions)

- Submission, peer review, plagiarism checking (use a separate system such as Open Journal Systems).
- Online publishing, DOI registration (the software only stores and prints the DOI; it can later export metadata).
- Automatic perfect rebuilding of tables, equations, footnotes and figures (these are flagged and may be kept from the original).
- Deep-learning metadata extraction from PDFs (GROBID was considered and rejected as too heavy).

### 1.3 Context

- Dual journal: electronic version is primary, print is occasional.
- Primary page size A5; A4 supported.
- Own printer prints A5, A4 and A3. Interior is black and white; only the cover is colour.
- Binding: mostly staples (saddle stitch); sometimes professional glue binding (the editor prints the pages and hands them to the binder).
- Possible multilingual content (for example Malayalam): fonts must support it (see section 7.4).

---

## 2. Glossary

| Term | Meaning |
|---|---|
| Recto | Right-hand page. Odd page numbers. |
| Verso | Left-hand page. Even page numbers. |
| Spine | The folded middle part of a cover wrap, between back and front cover. |
| Gutter | Extra inner margin on the binding side. |
| Imposition | Reordering pages onto sheets so a folded booklet reads in order. |
| Offprint | One article printed separately with the journal's cover and editorial pages. |
| Bleed | Extra printed area beyond the trim line (suggested 3 mm) for cover colour. |
| Block | One labelled piece of an article (title, paragraph, heading, and so on). |
| Leaf / sheet | One physical sheet. It has two pages. |

---

## 3. Architecture

```
 Submitted files (doc, docx, odt, pdf)
            │
   [Importer]  LibreOffice (headless) converts doc/odt → docx
            │
   [Analyzer]  python-docx reads styles/bold/size → labelled blocks (JSON)
            │         pdfplumber reads PDFs → suggested metadata only
   [Review screen]  editor corrects labels  → saved next to article
            │
   [Builder]   Copy of Word file restyled by python-docx → LibreOffice → article PDF
            │         (PDF submissions are passed through unchanged)
   [Assembler] front matter + contents + blank-page rules + page numbers
            │
   [Outputs]   Electronic PDF │ Print: staple / glue │ Cover │ Offprints
```

### 3.1 Technology stack

| Job | Tool | Licence (from general knowledge — VERIFY before distributing) |
|---|---|---|
| Word reading and editing | python-docx | MIT |
| Word page layout and conversion | LibreOffice Writer | MPL 2.0 |
| PDF structure and merge | pikepdf | MPL 2.0 |
| PDF text/image inspection | pdfplumber and pdfminer.six | MIT / MIT |
| PDF preview rendering | pypdfium2 | Apache 2.0 |
| PDF overlays and generated matter | ReportLab | BSD |
| Grayscale conversion (optional, separate program) | Ghostscript | AGPL 3.0 (or paid commercial) |
| OCR for scanned PDFs (optional) | OCRmyPDF + Tesseract | MPL 2.0 / Apache 2.0 |
| GUI | PySide6 | LGPL |
| Packaging | PyInstaller | GPL with packaging exception |
| Fonts | Tinos, Arimo, Gelasio, Noto family, TeX Gyre | open font licences |

**Implementation decision:** the shipped software uses pikepdf, pdfplumber, pypdfium2 and ReportLab,
and uses LibreOffice to lay out restyled Word copies. The planned Pandoc/Typst pipeline was not
implemented. Low-level pikepdf operations are isolated in `pdfops`; cover, output, and book-export
modules use the shared helpers. Ghostscript
is optional and used for grayscale conversion and PDF/A-2b conversion. PDF/A conversion depends on
Ghostscript's installed definition file and an available sRGB ICC profile; it uses strict
compatibility mode and still needs independent validation. The project remains
AGPL-3.0; see `THIRD_PARTY_NOTICES.md` for distribution notices and sources.

### 3.2 External programs

- LibreOffice: must be installed by the user. The app checks for it at start-up and explains how to install.
- Ghostscript: optional, for grayscale conversion. Detect it at start-up and explain when grayscale conversion is unavailable.

### 3.3 Folder structure (repository)

```
journal-issue-builder/
  README.md
  BLUEPRINT.md
  pyproject.toml
  src/issuebuilder/
    settings/        models.py, defaults.py, load_save.py
    tools/           libreoffice.py, ghostscript.py        (wrappers)
    importers/       convert.py, docx_reader.py, pdf_reader.py
    analyzer/        blocks.py, rules.py, orcid.py, confidence.py
    builder/         typst_render.py, article_template.typ, front_matter.typ
    assembler/       blank_pages.py, contents.py, numbering.py, issue.py
    cover/           spine.py, wrap.py, stapled.py
    pdfops/          merge.py, stamp.py, bookmarks.py, imposition.py, grayscale.py
    outputs/         electronic.py, print_glue.py, print_staple.py, offprint.py, calibration.py
    checks/          validation.py
    gui/             app.py, screens/
  fonts/
  templates/
  samples/           (real anonymised articles; never commit private ones)
  tests/
  docs/
```

### 3.4 Project data on disk

One folder per issue, plain JSON files so everything can be inspected and recovered:

```
MyJournal/
  journal.json                  publication details (section 5.1)
  issues/vol1-issue2/
    issue.json                  volume, issue, date, article order, settings overrides
    originals/                  untouched submitted files
    work/                       converted and rebuilt files
    articles/<id>/article.json  metadata + labelled blocks + review status
    output/                     final PDFs
```

**article.json (example)**

```json
{
  "id": "a03",
  "source_file": "originals/smith_paper.docx",
  "type": "Research article",
  "title": "Example title",
  "subtitle": "",
  "authors": [
    {"name": "A. Smith", "orcid": "0000-0002-1825-0097",
     "affiliation": "Dept. of X, University Y", "email": "a@x.org",
     "order": 1, "corresponding": true}
  ],
  "abstract": "…", "keywords": ["a", "b"],
  "dates": {"received": "2026-05-01", "accepted": "2026-08-10", "published": "2026-11-01"},
  "doi": "",
  "blocks": [
    {"i": 0, "text": "Example title", "label": "title", "confidence": 0.97, "confirmed": true}
  ],
  "review_status": "needs_review",
  "keep_original": false,
  "start_page": null, "end_page": null
}
```

---

## 4. Output concepts

| Output | Purpose | Notes |
|---|---|---|
| Electronic issue PDF | Main product | No binding margin, no crop marks, colour allowed, bookmarks, clickable contents, metadata. |
| Electronic article PDFs | Online per-article files | Built from the issue so page numbers match. |
| Print interior, glue mode | For binder | Pages in normal order, even count. |
| Print interior, staple mode | For stapled booklet | Booklet (imposed) order, count multiple of 4. |
| Cover files | Printed in colour | Staple: folded sheet, no spine. Glue: flat wrap with spine. |
| Offprint | One article, author's copy | Section 6 (module M12). |
| Calibration sheet | Test print | Checks printer scale, margins, flip direction. |

---

## 5. Functional requirements

Each module has an ID, requirements, and acceptance criteria (AC).

### M1 — Publication settings (journal.json)

Fields: journal title, short title, abbreviation, print ISSN, electronic ISSN, publisher name, address, website, email, editor-in-chief, editors, editorial board (name, role, institution), frequency, aims and scope, peer-review statement, copyright text, licence (single setting used everywhere), logo image, default fonts profile, default page size, default binding mode.

- Changing the journal title shows a warning (an ISSN is tied to the title).
- DOI is optional at journal and article level. When present it is shown as `https://doi.org/<doi>`.

AC: settings save and reload; both ISSNs appear on cover, masthead and PDF metadata; licence text is identical everywhere.

### M2 — Issue project

- Create or open an issue (volume, issue number, month, year, optional issue title).
- Add articles by file picker or drag and drop; reorder by drag; remove.
- Per-article fields: type (research article, review, book review, editorial), received/accepted/published dates, corresponding author, optional DOI.
- An article can belong to only one issue.
- Originals are copied into `originals/` and never changed.

AC: reopening an issue restores order and all fields.

### M3 — Import and conversion

- Formats: `.doc`, `.docx`, `.odt`, `.pdf`.
- DOC and ODT are converted to DOCX with LibreOffice headless.
- Before reading a Word file: accept all tracked changes and remove comments, and warn that this was done. VERIFY: confirm LibreOffice or python-docx handles this reliably.
- Detect and report: password-protected, corrupt, empty, scanned (image-only) PDFs.
- A failing file never stops the whole issue; it shows in a list with a clear message.
- Optional later: OCR for scanned PDFs.

AC: a folder of mixed files imports with a per-file status; bad files are listed with reasons.

### M4 — Article analyzer (Word files)

Reads the DOCX and labels each block.

| Label | Rule (starting point) |
|---|---|
| title | First non-empty block, largest or bold, often centred, or Word style "Title" |
| subtitle | Directly after title, smaller or italic |
| author | Short lines after title, name-like, may carry superscript markers |
| orcid | Regex for 16 characters in 4 groups (last may be X) + checksum validation |
| email | Email pattern |
| institution | Words such as University, Department, Institute, College, School |
| abstract | Block after the word "Abstract" (also accept "Summary") |
| keywords | Block after "Keywords" or "Key words", comma or semicolon separated |
| heading1 / heading2 | Word heading styles; else short bold line without full stop |
| body | Everything else |
| references | All blocks after a heading "References" or "Bibliography" |
| other | Acknowledgements, funding, conflict of interest, and so on (by heading) |

- Each block gets a confidence score (0 to 1). Low confidence is highlighted.
- Authors: the order of appearance gives first, second, third author. Authors and affiliations are linked through markers (numbers, asterisks) when present.
- Abstract length warning above a configurable limit (default 250 words).
- Detect and flag: tables, images, footnotes, equations (these make automatic rebuild risky).
- Rules live in one file so they can be improved from real samples. Corrections are logged so rules can be tuned later.

AC: software behavior is implemented, but this criterion is **not yet demonstrated**: the repository does not contain the required 10–20 approved real sample articles.

### M4b — PDF articles

- Only suggest title, authors, abstract using font size and position (pdfplumber).
- The editor confirms title, authors, and start details manually.
- PDF pages are inserted unchanged. Check the effective font size after scaling and warn if the body would be below 9 pt.

### M5 — Review screen

- Left: article text blocks. Right: label dropdown per block, with confidence shading.
- Quick actions: set as title, subtitle, author, and so on; merge or split blocks; mark ignore.
- Per-article status: needs review, reviewed, keep original.
- Corrections saved immediately into `article.json`.

AC: a corrected article reloads with the same labels; changing a label updates the preview.

### M6 — Article builder

- Word-type articles: the current implementation edits a working copy of the submitted Word document using the reviewed labels and LibreOffice lays it out at the issue's page size and typography profile. This replaces the planned Pandoc/Typst rebuild.
- Title bold, author line with ORCID, institution lines, abstract, keywords, headings, body, references.
- Page numbering uses the issue's continuous numbers (the assembler supplies the start page).
- Articles flagged complex, or marked "keep original", are converted to PDF with LibreOffice and passed through (scaled only if the editor allows).
- VERIFY: fidelity of the restyled Word copy on tables, footnotes, images and complex scripts using real manuscripts.

AC: layout and rebuild-from-reviewed-block editing are implemented. Confirm body size and visual fidelity against real author manuscripts before treating this criterion as passed.

### M7 — Issue assembly

Order of an issue (each element can be switched on or off):

1. Front cover (outside)
2. Inside front cover (blank, notes or advertisement)
3. Title page
4. Copyright and imprint (verso)
5. Editorial board and masthead
6. Contents page
7. Editorial (if any)
8. Articles
9. Author index (optional), notes for authors (optional)
10. Inside back cover, back cover

**Contents page:** article title, authors, start page. Built automatically from reviewed data and real page counts. Entries are clickable in the electronic PDF.

**Page numbering:** front matter in roman numerals (setting), articles continue in arabic from 1 (or as set), continuous across the issue.

**Blank-page balancing (important):** each element has a "starts on" setting: right, left, or any. The assembler inserts a blank page whenever the next element would start on the wrong side.

Defaults:

| Element | Starts on |
|---|---|
| Title page | right |
| Copyright and imprint | left |
| Contents | right |
| Editorial and masthead | right |
| Each article | right (option: any) |
| Author index, notes for authors | right |

Blank pages: counted, not numbered, no header or footer; optional "This page intentionally left blank"; optional filler content (call for papers, notes for authors).

**End padding:** glue mode pads to an even page count; staple mode pads to a multiple of 4.

AC: no element starts on the wrong side for any combination of article lengths (unit-tested); the total is even or a multiple of 4 as required.

### M8 — Typography and page profiles

Two editable profiles (A5, A4) and font profiles. Default values in section 7. The software never shrinks A4 content to make A5 (it rebuilds at A5). It warns if any scaled PDF text falls below 9 pt.

AC: switching the issue to A5 or A4 reloads sizes, margins and the gutter; a rebuilt article shows the new sizes.

### M9 — Cover

**Inputs:** front cover image (usually A4 portrait; same proportions as A5, so scales exactly), back cover content (generated from journal settings or uploaded), spine text (journal short title, volume, issue, year).

**Staple mode:** one landscape A4 sheet for an A5 journal (A3 landscape for an A4 journal), back cover on the left, front cover on the right, a fold mark in the middle, no spine.

**Glue mode:** flat wrap = back cover | spine | front cover.

- Wrap width = 2 × page width + spine width (+ 2 × bleed if trimming)
- A5 journal: 296 mm + spine, height 210 mm, printed on A3, then trimmed
- A4 journal: wrap does not fit A3; the software warns and offers separate front and back cover pages (and a spine strip)
- Spine width = (interior pages ÷ 2) × paper thickness per sheet + glue allowance
- Spine text only when the spine is at least 5 mm (setting); otherwise blank with a warning
- Fold and trim marks are drawn clear of the printer's unprintable edge
- The spine is recalculated automatically whenever the page count changes
- Allow entering a measured stack thickness instead of the per-sheet value
- The cover is a separate colour PDF

AC: for 80, 120 and 200 interior pages the spine matches the formula to 0.1 mm; the wrap dimensions are printed in the file name or on a cover info page.

### M10 — Print outputs

**Binding mode** setting changes page rules, margins and cover together.

| | Staple (saddle stitch) | Glue (professional binding) |
|---|---|---|
| Page count | multiple of 4 | even |
| Order | booklet (imposed) | normal |
| Interior paper (A5 journal) | A4, two pages per sheet, duplex, folded | A5, one page per sheet, duplex |
| Cover paper | A4 landscape, folded | A3 wrap, trimmed |
| Gutter default | about 5 mm | about 12–15 mm |

- Interior defaults to grayscale, configurable by paper profile (Ghostscript, optional; if it is missing, warn and export without conversion). Low image resolution is reported; grayscale darkness still requires visual print review.
- Mirrored margins: the inner margin flips on right and left pages.
- Print profiles for A5, A4, A3: duplex on/off, flip edge, scale locked at 100 percent (never fit to page), unprintable edge (default 5 mm), crop and fold marks on/off, colour or black and white.
- **Calibration sheet** per paper size: a 100 mm ruler, edges, and flip arrows.
- Stapled thickness warning above a set page count (default about 60 pages for an ordinary stapler).

AC: the booklet order test in section 6.3 passes; a printed calibration sheet measures 100 mm.

### M11 — Electronic output

- Single PDF with bookmarks per article and per front-matter section, clickable contents, clickable DOI and web links, PDF metadata (title, journal, volume, issue, ISSN, authors).
- No gutter and no crop marks. Colour allowed.
- Option: remove blank pages while keeping the printed page numbers (default on); option to keep them.
- Export checks report fonts that are not embedded. Generated overlay and front-matter fonts are embedded by their PDF generators; source PDFs may retain non-embedded fonts.
- Optional PDF/A-2b output is made with Ghostscript strict compatibility mode and an sRGB ICC profile. Validate each file with veraPDF before relying on conformance.

AC: PDF opens with working bookmarks and links; page labels match the printed numbering.

### M12 — Offprints (single-article print)

Contents of an offprint, in order:

1. Front cover (issue cover, optional "Offprint" line and author name)
2. Editorial and publication details (masthead, publisher, volume and issue, ISSN, copyright, licence)
3. The article itself, with its **original page numbers** (default), so citations stay correct
4. Back cover

- Option: renumber from 1.
- Left/right parity of the article is preserved; blank pages are inserted by the same rules.
- Optional "How to cite" line.
- Outputs: electronic offprint PDF, or print offprint (default staple mode, imposed, multiple of 4).
- **Batch:** one offprint per article, named `volX-issueY_Surname_ShortTitle.pdf`.
- Built from the finished issue, not rebuilt.

AC: an offprint of an article on pages 45–62 shows pages 45–62, begins on the correct side, and prints in correct booklet order.

### M13 — Validation and checks (run before export)

Block export (error) or warn:

- Missing journal title, ISSNs, volume, issue, date (error)
- Article without title or author (error)
- Article dates missing (warn)
- DOI suffix contains initials, date, ISSN, issue or page numbers (warn)
- Licence text missing or inconsistent (error)
- Abstract over the limit (warn)
- Image resolution too low for print (warn)
- Article assigned to more than one issue (error)
- Scaled PDF text below 9 pt (warn)
- Page count not valid for binding mode (auto-fixed with blank pages; log it)
- Missing fonts for a script found in text (warn)

Also: a "PROOF" watermark option for author proof PDFs, removed in the final export.

### M14 — GUI

Screens: Journal settings; Issue (article list); Review; Layout (page size, fonts, margins, header and footer, page-number position); Cover; Print (binding mode, paper, profiles); Export (checks, outputs, progress); Offprints. Buttons for volume and issue number as requested. Long jobs run in the background with a progress bar. Interface language: English.

Header and footer settings: text for left and right pages (default: short journal title on left pages, short article title on right pages), page number position (centre, outside, bottom-right), first page of each article without header (option).

### M15 — Packaging

- PyInstaller builds for Windows and Linux; CI installs the generated Windows installer and Linux package and runs their self-checks.
- Installer or first-run check for LibreOffice, with clear instructions.
- Fonts used by the program are packaged where applicable; LibreOffice is installed separately.
- Include licence notices and source offers for bundled GPL and MPL tools.

---

## 6. Key algorithms

### 6.1 Spine and cover wrap

```
sheets        = ceil(interior_pages / 2)
spine_mm      = sheets * paper_thickness_mm + glue_allowance_mm
wrap_width_mm = 2 * page_width_mm + spine_mm + 2 * bleed_mm   (bleed only if trimming)
wrap_height_mm= page_height_mm + 2 * bleed_mm
# A5: page_width 148, page_height 210
```
Example with 0.1 mm paper and 0.5 mm glue: 80 pages → 4.5 mm, 120 → 6.5 mm, 200 → 10.5 mm.

### 6.2 Blank-page balancing

```
physical page 1 (first page after the outside cover) is a RECTO (right).
parity(p) = right if p is odd else left

for element in issue_elements_in_order:
    if element.starts_on in ("right", "left"):
        if parity(next_page_number) != element.starts_on:
            insert one blank page
    place element (it occupies element.page_count pages)

if binding_mode == "glue":   pad blank pages until total is even
if binding_mode == "staple": pad blank pages until total % 4 == 0
```
The same function is used for the electronic version (when blanks are kept), print files and offprints. Unit-test with elements of 1 to 9 pages in many combinations.

### 6.3 Booklet imposition (saddle stitch)

For N pages, N divisible by 4. Sheets k = 0 … N/4 − 1. Each sheet has a front and a back side, each holding a left and a right page:

```
front: left = N - 2k      right = 1 + 2k
back : left = 2 + 2k      right = N - 1 - 2k
```
Check with N = 8: sheet 0 front 8|1, back 2|7; sheet 1 front 6|3, back 4|5. The test must assert this exact result. Also record the duplex flip edge (for landscape sheets, usually short edge — VERIFY on the real printer with the calibration sheet).

### 6.4 ORCID validation

```
total = 0
for digit in first 15 digits: total = (total + digit) * 2
result = (12 - (total % 11)) % 11
check = "X" if result == 10 else str(result)
valid if check == 16th character
```
Test value: `0000-0002-1825-0097` is valid.

### 6.5 Contents page numbers

1. Build every article PDF; count its pages.
2. Walk the issue order with the blank-page function, assigning each article a start page.
3. Render the contents page; if it changes the page count, repeat once until stable.

### 6.6 Effective font size for scaled PDFs

`effective_pt = original_pt * (target_page_width / original_page_width)`. A4 → A5 is 0.707, so 11 pt becomes 7.8 pt. Warn below 9 pt.

---

## 7. Default settings (all editable; VERIFY by test prints)

### 7.1 A5 profile (148 × 210 mm)

| Element | Default |
|---|---|
| Body | 11 pt on 14 pt lines, serif, justified |
| Article title | 14–15 pt bold |
| Heading 1 / 2 | 12 pt bold / 11 pt bold italic |
| Abstract, keywords | 10 pt |
| Footnotes, references | 9 pt |
| Header / footer text | 8 pt |
| Page number | 9 pt |
| Margins top / bottom / inside / outside | 18 / 20 / 20 / 15 mm |

This gives about 113 mm text width, roughly 60–65 characters per line at 11 pt.

### 7.2 A4 profile (210 × 297 mm)

| Element | Default |
|---|---|
| Body | 11 or 12 pt on 14–15 pt lines |
| Article title | 16 pt bold |
| Heading 1 / 2 | 13 pt bold / 12 pt bold italic |
| Abstract, keywords | 10 pt |
| Footnotes, references | 9–10 pt |
| Header / footer text | 9 pt |
| Page number | 10 pt |
| Margins top / bottom / inside / outside | 25 / 25 / 28 / 22 mm (or two-column option) |

### 7.3 Physical settings

| Setting | Default |
|---|---|
| Paper thickness per sheet (80 gsm) | 0.1 mm (measure real paper) |
| Glue allowance | 0.5 mm |
| Bleed | 3 mm |
| Unprintable edge | 5 mm (check printer) |
| Gutter, staple | about 5 mm |
| Gutter, glue | about 12–15 mm (grows with page count) |
| Min spine for text | 5 mm |
| Abstract word limit | 250 |
| Min scaled body text | 9 pt |
| Min image resolution (print) | about 300 dpi |

### 7.4 Fonts

Maximum two families per journal. Bundle open-licence fonts and embed them in every PDF.

| Profile | Body | Headings and headers |
|---|---|---|
| Classic (default) | Tinos (Times-like) | Arimo (Helvetica or Arial-like) |
| Book style | TeX Gyre Pagella (Palatino-like) | TeX Gyre Heros |
| Modern | Gelasio or Source Serif 4 | Arimo |
| Indian scripts | User-mapped script fonts (Manjari included for Malayalam), with Noto fallbacks | User-mapped script fonts, with Noto fallbacks |

Text blocks in another script use the font mapped to that script in Layout, then fall back to Noto. Users can import local OTF/TTF/TTC files and map them by script.

---

## 8. Quality, safety and robustness

- Originals are read-only copies; outputs go to a separate folder.
- A failed article never blocks the rest.
- Every export writes a small log (settings used, page counts, warnings).
- Settings and issue files carry a version number for future upgrades.
- A "use original without rebuilding" option exists for every article.

---

## 9. Testing plan

1. **Sample set (outstanding):** collect 10–20 real, anonymised articles (DOC, DOCX, ODT, PDF; some with tables, images, footnotes, tracked changes; one scanned PDF; one Malayalam). Generated samples exercise the pipeline but do not satisfy this check.
2. **Unit tests:** spine formula, wrap size, blank-page balancing, booklet order, ORCID check, contents page numbers, effective font size.
3. **Golden files:** a generated 31-page reference PDF and JSON page-number manifest now guard the issue pipeline (`tests/golden/`). The baseline is synthetic; compare it and later real-issue references after changes.
4. **Print tests (outstanding):** print the calibration sheet on A5, A4 and A3; print one stapled A5 booklet and fold it; fold a cover; measure a stack for the spine; do a trial with the binder.
5. **Cross-platform:** the GitHub Actions workflow builds and installs packages on Linux and Windows; confirm passing runs for each release.

---

## 10. Risks and open items

| Item | Action |
|---|---|
| Restyled Word fidelity on complex files | Test with real manuscripts; keep the "keep original" fallback |
| PDF/A conformance | Ghostscript PDF/A-2b output passed veraPDF 1.30.4 (144 rules, 249,153 checks) on the generated 31-page issue. Repeat on a real journal issue before release. |
| Duplex flip direction for imposed sheets | VERIFY with the calibration sheet |
| Binder requirements (spine formula, bleed, cover format) | Ask the binder before first glue-bound issue |
| Printer unprintable edge and A3 margins | Measure with calibration sheet |
| Reference style (numbered or author-year), single "References" heading | Decide per journal |
| ISSN rules vary by country | Check with the national ISSN centre |
| Windows build | CI builds and installs on a Windows runner; confirm CI success before each release. |
| Multilingual content | Decide the languages and test the fonts |
| Licences | Re-check every bundled tool before distributing |

Later ideas: exporting article metadata for indexing services (for example Crossref XML), automatic DOI lookup in reference lists, learning from reviewer corrections, OCR for scans, an optional PDF header extraction add-on.

---

## 11. Milestones

This table records the original planned sequence. The shipped implementation followed a changed
sequence; use the current implementation status table at the beginning of this document for its
actual state. Historical milestones do not imply their real-sample or physical acceptance checks passed.

| # | Milestone | Deliverable | Done when |
|---|---|---|---|
| 0 | Project setup | Repo, `pyproject.toml`, folder structure, tool-wrapper modules, a check that LibreOffice, Pandoc and Typst are found | `python -m issuebuilder doctor` reports status on Windows and Linux |
| 1 | Formulas | `spine.py`, `blank_pages.py`, `imposition.py`, `orcid.py` with unit tests | All tests in section 9.2 pass |
| 2 | Convert and merge | LibreOffice conversion of DOC/ODT/DOCX to PDF; merge several files with continuous page numbers; A5 or A4 | A folder of mixed files becomes one numbered PDF |
| 3 | Typst pipeline test | One DOCX → Pandoc → Typst → A5 PDF with mirrored margins | Visual check at real size |
| 4 | Journal settings and front matter | `journal.json`, title page, copyright page, masthead, contents page (automatic) | Front matter appears with correct page numbers |
| 5 | Issue assembly | Blank-page rules, roman and arabic numbering, headers and footers | No element on the wrong side; contents match |
| 6 | Electronic output | Bookmarks, links, metadata | Opens correctly in a PDF reader |
| 7 | Print outputs | Gutter, glue mode, staple mode with imposition, grayscale, print profiles, calibration sheet | Real print test passes |
| 8 | Covers | Staple fold sheet, glue wrap with spine, trim marks | Real cover test passes |
| 9 | Offprints | Single-article outputs and batch | Original page numbers preserved |
| 10 | Analyzer and review screen | Labelling rules, confidence, review UI, saved corrections | Section M4 acceptance test on the sample set |
| 11 | Article rebuild | Rebuild Word-type articles from labelled blocks | Output matches journal template |
| 12 | GUI | All screens | Whole workflow without the command line |
| 13 | Checks and polish | Validation list, proof watermark, logs | All checks implemented |
| 14 | Packaging | Windows and Linux installers | Installs on a clean machine |

Milestones 1–9 give a complete assembly tool using the articles as they arrive. Milestones 10–11 add the smart article analysis and rebuilding.

---

## 12. Prompt starters per milestone

- **Milestone 1:** "Implement `spine.py`, `blank_pages.py`, `imposition.py` and `orcid.py` exactly as in section 6, with pytest tests. Do not add anything else."
- **Milestone 2:** "Implement conversion with LibreOffice headless through the wrapper in `tools/libreoffice.py`, and merge with PyMuPDF, adding continuous page numbers with a settings-driven position. Command-line only."
- **Milestone 3:** "Write a minimal Typst template for A5 with `inside` and `outside` margins and run one DOCX through Pandoc and Typst. Report what Pandoc loses (tables, footnotes, images)."
- **Milestone 7:** "Implement glue mode and staple mode print outputs and the calibration sheet. Use section 6.3 for imposition. Add a test that checks N = 8 and N = 12."
- **Milestone 10:** "Implement the analyzer rules in section M4 as small, separate functions with tests on the files in `samples/`. Every label gets a confidence score."

---

## 13. Licence and credits

Licence of this project: **GNU Affero General Public License v3.0 (AGPL-3.0)**. The implementation
uses components with different licences, including Ghostscript (AGPL) and pikepdf (MPL); do not
infer component licensing from the project licence. Verify each bundled component's licence and
distribution obligations before release, and keep `THIRD_PARTY_NOTICES.md` current. Never commit
real author manuscripts or private data: keep them in a folder listed in `.gitignore`.
