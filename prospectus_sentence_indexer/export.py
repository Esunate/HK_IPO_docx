from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from docx import Document

from .models import QAReport, Sentence, Summary


class Exporter:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_csv(self, sentences: list[Sentence]) -> str:
        output = self.output_dir / "sentences.csv"
        with output.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "sentence_id",
                "block_id",
                "part",
                "block_type",
                "heading_level",
                "heading_path",
                "text",
                "qa_flags",
            ])
            for sentence in sentences:
                writer.writerow([
                    sentence.sentence_id,
                    sentence.block_id,
                    sentence.part,
                    sentence.block_type.value,
                    sentence.heading_level,
                    sentence.heading_path,
                    sentence.text,
                    "|".join(sentence.qa_flags),
                ])
        return str(output)

    def export_docx(self, sentences: list[Sentence]) -> str:
        output = self.output_dir / "sentences.docx"
        document = Document()
        table = document.add_table(rows=1, cols=8)
        headers = [
            "sentence_id",
            "block_id",
            "part",
            "block_type",
            "heading_level",
            "heading_path",
            "text",
            "qa_flags",
        ]
        for idx, header in enumerate(headers):
            table.rows[0].cells[idx].text = header

        for sentence in sentences:
            row = table.add_row().cells
            row[0].text = sentence.sentence_id
            row[1].text = sentence.block_id
            row[2].text = sentence.part
            row[3].text = sentence.block_type.value
            row[4].text = str(sentence.heading_level)
            row[5].text = sentence.heading_path
            row[6].text = sentence.text
            row[7].text = "|".join(sentence.qa_flags)

        document.save(output)
        return str(output)

    def export_qa_report(self, qa_reports: list[QAReport]) -> str:
        output = self.output_dir / "qa_report.csv"
        with output.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "block_id",
                "sentence_id",
                "part",
                "block_type",
                "heading_path",
                "issue",
                "details",
                "raw_excerpt",
            ])
            for report in qa_reports:
                writer.writerow([
                    report.block_id,
                    report.sentence_id or "",
                    report.part,
                    report.block_type.value,
                    report.heading_path,
                    report.issue,
                    report.details,
                    report.raw_excerpt,
                ])
        return str(output)

    def export_summary_json(self, summary: Summary) -> str:
        output = self.output_dir / "summary.json"
        with output.open("w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, ensure_ascii=False, indent=2)
        return str(output)
