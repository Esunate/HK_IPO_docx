from __future__ import annotations

from prospectus_sentence_indexer.segment import SentenceSegmenter


def test_pysbd_basic_segmentation() -> None:
    result = SentenceSegmenter().segment("Hello. World.")
    assert result.sentences == ["Hello.", "World."]


def test_pysbd_abbreviations() -> None:
    result = SentenceSegmenter().segment("Dr. Smith said hello.")
    assert result.sentences == ["Dr. Smith said hello."]


def test_pysbd_decimal_numbers() -> None:
    result = SentenceSegmenter().segment("Value is 3.14. Next.")
    assert result.sentences == ["Value is 3.14.", "Next."]


def test_pysbd_section_numbers() -> None:
    result = SentenceSegmenter().segment("See Section 1.2.3. Next.")
    assert result.sentences == ["See Section 1.2.3.", "Next."]


def test_segment_with_abbrev_whitelist() -> None:
    segmenter = SentenceSegmenter(abbrev_whitelist={"Co"})
    result = segmenter.segment("Company Co. filed today.")
    assert result.sentences == ["Company Co. filed today."]
    assert "ABBR_EDGE" in result.qa_flags


def test_segment_reconstruct_fail_fallback() -> None:
    segmenter = SentenceSegmenter()
    segmenter._segmenter.segment = lambda _: ["broken"]  # type: ignore[method-assign]

    result = segmenter.segment("Original text.")

    assert result.sentences == ["Original text."]
    assert result.reconstruct_passed is False
    assert "RECONSTRUCT_FAIL" in result.qa_flags


def test_normalize_whitespace_reconstruct() -> None:
    segmenter = SentenceSegmenter()
    assert segmenter.reconstruct_check("A   B", ["A", "B"])
