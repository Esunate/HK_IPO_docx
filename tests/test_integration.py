from __future__ import annotations

import csv
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from prospectus_sentence_indexer.cli import main

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _make_docx(tmp_path: Path, include_header: bool = False) -> Path:
    document = (
        f"<w:document xmlns:w=\"{W_NS}\"><w:body>"
        "<w:p><w:r><w:t>Hello world.</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>Second sentence.</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    styles = (
        f"<w:styles xmlns:w=\"{W_NS}\">"
        "<w:style w:type=\"paragraph\" w:styleId=\"Heading1\"><w:name w:val=\"Heading 1\"/></w:style>"
        "</w:styles>"
    )
    header = f"<w:hdr xmlns:w=\"{W_NS}\"><w:p><w:r><w:t>Header A.</w:t></w:r></w:p></w:hdr>"

    docx_path = tmp_path / "input.docx"
    with ZipFile(docx_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("_rels/.rels", "<Relationships></Relationships>")
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)
        if include_header:
            archive.writestr("word/header1.xml", header)
    return docx_path


def test_cli_basic_run(tmp_path: Path) -> None:
    docx_path = _make_docx(tmp_path)
    out_dir = tmp_path / "out"

    code = main([str(docx_path), "--output-dir", str(out_dir)])

    assert code == 0
    assert (out_dir / "sentences.csv").exists()
    assert (out_dir / "sentences.docx").exists()
    assert (out_dir / "qa_report.csv").exists()
    assert (out_dir / "summary.json").exists()


def test_cli_params_include_headers(tmp_path: Path) -> None:
    docx_path = _make_docx(tmp_path, include_header=True)
    out_dir = tmp_path / "out"

    main([
        str(docx_path),
        "--output-dir",
        str(out_dir),
        "--include-headers-footers",
    ])

    with (out_dir / "sentences.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    assert all(row["block_type"] == "paragraph" for row in rows)


def test_end_to_end_summary(tmp_path: Path) -> None:
    docx_path = _make_docx(tmp_path)
    out_dir = tmp_path / "out"

    main([str(docx_path), "--output-dir", str(out_dir)])

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_blocks"] >= 1
    assert summary["total_sentences"] >= 1


def test_error_handling_missing_input(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([str(tmp_path / "missing.docx")])
    assert exc_info.value.code == 2


def test_cli_heading_style_map(tmp_path: Path) -> None:
    document = (
        f"<w:document xmlns:w=\"{W_NS}\"><w:body>"
        "<w:p><w:pPr><w:pStyle w:val=\"Title\"/></w:pPr><w:r><w:t>Company Overview</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>Body line.</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    styles = f"<w:styles xmlns:w=\"{W_NS}\"><w:style w:type=\"paragraph\" w:styleId=\"Title\"><w:name w:val=\"Title\"/></w:style></w:styles>"
    docx_path = tmp_path / "input.docx"
    with ZipFile(docx_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("_rels/.rels", "<Relationships></Relationships>")
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)

    style_map = tmp_path / "heading_style_map.json"
    style_map.write_text('{"Title": 1}', encoding="utf-8")
    out_dir = tmp_path / "out"

    main([str(docx_path), "--output-dir", str(out_dir), "--heading-style-map", str(style_map)])

    with (out_dir / "sentences.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["text"] == "Body line."
    assert rows[0]["heading_level"] == "0"
    assert rows[0]["heading_path"] == "Company Overview"
