from prospectus_sentence_indexer.models import Block, BlockType, QAReport, Sentence, Summary


def test_block_type_covers_required_values() -> None:
    values = {item.value for item in BlockType}
    assert values == {
        "paragraph",
        "table_cell",
        "textbox_paragraph",
        "footnote_paragraph",
        "endnote_paragraph",
        "header_paragraph",
        "footer_paragraph",
    }


def test_block_defaults_and_required_fields() -> None:
    block = Block(
        block_id="B000001",
        part="document.xml",
        block_type=BlockType.PARAGRAPH,
        raw_text="Sample text.",
    )

    assert block.block_id == "B000001"
    assert block.heading_level == 0
    assert block.heading_path == ""
    assert block.style_id is None
    assert block.para_id is None


def test_sentence_defaults() -> None:
    sentence = Sentence(
        sentence_id="S000001",
        block_id="B000001",
        part="document.xml",
        block_type=BlockType.PARAGRAPH,
        heading_level=1,
        heading_path="1 Business",
        text="This is a sentence.",
    )

    assert sentence.qa_flags == []
    assert sentence.is_fallback is False


def test_qareport_fields() -> None:
    report = QAReport(
        block_id="B000001",
        sentence_id="S000001",
        part="document.xml",
        block_type=BlockType.PARAGRAPH,
        heading_path="1 Business",
        issue="TOO_SHORT",
        details="Length=2",
        raw_excerpt="ab",
    )

    assert report.issue == "TOO_SHORT"
    assert report.details == "Length=2"
    assert report.raw_excerpt == "ab"


def test_summary_fields() -> None:
    summary = Summary(
        input_file="sample.docx",
        processing_time_seconds=1.25,
        total_blocks=10,
        total_sentences=16,
        block_type_counts={"paragraph": 8, "table_cell": 2},
        qa_issue_counts={"TOO_SHORT": 2},
        reconstruct_fail_count=1,
        fallback_sentence_count=1,
    )

    assert summary.input_file.endswith(".docx")
    assert summary.processing_time_seconds == 1.25
    assert summary.total_blocks == 10
    assert summary.total_sentences == 16
    assert summary.block_type_counts["paragraph"] == 8
    assert summary.qa_issue_counts["TOO_SHORT"] == 2
    assert summary.reconstruct_fail_count == 1
    assert summary.fallback_sentence_count == 1
