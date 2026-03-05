from __future__ import annotations

import re
from dataclasses import dataclass, field

from pysbd import Segmenter

from .extract import reconstruct_check as _reconstruct_check


@dataclass
class SegmentResult:
    sentences: list[str]
    qa_flags: list[str] = field(default_factory=list)
    reconstruct_passed: bool = True


class SentenceSegmenter:
    def __init__(
        self,
        abbrev_whitelist: set[str] | None = None,
        min_len: int = 20,
        max_len: int = 500,
        semicolon_threshold: int = 2,
    ):
        self.abbrev_whitelist = {item.rstrip(".") for item in (abbrev_whitelist or set())}
        self.min_len = min_len
        self.max_len = max_len
        self.semicolon_threshold = semicolon_threshold
        self._segmenter = Segmenter(language="en", clean=False)

    def segment(self, raw_text: str) -> SegmentResult:
        if not raw_text.strip():
            return SegmentResult(sentences=[])

        segmented = [s.strip() for s in self._segmenter.segment(raw_text) if s.strip()]
        segmented, qa_flags = self._apply_abbrev_whitelist(segmented)

        passed = self.reconstruct_check(raw_text, segmented)
        if not passed:
            return SegmentResult(
                sentences=[raw_text],
                qa_flags=sorted(set([*qa_flags, "RECONSTRUCT_FAIL"])),
                reconstruct_passed=False,
            )

        return SegmentResult(sentences=segmented, qa_flags=sorted(set(qa_flags)), reconstruct_passed=True)

    def reconstruct_check(self, raw_text: str, sentences: list[str]) -> bool:
        return _reconstruct_check(raw_text, sentences)

    def _apply_abbrev_whitelist(self, sentences: list[str]) -> tuple[list[str], list[str]]:
        if not self.abbrev_whitelist:
            return sentences, []

        merged: list[str] = []
        flags: list[str] = []
        has_abbrev_edge = False
        i = 0
        while i < len(sentences):
            current = sentences[i]
            if self._contains_whitelisted_abbrev(current):
                has_abbrev_edge = True
            if i + 1 < len(sentences) and self._ends_with_abbrev(current):
                merged.append(f"{current} {sentences[i + 1]}")
                flags.append("ABBR_EDGE")
                i += 2
                continue
            merged.append(current)
            i += 1
        if has_abbrev_edge:
            flags.append("ABBR_EDGE")
        return merged, flags

    def _ends_with_abbrev(self, sentence: str) -> bool:
        match = re.search(r"\b([A-Za-z][A-Za-z0-9]{0,15})\.$", sentence.strip())
        if not match:
            return False
        return match.group(1) in self.abbrev_whitelist

    def _contains_whitelisted_abbrev(self, sentence: str) -> bool:
        for abbr in self.abbrev_whitelist:
            if re.search(rf"\b{re.escape(abbr)}\.", sentence):
                return True
        return False
