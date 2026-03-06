from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BlockType(Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    IMAGE = "image"
    TABLE = "table"
    EQUATION = "equation"
    TABLE_CELL = "table_cell"
    TEXTBOX_PARAGRAPH = "textbox_paragraph"
    FOOTNOTE_PARAGRAPH = "footnote_paragraph"
    ENDNOTE_PARAGRAPH = "endnote_paragraph"
    HEADER_PARAGRAPH = "header_paragraph"
    FOOTER_PARAGRAPH = "footer_paragraph"


@dataclass
class Block:
    block_id: str
    part: str
    block_type: BlockType
    raw_text: str
    heading_level: int = 0
    heading_path: str = ""
    image_path: Optional[str] = None
    style_id: Optional[str] = None
    para_id: Optional[str] = None


@dataclass
class Sentence:
    sentence_id: str
    block_id: str
    part: str
    block_type: BlockType
    heading_level: int
    heading_path: str
    text: str
    image_path: Optional[str] = None
    qa_flags: list[str] = field(default_factory=list)
    is_fallback: bool = False


@dataclass
class QAReport:
    block_id: str
    sentence_id: Optional[str]
    part: str
    block_type: BlockType
    heading_path: str
    issue: str
    details: str
    raw_excerpt: str = ""


@dataclass
class Summary:
    input_file: str
    processing_time_seconds: float
    total_blocks: int
    total_sentences: int
    block_type_counts: dict[str, int] = field(default_factory=dict)
    qa_issue_counts: dict[str, int] = field(default_factory=dict)
    reconstruct_fail_count: int = 0
    fallback_sentence_count: int = 0
