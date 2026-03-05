from __future__ import annotations

import re

from .models import Block, QAReport
from .segment import SegmentResult


class QAChecker:
    def __init__(
        self,
        min_len: int = 20,
        max_len: int = 500,
        semicolon_threshold: int = 2,
    ):
        self.min_len = min_len
        self.max_len = max_len
        self.semicolon_threshold = semicolon_threshold

    def check_sentence(self, sentence: str, is_fallback: bool = False) -> list[str]:
        text = sentence.strip()
        flags: list[str] = []

        if len(text) < self.min_len:
            flags.append("TOO_SHORT")
        if len(text) > self.max_len:
            flags.append("TOO_LONG")
        if text and text[0].islower():
            flags.append("LOWERCASE_START")
        if text and not self._is_list_item(text) and not re.search(r"[.!?]$", text):
            flags.append("NO_END_PUNCT")
        if text.count(";") >= self.semicolon_threshold:
            flags.append("MANY_SEMICOLONS")
        if re.search(r"\b(?:Mr|Mrs|Ms|Dr|Prof|Inc|Ltd|Co)\.$", text):
            flags.append("ABBR_EDGE")
        if is_fallback:
            flags.append("FALLBACK_SEGMENT")

        return sorted(set(flags))

    def check_block_segmentation(self, block: Block, segment_result: SegmentResult) -> list[QAReport]:
        reports: list[QAReport] = []
        is_fallback = not segment_result.reconstruct_passed

        for idx, sentence in enumerate(segment_result.sentences, start=1):
            sentence_flags = self.check_sentence(sentence, is_fallback=is_fallback)
            if "ABBR_EDGE" in segment_result.qa_flags:
                sentence_flags = sorted(set([*sentence_flags, "ABBR_EDGE"]))
            for issue in sentence_flags:
                reports.append(
                    QAReport(
                        block_id=block.block_id,
                        sentence_id=f"{block.block_id}_S{idx:03d}",
                        part=block.part,
                        block_type=block.block_type,
                        heading_path=block.heading_path,
                        issue=issue,
                        details=sentence,
                        raw_excerpt=sentence[:200],
                    )
                )

        if "RECONSTRUCT_FAIL" in segment_result.qa_flags:
            reports.append(
                QAReport(
                    block_id=block.block_id,
                    sentence_id=None,
                    part=block.part,
                    block_type=block.block_type,
                    heading_path=block.heading_path,
                    issue="RECONSTRUCT_FAIL",
                    details="Segmentation failed reconstruct check",
                    raw_excerpt=block.raw_text[:200],
                )
            )

        return reports

    @staticmethod
    def _is_list_item(text: str) -> bool:
        return bool(re.match(r"^(?:[-*•]|\(?[0-9A-Za-z]+[.)])\s", text))
