from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import Block, BlockType

WORD_EXTENSIONS = {".doc", ".docx"}
PDF_EXTENSIONS = {".pdf"}
OCR_SEGMENT_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into", "is", "of", "on",
    "or", "that", "the", "their", "this", "to", "with",
    "access", "across", "advantages", "allocation", "among", "architecture", "business", "cellular",
    "communications", "complete", "computing", "conditions", "confirming", "connect", "connectivity",
    "constellations", "coverage", "customer", "customers", "cycle", "deep", "distinct", "domestic",
    "downstream", "durable", "dynamic", "dynamically", "early", "ecosystem", "efficient", "enabling",
    "equipment", "establish", "exceeds", "field", "first", "full", "geographies", "global", "ground",
    "hardware", "identifies", "incumbent", "industry", "intelligent", "integration", "interoperability",
    "internet", "laboratory", "load", "manufacturers", "market", "mechanisms", "mobile", "moving",
    "multi", "network", "networks", "non", "operators", "optimize", "optimizing", "orbit", "oriented",
    "payloads", "power", "process", "processing", "product", "products", "protracted", "protocols",
    "providing", "qualification", "real", "requirements", "resource", "retention", "resulting", "satellite",
    "sagsin", "secure", "seamless", "select", "shipment", "single", "software", "standards", "strong",
    "suppliers", "switch", "switching", "systems", "terminal", "terminals", "terrestrial", "testing",
    "the", "these", "through", "traditional", "two", "unified", "user", "validation", "vendors",
    "verification", "volume", "which",
}


@dataclass
class MinerUArtifacts:
    markdown_path: Path
    content_json_path: Path
    root_dir: Path
    parse_pdf_path: Path


def run_mineru_pipeline(
    input_path: Path,
    output_dir: Path,
    mineru_command: str = "mineru",
    mineru_method: str = "auto",
    mineru_lang: str = "en",
) -> MinerUArtifacts:
    mineru_output_dir = output_dir / "mineru_md"
    mineru_output_dir.mkdir(parents=True, exist_ok=True)

    parse_source = _prepare_parse_source(input_path, output_dir)
    subprocess.run(
        [
            mineru_command,
            "-p",
            str(parse_source),
            "-o",
            str(mineru_output_dir),
            "-m",
            mineru_method,
            "-l",
            mineru_lang,
        ],
        check=True,
    )
    return _discover_artifacts(mineru_output_dir, parse_source.stem, parse_source)


def _prepare_parse_source(input_path: Path, output_dir: Path) -> Path:
    suffix = input_path.suffix.lower()
    if suffix in PDF_EXTENSIONS:
        return input_path
    if suffix in WORD_EXTENSIONS:
        return _convert_word_to_pdf(input_path, output_dir / "word_to_pdf")
    raise ValueError(f"Unsupported input format: {input_path.suffix}")


def _convert_word_to_pdf(input_path: Path, pdf_output_dir: Path) -> Path:
    pdf_output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(pdf_output_dir),
            str(input_path),
        ],
        check=True,
    )
    pdf_path = pdf_output_dir / f"{input_path.stem}.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"Word->PDF conversion succeeded but output not found: {pdf_path}")
    return pdf_path


def _discover_artifacts(mineru_output_dir: Path, stem: str, parse_pdf_path: Path) -> MinerUArtifacts:
    normalized = stem.strip()
    txt_dir = mineru_output_dir / normalized / "txt"
    if txt_dir.exists():
        candidates_json = sorted(txt_dir.glob("*_content_list.json"))
        candidates_md = sorted(txt_dir.glob("*.md"))
        if candidates_json and candidates_md:
            return MinerUArtifacts(
                markdown_path=candidates_md[0],
                content_json_path=candidates_json[0],
                root_dir=txt_dir,
                parse_pdf_path=parse_pdf_path,
            )

    artifact_dirs = sorted(path.parent for path in mineru_output_dir.glob("**/*_content_list.json"))
    if not artifact_dirs:
        raise FileNotFoundError(f"No MinerU artifact directory found in: {mineru_output_dir}")
    artifact_dir = artifact_dirs[0]
    candidates_json = sorted(artifact_dir.glob("*_content_list.json"))
    candidates_md = sorted(artifact_dir.glob("*.md"))
    if not candidates_md:
        raise FileNotFoundError(f"No markdown file found in: {artifact_dir}")

    return MinerUArtifacts(
        markdown_path=candidates_md[0],
        content_json_path=candidates_json[0],
        root_dir=artifact_dir,
        parse_pdf_path=parse_pdf_path,
    )


