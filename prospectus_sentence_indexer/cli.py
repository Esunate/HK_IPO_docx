from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from .export import Exporter
from .models import BlockType, Sentence, Summary
from .mineru import extract_blocks_from_content_list, run_mineru_pipeline
from .qa import QAChecker
from .segment import SentenceSegmenter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Split prospectus text into indexed sentences.")
    parser.add_argument("input_path", help="Path to input .doc/.docx/.pdf file")
    parser.add_argument("--output-dir", default="output", help="Output directory path")
    parser.add_argument("--abbrev", action="append", default=[], help="Abbreviation whitelist entry")
    parser.add_argument("--mineru-command", default="mineru", help="MinerU command, default: mineru")
    parser.add_argument("--mineru-method", default="auto", help="MinerU parse method: auto/txt/ocr")
    parser.add_argument("--mineru-lang", default="en", help="MinerU OCR language")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    input_path = Path(args.input_path)
    if not input_path.exists():
        parser.error(f"Input file not found: {input_path}")
    output_dir = Path(args.output_dir)

    start = perf_counter()
    artifacts = run_mineru_pipeline(
        input_path=input_path,
        output_dir=output_dir,
        mineru_command=args.mineru_command,
        mineru_method=args.mineru_method,
        mineru_lang=args.mineru_lang,
    )
    blocks = extract_blocks_from_content_list(
        artifacts.content_json_path,
        artifacts_root_dir=artifacts.root_dir,
        parse_pdf_path=artifacts.parse_pdf_path,
    )

    segmenter = SentenceSegmenter(abbrev_whitelist=set(args.abbrev))
    qa_checker = QAChecker()

    sentences: list[Sentence] = []
    qa_reports = []
    sentence_counter = 1
    reconstruct_fail_count = 0
    fallback_sentence_count = 0

    for block in blocks:
        if block.block_type == BlockType.HEADING:
            # 标题单独起一行，不记作句子。
            sentences.append(
                Sentence(
                    sentence_id="",
                    block_id=block.block_id,
                    part=block.part,
                    block_type=block.block_type,
                    heading_level=block.heading_level,
                    heading_path=block.heading_path,
                    text=block.raw_text,
                    image_path=block.image_path,
                    qa_flags=[],
                    is_fallback=False,
                )
            )
            continue

        if block.block_type == BlockType.IMAGE:
            # 图片当成一个句子，单独起一行。
            sentences.append(
                Sentence(
                    sentence_id=f"S{sentence_counter:06d}",
                    block_id=block.block_id,
                    part=block.part,
                    block_type=block.block_type,
                    heading_level=0,
                    heading_path=block.heading_path,
                    text=block.raw_text,
                    image_path=block.image_path,
                    qa_flags=[],
                    is_fallback=False,
                )
            )
            sentence_counter += 1
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
                    image_path=block.image_path,
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
        input_file=str(input_path),
        processing_time_seconds=perf_counter() - start,
        total_blocks=len(blocks),
        total_sentences=sum(1 for item in sentences if item.sentence_id),
        block_type_counts=block_type_counts,
        qa_issue_counts=qa_issue_counts,
        reconstruct_fail_count=reconstruct_fail_count,
        fallback_sentence_count=fallback_sentence_count,
    )

    exporter = Exporter(args.output_dir)
    exporter.export_docx(sentences, input_name=input_path.name)
    exporter.export_csv(sentences)
    exporter.export_qa_report(qa_reports)
    exporter.export_summary_json(summary)
    (output_dir / "mineru_artifacts.json").write_text(
        json.dumps(
            {
                "markdown_path": str(artifacts.markdown_path),
                "content_json_path": str(artifacts.content_json_path),
                "parse_pdf_path": str(artifacts.parse_pdf_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Processed {len(blocks)} blocks into {len(sentences)} sentences. "
        f"QA issues: {len(qa_reports)}."
    )
    return 0
