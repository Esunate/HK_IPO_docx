from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from .export import Exporter
from .extract import DocxExtractor
from .headings import HeadingResolver
from .models import BlockType, Sentence, Summary
from .qa import QAChecker
from .segment import SentenceSegmenter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Split prospectus text into indexed sentences.")
    parser.add_argument("docx_path", help="Path to input .docx file")
    parser.add_argument("--output-dir", default="output", help="Output directory path")
    parser.add_argument("--include-headers-footers", action="store_true")
    parser.add_argument("--abbrev", action="append", default=[], help="Abbreviation whitelist entry")
    parser.add_argument(
        "--heading-style-map",
        help="Path to JSON mapping for heading levels, e.g. {\"Title\": 1, \"SectionHeader\": 2}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    docx_path = Path(args.docx_path)
    if not docx_path.exists():
        parser.error(f"Input file not found: {docx_path}")

    start = perf_counter()
    extractor = DocxExtractor(
        docx_path=str(docx_path),
        include_headers_footers=args.include_headers_footers,
    )
    blocks = extractor.extract()

    style_level_overrides: dict[str, int] | None = None
    if args.heading_style_map:
        map_path = Path(args.heading_style_map)
        if not map_path.exists():
            parser.error(f"Heading style map not found: {map_path}")
        try:
            style_level_overrides = json.loads(map_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            parser.error(f"Invalid heading style map JSON: {exc}")

    resolver = HeadingResolver(
        extractor.get_styles_xml(),
        style_level_overrides=style_level_overrides,
    )
    blocks = resolver.build_heading_paths(blocks)
    blocks = [block for block in blocks if block.block_type == BlockType.PARAGRAPH]

    segmenter = SentenceSegmenter(abbrev_whitelist=set(args.abbrev))
    qa_checker = QAChecker()

    sentences: list[Sentence] = []
    qa_reports = []
    sentence_counter = 1
    reconstruct_fail_count = 0
    fallback_sentence_count = 0

    for block in blocks:
        if block.heading_level > 0:
            # Heading blocks are context anchors only; do not emit sentence rows.
            continue

        result = segmenter.segment(block.raw_text)
        if not result.reconstruct_passed:
            reconstruct_fail_count += 1
            fallback_sentence_count += len(result.sentences)
        qa_reports.extend(qa_checker.check_block_segmentation(block, result))

        for text in result.sentences:
            sentences.append(
                Sentence(
                    sentence_id=f"S{sentence_counter:06d}",
                    block_id=block.block_id,
                    part=block.part,
                    block_type=block.block_type,
                    heading_level=block.heading_level,
                    heading_path=block.heading_path,
                    text=text,
                    qa_flags=result.qa_flags.copy(),
                    is_fallback=not result.reconstruct_passed,
                )
            )
            sentence_counter += 1

    block_type_counts: dict[str, int] = {}
    for block in blocks:
        block_type_counts[block.block_type.value] = block_type_counts.get(block.block_type.value, 0) + 1

    qa_issue_counts: dict[str, int] = {}
    for item in qa_reports:
        qa_issue_counts[item.issue] = qa_issue_counts.get(item.issue, 0) + 1

    summary = Summary(
        input_file=str(docx_path),
        processing_time_seconds=perf_counter() - start,
        total_blocks=len(blocks),
        total_sentences=len(sentences),
        block_type_counts=block_type_counts,
        qa_issue_counts=qa_issue_counts,
        reconstruct_fail_count=reconstruct_fail_count,
        fallback_sentence_count=fallback_sentence_count,
    )

    exporter = Exporter(args.output_dir)
    exporter.export_docx(sentences)
    exporter.export_csv(sentences)
    exporter.export_qa_report(qa_reports)
    exporter.export_summary_json(summary)

    print(
        f"Processed {len(blocks)} blocks into {len(sentences)} sentences. "
        f"QA issues: {len(qa_reports)}."
    )
    return 0
