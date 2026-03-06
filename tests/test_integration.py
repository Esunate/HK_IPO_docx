from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from prospectus_sentence_indexer.cli import main
from prospectus_sentence_indexer.mineru import MinerUArtifacts


def _make_content_json(tmp_path: Path) -> Path:
    content = [
        {"type": "text", "text": "INDUSTRY OVERVIEW", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "Body sentence one. Body sentence two.", "page_idx": 0},
        {
            "type": "image",
            "image_caption": ["Chart A", "Source: CIC"],
            "img_path": "images/a.jpg",
            "page_idx": 0,
        },
        {"type": "discarded", "text": "Footer", "page_idx": 0},
    ]
    content_path = tmp_path / "sample_content_list.json"
    content_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return content_path


def _patch_mineru(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    content_json = _make_content_json(tmp_path)
    md_path = tmp_path / "sample.md"
    md_path.write_text("# INDUSTRY OVERVIEW\n", encoding="utf-8")

    def _fake_pipeline(*_args, **_kwargs) -> MinerUArtifacts:
        return MinerUArtifacts(
            markdown_path=md_path,
            content_json_path=content_json,
            root_dir=tmp_path,
            parse_pdf_path=tmp_path / "input.pdf",
        )

    monkeypatch.setattr("prospectus_sentence_indexer.cli.run_mineru_pipeline", _fake_pipeline)
    return content_json


def test_cli_basic_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mineru(monkeypatch, tmp_path)
    input_path = tmp_path / "input.pdf"
    input_path.write_bytes(b"%PDF-1.4")
    out_dir = tmp_path / "out"

    code = main([str(input_path), "--output-dir", str(out_dir)])

    assert code == 0
    assert (out_dir / "sentences.csv").exists()
    assert (out_dir / "sentences.docx").exists()
    assert (out_dir / "qa_report.csv").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "mineru_artifacts.json").exists()


def test_cli_heading_and_image_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mineru(monkeypatch, tmp_path)
    input_path = tmp_path / "input.pdf"
    input_path.write_bytes(b"%PDF-1.4")
    out_dir = tmp_path / "out"

    main([str(input_path), "--output-dir", str(out_dir)])

    with (out_dir / "sentences.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    assert rows[0]["block_type"] == "heading"
    assert rows[0]["sentence_id"] == ""
    assert rows[0]["text"] == "INDUSTRY OVERVIEW"
    assert rows[1]["block_type"] == "paragraph"
    assert rows[2]["block_type"] == "paragraph"
    assert rows[3]["block_type"] == "image"
    assert rows[3]["sentence_id"] != ""
    assert rows[3]["image_path"].endswith("images/a.jpg")

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_sentences"] == 3


def test_error_handling_missing_input(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([str(tmp_path / "missing.pdf")])
    assert exc_info.value.code == 2
