from __future__ import annotations

import csv
import json
from pathlib import Path

from docx import Document

from prospectus_sentence_indexer.export import Exporter
from prospectus_sentence_indexer.models import BlockType, QAReport, Sentence, Summary


def _sentence(text: str = "Sentence.") -> Sentence:
    return Sentence(
        sentence_id="S000001",
        block_id="B000001",
        part="document.xml",
        block_type=BlockType.PARAGRAPH,
        heading_level=1,
        heading_path="1 Business",
        text=text,
        qa_flags=["TOO_SHORT"],
    )


def test_export_csv_format(tmp_path: Path) -> None:
    exporter = Exporter(str(tmp_path))
    output = exporter.export_csv([_sentence()])

    with Path(output).open(encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    assert rows[0][0] == "sentence_id"
    assert rows[1][0] == "S000001"
    assert rows[1][6] == "Sentence."


def test_export_docx_table(tmp_path: Path) -> None:
    exporter = Exporter(str(tmp_path))
    output = exporter.export_docx([_sentence()])

    doc = Document(output)
    table = doc.tables[0]
    assert table.rows[0].cells[0].text == "sentence_id"
    assert table.rows[1].cells[0].text == "S000001"


def test_export_qa_report(tmp_path: Path) -> None:
    exporter = Exporter(str(tmp_path))
    output = exporter.export_qa_report(
        [
            QAReport(
                block_id="B000001",
                sentence_id="S000001",
                part="document.xml",
                block_type=BlockType.PARAGRAPH,
                heading_path="1 Business",
                issue="TOO_SHORT",
                details="short",
                raw_excerpt="abc",
            )
        ]
    )

    with Path(output).open(encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    assert rows[0][0] == "block_id"
    assert rows[1][5] == "TOO_SHORT"


def test_export_summary_json(tmp_path: Path) -> None:
    exporter = Exporter(str(tmp_path))
    output = exporter.export_summary_json(
        Summary(
            input_file="sample.docx",
            processing_time_seconds=1.2,
            total_blocks=10,
            total_sentences=12,
            block_type_counts={"paragraph": 10},
            qa_issue_counts={"TOO_SHORT": 2},
            reconstruct_fail_count=1,
            fallback_sentence_count=1,
        )
    )

    data = json.loads(Path(output).read_text(encoding="utf-8"))
    assert data["input_file"] == "sample.docx"
    assert data["qa_issue_counts"]["TOO_SHORT"] == 2


def test_export_special_chars(tmp_path: Path) -> None:
    exporter = Exporter(str(tmp_path))
    special = 'Quote " and comma, and unicode 測試'
    output = exporter.export_csv([_sentence(text=special)])

    with Path(output).open(encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    assert rows[1][6] == special
