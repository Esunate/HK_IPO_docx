from __future__ import annotations

from prospectus_sentence_indexer.models import Block, BlockType
from prospectus_sentence_indexer.qa import QAChecker
from prospectus_sentence_indexer.segment import SegmentResult


def _block() -> Block:
    return Block(
        block_id="B000001",
        part="document.xml",
        block_type=BlockType.PARAGRAPH,
        raw_text="source",
        heading_path="1 Business",
    )


def test_qa_too_short() -> None:
    flags = QAChecker(min_len=5).check_sentence("Hi.")
    assert "TOO_SHORT" in flags


def test_qa_too_long() -> None:
    flags = QAChecker(max_len=10).check_sentence("x" * 20)
    assert "TOO_LONG" in flags


def test_qa_lowercase_start() -> None:
    flags = QAChecker(min_len=1).check_sentence("this is a test.")
    assert "LOWERCASE_START" in flags


def test_qa_no_end_punct() -> None:
    flags = QAChecker(min_len=1).check_sentence("This is a test")
    assert "NO_END_PUNCT" in flags


def test_qa_many_semicolons() -> None:
    flags = QAChecker(min_len=1, semicolon_threshold=2).check_sentence("a;b;c")
    assert "MANY_SEMICOLONS" in flags


def test_qa_abbr_edge() -> None:
    flags = QAChecker(min_len=1).check_sentence("Met with Dr.")
    assert "ABBR_EDGE" in flags


def test_qa_reconstruct_fail() -> None:
    checker = QAChecker(min_len=1)
    reports = checker.check_block_segmentation(
        _block(),
        SegmentResult(
            sentences=["Original text."],
            qa_flags=["RECONSTRUCT_FAIL"],
            reconstruct_passed=False,
        ),
    )

    issues = [item.issue for item in reports]
    assert "RECONSTRUCT_FAIL" in issues
    assert "FALLBACK_SEGMENT" in issues