def extract_blocks_from_content_list(
    content_json_path: Path,
    artifacts_root_dir: Path | None = None,
    parse_pdf_path: Path | None = None,
) -> list[Block]:
    data = json.loads(content_json_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Unexpected content_list format: {content_json_path}")

    blocks: list[Block] = []
    current_heading_stack: list[tuple[int, str]] = []
    block_counter = 1
    page_bbox_max = _page_bbox_max_map(data)

    for item in data:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", "")).strip().lower()
        item_sub_type = str(item.get("sub_type", "")).strip().lower()
        if item_type == "discarded":
            continue

        if item_type == "text" or item_type == "list":
            text = _extract_text_like_content(item)
            if not text:
                continue
            if _is_note_label(text):
                continue
            level = _safe_int(item.get("text_level"), 0) if item_type == "text" else 0
            if level > 0:
                while current_heading_stack and current_heading_stack[-1][0] >= level:
                    current_heading_stack.pop()
                current_heading_stack.append((level, text))
                block = Block(
                    block_id=f"B{block_counter:06d}",
                    part=_part_name(item),
                    block_type=BlockType.HEADING,
                    raw_text=text,
                    heading_level=level,
                    heading_path=" > ".join(part for _, part in current_heading_stack),
                )
            else:
                block = Block(
                    block_id=f"B{block_counter:06d}",
                    part=_part_name(item),
                    block_type=BlockType.PARAGRAPH,
                    raw_text=text,
                    heading_level=0,
                    heading_path=" > ".join(part for _, part in current_heading_stack),
                )
            blocks.append(block)
            block_counter += 1
            continue

        if item_type == "image":
            image_text = _image_text(item)
            if not image_text:
                continue
            image_path = _resolve_image_path(item, artifacts_root_dir or content_json_path.parent)
            blocks.append(
                Block(
                    block_id=f"B{block_counter:06d}",
                    part=_part_name(item),
                    block_type=BlockType.IMAGE,
                    raw_text=image_text,
                    image_path=image_path,
                    heading_level=0,
                    heading_path=" > ".join(part for _, part in current_heading_stack),
                )
            )
            block_counter += 1
            continue

        if item_type == "table":
            table_image_path = _crop_item_from_pdf(
                item=item,
                parse_pdf_path=parse_pdf_path,
                output_dir=(artifacts_root_dir or content_json_path.parent) / "crops",
                name_prefix="table",
                page_bbox_max=page_bbox_max,
                index=block_counter,
            )
            if table_image_path:
                blocks.append(
                    Block(
                        block_id=f"B{block_counter:06d}",
                        part=_part_name(item),
                        block_type=BlockType.IMAGE,
                        raw_text=_table_image_text(
                            item,
                            fallback_title=(" > ".join(part for _, part in current_heading_stack)),
                        ),
                        image_path=table_image_path,
                        heading_level=0,
                        heading_path=" > ".join(part for _, part in current_heading_stack),
                    )
                )
            else:
                table_text = _normalize_space(str(item.get("table_body", "") or item.get("text", "")))
                if not table_text:
                    continue
                blocks.append(
                    Block(
                        block_id=f"B{block_counter:06d}",
                        part=_part_name(item),
                        block_type=BlockType.TABLE,
                        raw_text=table_text,
                        heading_level=0,
                        heading_path=" > ".join(part for _, part in current_heading_stack),
                    )
                )
            block_counter += 1
            continue

        if item_type == "equation":
            equation_text = _normalize_space(str(item.get("text", "") or item.get("latex", "")))
            if not equation_text:
                continue
            blocks.append(
                Block(
                    block_id=f"B{block_counter:06d}",
                    part=_part_name(item),
                    block_type=BlockType.EQUATION,
                    raw_text=equation_text,
                    heading_level=0,
                    heading_path=" > ".join(part for _, part in current_heading_stack),
                )
            )
            block_counter += 1

    blocks = _merge_continuation_paragraphs(blocks)
    _reindex_blocks(blocks)
    return blocks


def _extract_text_like_content(item: dict) -> str:
    if str(item.get("type", "")).strip().lower() == "text":
        return _normalize_mineru_text(str(item.get("text", "")))

    candidate_fields = (
        "text",
        "list_text",
        "list_body",
        "list_items",
        "items",
        "children",
    )
    for field in candidate_fields:
        text = _collect_text_fragments(item.get(field))
        if text:
            return _normalize_mineru_text(text)
    return ""


def _collect_text_fragments(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [_collect_text_fragments(entry) for entry in value]
        return " ".join(part for part in parts if part)
    if isinstance(value, dict):
        for field in ("text", "content", "list_text", "list_body"):
            text = _collect_text_fragments(value.get(field))
            if text:
                return text
        parts = [_collect_text_fragments(entry) for entry in value.values()]
        return " ".join(part for part in parts if part)
    return str(value)


def _image_text(item: dict) -> str:
    captions = item.get("image_caption", [])
    if isinstance(captions, list):
        lines = [_normalize_space(str(entry)) for entry in captions if str(entry).strip()]
        lines = [line for line in lines if line]
    else:
        lines = []
    if lines:
        return " | ".join(lines)
    img_path = _normalize_space(str(item.get("img_path", "")))
    return f"[IMAGE] {img_path}" if img_path else ""


def _resolve_image_path(item: dict, root_dir: Path) -> str | None:
    raw_path = _normalize_space(str(item.get("img_path", "")))
    if not raw_path:
        return None
    candidate = (root_dir / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path)
    return str(candidate)


def _table_image_text(item: dict, fallback_title: str = "") -> str:
    page_idx = _safe_int(item.get("page_idx"), 0)
    caption = item.get("table_caption", [])
    title = ""
    if isinstance(caption, list):
        lines = [_normalize_space(str(entry)) for entry in caption if str(entry).strip()]
        title = " | ".join(lines)
    elif isinstance(caption, str):
        title = _normalize_space(caption)

    if not title:
        title = _normalize_space(fallback_title.split(">")[-1] if fallback_title else "")

    if title:
        return f"表格（第{page_idx + 1}页）{title}"
    return f"表格（第{page_idx + 1}页）"


def _page_bbox_max_map(data: list[object]) -> dict[int, tuple[float, float]]:
    page_max: dict[int, tuple[float, float]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        bbox = item.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        page_idx = _safe_int(item.get("page_idx"), 0)
        _, _, x2, y2 = bbox
        prev_x, prev_y = page_max.get(page_idx, (0.0, 0.0))
        page_max[page_idx] = (max(float(x2), prev_x), max(float(y2), prev_y))
    return page_max


def _crop_item_from_pdf(
    item: dict,
    parse_pdf_path: Path | None,
    output_dir: Path,
    name_prefix: str,
    page_bbox_max: dict[int, tuple[float, float]],
    index: int,
) -> str | None:
    if parse_pdf_path is None:
        return None
    bbox = item.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    if not parse_pdf_path.exists():
        return None
    try:
        import fitz  # type: ignore
    except Exception:
        return None

    page_idx = _safe_int(item.get("page_idx"), 0)
    try:
        with fitz.open(parse_pdf_path) as doc:
            if page_idx < 0 or page_idx >= len(doc):
                return None
            page = doc[page_idx]
            x1, y1, x2, y2 = [float(value) for value in bbox]
            max_x, max_y = page_bbox_max.get(page_idx, (x2, y2))
            scale_x = page.rect.width / max_x if max_x > page.rect.width * 1.2 else 1.0
            scale_y = page.rect.height / max_y if max_y > page.rect.height * 1.2 else 1.0
            rect = fitz.Rect(x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y)
            rect = rect & page.rect
            if rect.is_empty or rect.width < 2 or rect.height < 2:
                return None
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"{name_prefix}_p{page_idx + 1}_{index:04d}.png"
            pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(2, 2))
            pix.save(str(out_path))
            return str(out_path.resolve())
    except Exception:
        return None
    return None


def _part_name(item: dict) -> str:
    page_idx = _safe_int(item.get("page_idx"), 0)
    return f"page_{page_idx + 1}"


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_mineru_text(text: str) -> str:
    def replace_math(match: re.Match[str]) -> str:
        return _normalize_inline_math(match.group(1))

    normalized = re.sub(r"\$([^$]+)\$", replace_math, text)
    normalized = _cleanup_latex_artifacts(normalized)
    normalized = _repair_spaced_letter_sequences(normalized)
    return _normalize_space(normalized)


def _repair_spaced_letter_sequences(text: str) -> str:
    parts = re.findall(r"\S+|\s+", text)
    repaired: list[str] = []
    index = 0

    while index < len(parts):
        if parts[index].isspace():
            repaired.append(parts[index])
            index += 1
            continue

        current = _split_fragment_token(parts[index])
        if current is None:
            repaired.append(parts[index])
            index += 1
            continue

        prefix, core, suffix = current
        run_tokens = [core]
        run_prefix = prefix
        run_suffix = suffix
        run_end = index + 1
        while not run_suffix and run_end + 1 < len(parts) and parts[run_end].isspace():
            next_token = _split_fragment_token(parts[run_end + 1])
            if next_token is None:
                break
            next_prefix, next_core, next_suffix = next_token
            if next_prefix:
                break
            run_tokens.append(next_core)
            run_suffix = next_suffix
            run_end += 2

        letter_count = sum(len(token.replace("-", "")) for token in run_tokens)
        if len(run_tokens) >= 4 or letter_count >= 8:
            repaired.append(f"{run_prefix}{_segment_fragment_run(run_tokens)}{run_suffix}")
            index = run_end
            continue

        repaired.append(parts[index])
        index += 1

    return "".join(repaired)


def _is_letter_fragment(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]{1,2}(?:-[A-Za-z]{1,2})*", token))


def _split_fragment_token(token: str) -> tuple[str, str, str] | None:
    match = re.fullmatch(r"([^A-Za-z]*)([A-Za-z]{1,2}(?:-[A-Za-z]{1,2})*)([^A-Za-z]*)", token)
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


def _segment_fragment_run(tokens: list[str]) -> str:
    compact = "".join(tokens)
    segments = [_segment_compact_letters(part) for part in compact.split("-")]
    return "-".join(segments)


def _segment_compact_letters(compact: str) -> str:
    lower = compact.lower()
    n = len(lower)
    best_score: list[int | None] = [None] * (n + 1)
    best_parts: list[list[str] | None] = [None] * (n + 1)
    best_score[0] = 0
    best_parts[0] = []

    for start in range(n):
        if best_parts[start] is None:
            continue

        for end in range(start + 1, min(n, start + 24) + 1):
            word = lower[start:end]
            if word not in OCR_SEGMENT_WORDS:
                continue
            score = best_score[start] + len(word)
            parts = [*best_parts[start], word]
            if best_score[end] is None or score > best_score[end] or (
                score == best_score[end] and len(parts) < len(best_parts[end])
            ):
                best_score[end] = score
                best_parts[end] = parts

        fallback_end = start + 1
        fallback = compact[start:fallback_end]
        score = best_score[start]
        parts = [*best_parts[start], fallback]
        if best_score[fallback_end] is None or score > best_score[fallback_end] or (
            score == best_score[fallback_end] and len(parts) < len(best_parts[fallback_end])
        ):
            best_score[fallback_end] = score
            best_parts[fallback_end] = parts

    if best_parts[n] is None:
        return compact

    merged: list[str] = []
    for part in best_parts[n]:
        if merged and part not in OCR_SEGMENT_WORDS and merged[-1] not in OCR_SEGMENT_WORDS:
            merged[-1] += part
        else:
            merged.append(part)
    return " ".join(merged)


def _normalize_inline_math(content: str) -> str:
    text = content
    text = re.sub(r"\\+%", "%", text)
    text = text.replace(r"\$", "$")
    text = text.replace(r"\(", "(").replace(r"\)", ")")
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)
    text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    text = re.sub(r"\s*([.,%])\s*", r"\1", text)
    return _normalize_space(text)


def _cleanup_latex_artifacts(text: str) -> str:
    def _replace_rm(match: re.Match[str]) -> str:
        inner = _normalize_space(match.group(1))
        if re.fullmatch(r"(?:[A-Za-z]\s+)+[A-Za-z]", inner):
            inner = inner.replace(" ", "")
        return inner

    cleaned = re.sub(r"\b(?:math)?rm\s*\{\s*([^{}]+?)\s*\}", _replace_rm, text)
    cleaned = re.sub(r"\{\s*,\s*\}", ",", cleaned)
    cleaned = re.sub(r"\{\s*([%.,:;!?()])\s*\}", r"\1", cleaned)
    cleaned = re.sub(r"\bk\s*m\s*/\s*s\b", "km/s", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?<=\d)\s+k\s*m\b", " km", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?<=\d)\s*,\s*(?=\d)", ",", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    return cleaned


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _merge_continuation_paragraphs(blocks: list[Block]) -> list[Block]:
    if not blocks:
        return []

    merged: list[Block] = [blocks[0]]
    for current in blocks[1:]:
        previous = merged[-1]
        if _should_merge_paragraph(previous, current):
            previous.raw_text = _normalize_space(f"{previous.raw_text} {current.raw_text}")
            continue
        merged.append(current)
    return merged


def _should_merge_paragraph(previous: Block, current: Block) -> bool:
    if previous.block_type != BlockType.PARAGRAPH or current.block_type != BlockType.PARAGRAPH:
        return False
    if previous.part != current.part or previous.heading_path != current.heading_path:
        return False

    prev_text = previous.raw_text.strip()
    curr_text = current.raw_text.strip()
    if not prev_text or not curr_text:
        return False
    if re.search(r"[.!?。！？:：;；]$", prev_text):
        return False

    return bool(re.match(r'^[a-z0-9"“”\'(（\[]', curr_text))


def _reindex_blocks(blocks: list[Block]) -> None:
    for idx, block in enumerate(blocks, start=1):
        block.block_id = f"B{idx:06d}"


def _is_note_label(text: str) -> bool:
    normalized = _normalize_space(text).lower()
    return normalized in {"notes:", "note:", "注:", "注释:"}
