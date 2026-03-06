from __future__ import annotations

import json
from pathlib import Path

from prospectus_sentence_indexer.mineru import _table_image_text, extract_blocks_from_content_list
from prospectus_sentence_indexer.models import BlockType
from prospectus_sentence_indexer.segment import SentenceSegmenter


def test_extract_blocks_from_content_list(tmp_path: Path) -> None:
    content = [
        {"type": "text", "text": "TITLE A", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "Paragraph one. Next sentence.", "page_idx": 0},
        {
            "type": "image",
            "image_caption": ["Figure 1", "Source: Test"],
            "img_path": "images/a.jpg",
            "page_idx": 0,
        },
        {"type": "table", "table_body": "<table><tr><td>X</td></tr></table>", "page_idx": 0},
        {"type": "equation", "latex": "x+y=z", "page_idx": 0},
        {"type": "discarded", "text": "footer", "page_idx": 0},
    ]
    json_path = tmp_path / "sample_content_list.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    blocks = extract_blocks_from_content_list(json_path)

    assert len(blocks) == 5
    assert blocks[0].block_type == BlockType.HEADING
    assert blocks[1].block_type == BlockType.PARAGRAPH
    assert blocks[1].heading_path == "TITLE A"
    assert blocks[2].block_type == BlockType.IMAGE
    assert blocks[2].raw_text == "Figure 1 | Source: Test"
    assert blocks[2].image_path is not None
    assert blocks[2].image_path.endswith("images/a.jpg")
    assert blocks[3].block_type == BlockType.TABLE
    assert blocks[4].block_type == BlockType.EQUATION


def test_latex_inline_percent_kept_as_plain_text(tmp_path: Path) -> None:
    content = [
        {
            "type": "text",
            "text": (
                "The total shipment volume ... representing a CAGR of $3 2 . 6 \\\\%$ "
                "from 2030 to 2035."
            ),
            "page_idx": 0,
        }
    ]
    json_path = tmp_path / "sample_content_list.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    blocks = extract_blocks_from_content_list(json_path)
    text = blocks[0].raw_text

    assert "$" not in text
    assert "\\%" not in text
    assert "32.6%" in text

    segmented = SentenceSegmenter().segment(text)
    assert len(segmented.sentences) == 1
    assert "32.6%" in text


def test_cleanup_latex_rm_and_brace_comma(tmp_path: Path) -> None:
    content = [
        {
            "type": "text",
            "text": "between 200 mathrm { k m } and 2 {,} 000 mathrm { k m } , transmission",
            "page_idx": 0,
        }
    ]
    json_path = tmp_path / "sample_content_list.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    blocks = extract_blocks_from_content_list(json_path)
    text = blocks[0].raw_text
    assert "200 km and 2,000 km, transmission" in text


def test_cleanup_km_per_second_spacing(tmp_path: Path) -> None:
    content = [{"type": "text", "text": "up to 7.8 k m / s, transmission", "page_idx": 0}]
    json_path = tmp_path / "sample_content_list.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    blocks = extract_blocks_from_content_list(json_path)
    assert "7.8 km/s, transmission" in blocks[0].raw_text


def test_cleanup_spaced_letter_sequences(tmp_path: Path) -> None:
    content = [
        {
            "type": "text",
            "text": (
                "Access to domestic LEO satellite Internet constellations requires chips to complete "
                "a protracted validation process across l a b o r a t o r y t e s t i n g, "
                "g r o u n d fi e l d t e s t i n g, a n d o n-o r b i t ve r i fi c a t i o n, "
                "c o n fi r m i n g f u l l interoperability"
            ),
            "page_idx": 0,
        }
    ]
    json_path = tmp_path / "sample_content_list.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    blocks = extract_blocks_from_content_list(json_path)
    text = blocks[0].raw_text

    assert "laboratory testing" in text
    assert "ground field testing" in text
    assert "and on-orbit verification" in text
    assert "confirming full interoperability" in text


