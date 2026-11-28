import hashlib
import json
import lzma
from pathlib import Path

import pikepdf


GOLDEN = Path(__file__).parent / "golden"
INFO = json.loads((GOLDEN / "sample_issue_v1.json").read_text(encoding="utf-8"))


def test_compressed_golden_pdf_is_lossless_and_matches_manifest(tmp_path):
    data = lzma.decompress((GOLDEN / "sample_issue_v1.pdf.xz").read_bytes())
    assert hashlib.sha256(data).hexdigest() == INFO["pdf_sha256"]

    path = tmp_path / "sample_issue_v1.pdf"
    path.write_bytes(data)
    with pikepdf.open(path) as pdf:
        pages = len(pdf.pages)
        links = sum(len(page.obj.get("/Annots", [])) for page in pdf.pages)
    assert pages == INFO["electronic_pages"]
    assert links == INFO["link_annotations"]
