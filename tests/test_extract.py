from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from prospectus_sentence_indexer.extract import DocxExtractor, normalize_whitespace, reconstruct_check
from prospectus_sentence_indexer.models import BlockType

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _make_docx(tmp_path: Path, parts: dict[str, str]) -> Path:
    docx_path = tmp_path / "sample.docx"
    with ZipFile(docx_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("_rels/.rels", "<Relationships></Relationships>")
        for part, xml in parts.items():
            archive.writestr(part, xml)
    return docx_path


def _doc_xml(paragraphs: list[str], extra_body: str = "") -> str:
    para_xml = "".join(
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs
    )
    return (
        f"<w:document xmlns:w=\"{W_NS}\"><w:body>{para_xml}{extra_body}</w:body></w:document>"
    )


def test_normalize_whitespace() -> None:
    assert normalize_whitespace("  A\t\n  B   C ") == "A B C"


def test_reconstruct_check_pass() -> None:
    raw = "A   sentence.   Another one."
    assert reconstruct_check(raw, ["A sentence.", "Another one."])


def test_reconstruct_check_fail() -> None:
    raw = "A sentence. Another one."
    assert not reconstruct_check(raw, ["A sentence.", "Another"])


def test_extract_from_minimal_docx(tmp_path: Path) -> None:
    docx_path = _make_docx(
        tmp_path,
        {"word/document.xml": _doc_xml(["First paragraph.", "Second paragraph."])},
    )

    blocks = DocxExtractor(str(docx_path)).extract()

    assert len(blocks) == 2
    assert [b.raw_text for b in blocks] == ["First paragraph.", "Second paragraph."]
    assert all(b.block_type == BlockType.PARAGRAPH for b in blocks)


def test_extract_includes_footnotes(tmp_path: Path) -> None:
    footnotes = (
        f"<w:footnotes xmlns:w=\"{W_NS}\">"
        "<w:footnote w:id=\"1\"><w:p><w:r><w:t>Footnote A.</w:t></w:r></w:p></w:footnote>"
        "</w:footnotes>"
    )
    docx_path = _make_docx(
        tmp_path,
        {
            "word/document.xml": _doc_xml(["Main."]),
            "word/footnotes.xml": footnotes,
        },
    )

    blocks = DocxExtractor(str(docx_path)).extract()

    assert any(b.block_type == BlockType.FOOTNOTE_PARAGRAPH for b in blocks)
    assert any(b.raw_text == "Footnote A." for b in blocks)


def test_extract_includes_endnotes(tmp_path: Path) -> None:
    endnotes = (
        f"<w:endnotes xmlns:w=\"{W_NS}\">"
        "<w:endnote w:id=\"1\"><w:p><w:r><w:t>Endnote A.</w:t></w:r></w:p></w:endnote>"
        "</w:endnotes>"
    )
    docx_path = _make_docx(
        tmp_path,
        {
            "word/document.xml": _doc_xml(["Main."]),
            "word/endnotes.xml": endnotes,
        },
    )

    blocks = DocxExtractor(str(docx_path)).extract()

    assert any(b.block_type == BlockType.ENDNOTE_PARAGRAPH for b in blocks)
    assert any(b.raw_text == "Endnote A." for b in blocks)


def test_extract_includes_textbox(tmp_path: Path) -> None:
    textbox = (
        "<w:p><w:r><w:drawing><wp:anchor xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\">"
        "<w:txbxContent><w:p><w:r><w:t>Textbox line.</w:t></w:r></w:p></w:txbxContent>"
        "</wp:anchor></w:drawing></w:r></w:p>"
    )
    docx_path = _make_docx(
        tmp_path,
        {"word/document.xml": _doc_xml(["Main."], extra_body=textbox)},
    )

    blocks = DocxExtractor(str(docx_path)).extract()

    assert any(b.block_type == BlockType.TEXTBOX_PARAGRAPH for b in blocks)
    assert any(b.raw_text == "Textbox line." for b in blocks)


def test_extract_excludes_headers_by_default(tmp_path: Path) -> None:
    header = f"<w:hdr xmlns:w=\"{W_NS}\"><w:p><w:r><w:t>Header A.</w:t></w:r></w:p></w:hdr>"
    docx_path = _make_docx(
        tmp_path,
        {
            "word/document.xml": _doc_xml(["Main."]),
            "word/header1.xml": header,
        },
    )

    blocks = DocxExtractor(str(docx_path)).extract()

    assert not any(b.block_type == BlockType.HEADER_PARAGRAPH for b in blocks)


def test_extract_includes_headers_with_flag(tmp_path: Path) -> None:
    header = f"<w:hdr xmlns:w=\"{W_NS}\"><w:p><w:r><w:t>Header A.</w:t></w:r></w:p></w:hdr>"
    docx_path = _make_docx(
        tmp_path,
        {
            "word/document.xml": _doc_xml(["Main."]),
            "word/header1.xml": header,
        },
    )

    blocks = DocxExtractor(str(docx_path), include_headers_footers=True).extract()

    assert any(b.block_type == BlockType.HEADER_PARAGRAPH for b in blocks)
    assert any(b.raw_text == "Header A." for b in blocks)


def test_extract_keeps_document_order(tmp_path: Path) -> None:
    mixed = (
        "<w:p><w:r><w:t>Intro.</w:t></w:r></w:p>"
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell text.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
        "<w:p><w:r><w:t>Outro.</w:t></w:r></w:p>"
    )
    docx_path = _make_docx(
        tmp_path,
        {"word/document.xml": f"<w:document xmlns:w=\"{W_NS}\"><w:body>{mixed}</w:body></w:document>"},
    )

    blocks = DocxExtractor(str(docx_path)).extract()

    assert [b.raw_text for b in blocks] == ["Intro.", "Cell text.", "Outro."]
    assert [b.block_type for b in blocks] == [
        BlockType.PARAGRAPH,
        BlockType.TABLE_CELL,
        BlockType.PARAGRAPH,
    ]