def test_list_object_treated_like_text_paragraph(tmp_path: Path) -> None:
    content = [
        {"type": "text", "text": "SECTION", "text_level": 1, "page_idx": 0},
        {"type": "list", "text": "Item one. Item two.", "page_idx": 0},
    ]
    json_path = tmp_path / "sample_content_list.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    blocks = extract_blocks_from_content_list(json_path)
    assert len(blocks) == 2
    assert blocks[1].block_type == BlockType.PARAGRAPH
    assert blocks[1].heading_path == "SECTION"


def test_list_text_subtype_treated_like_text_paragraph(tmp_path: Path) -> None:
    content = [
        {"type": "text", "text": "SECTION", "text_level": 1, "page_idx": 0},
        {"type": "list", "sub_type": "text", "text": "Item one. Item two.", "page_idx": 0},
    ]
    json_path = tmp_path / "sample_content_list.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    blocks = extract_blocks_from_content_list(json_path)
    assert len(blocks) == 2
    assert blocks[1].block_type == BlockType.PARAGRAPH
    assert blocks[1].raw_text == "Item one. Item two."
    assert blocks[1].heading_path == "SECTION"


def test_list_nested_items_are_flattened_to_paragraph(tmp_path: Path) -> None:
    content = [
        {"type": "text", "text": "SECTION", "text_level": 1, "page_idx": 0},
        {
            "type": "list",
            "sub_type": "unordered",
            "items": [
                {"text": "First bullet."},
                {"content": ["Second", "bullet."]},
            ],
            "page_idx": 0,
        },
    ]
    json_path = tmp_path / "sample_content_list.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    blocks = extract_blocks_from_content_list(json_path)
    assert len(blocks) == 2
    assert blocks[1].block_type == BlockType.PARAGRAPH
    assert blocks[1].raw_text == "First bullet. Second bullet."
    assert blocks[1].heading_path == "SECTION"


def test_list_items_field_is_flattened_to_paragraph(tmp_path: Path) -> None:
    content = [
        {"type": "text", "text": "SECTION", "text_level": 1, "page_idx": 0},
        {
            "type": "list",
            "sub_type": "text",
            "list_items": ["First bullet.", "Second bullet."],
            "page_idx": 0,
        },
    ]
    json_path = tmp_path / "sample_content_list.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    blocks = extract_blocks_from_content_list(json_path)
    assert len(blocks) == 2
    assert blocks[1].block_type == BlockType.PARAGRAPH
    assert blocks[1].raw_text == "First bullet. Second bullet."
    assert blocks[1].heading_path == "SECTION"


def test_continuation_text_blocks_are_merged_before_segment(tmp_path: Path) -> None:
    content = [
        {"type": "text", "text": "OVERVIEW", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "This creates a distinct market for ", "page_idx": 0},
        {
            "type": "text",
            "text": "“6G-Oriented Satellite Internet Solutions,” which provide the essential hardware and software enabling ",
            "page_idx": 0,
        },
        {"type": "text", "text": "user equipment to connect to the satellite Internet.", "page_idx": 0},
    ]
    json_path = tmp_path / "sample_content_list.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    blocks = extract_blocks_from_content_list(json_path)
    paragraphs = [item for item in blocks if item.block_type == BlockType.PARAGRAPH]

    assert len(paragraphs) == 1
    assert "This creates a distinct market for “6G-Oriented Satellite Internet Solutions,”" in paragraphs[0].raw_text
    assert paragraphs[0].raw_text.endswith("user equipment to connect to the satellite Internet.")


def test_table_image_text_uses_page_and_title() -> None:
    text = _table_image_text(
        {
            "table_caption": ["Ranking of Providers"],
            "page_idx": 2,
        }
    )
    assert text == "表格（第3页）Ranking of Providers"


def test_notes_label_is_merged_with_following_paragraph(tmp_path: Path) -> None:
    content = [
        {"type": "text", "text": "SECTION", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "Notes:", "page_idx": 0},
        {"type": "text", "text": "(a) First note line.", "page_idx": 0},
    ]
    json_path = tmp_path / "sample_content_list.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    blocks = extract_blocks_from_content_list(json_path)
    paragraphs = [item for item in blocks if item.block_type == BlockType.PARAGRAPH]
    assert len(paragraphs) == 1
    assert paragraphs[0].raw_text == "(a) First note line."
