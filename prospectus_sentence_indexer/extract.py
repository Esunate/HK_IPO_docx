from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from .models import Block, BlockType

NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def reconstruct_check(raw_text: str, sentences: list[str]) -> bool:
    reconstructed = " ".join(sentences)
    return normalize_whitespace(raw_text) == normalize_whitespace(reconstructed)


class DocxExtractor:
    def __init__(self, docx_path: str, include_headers_footers: bool = False):
        self.docx_path = Path(docx_path)
        self.include_headers_footers = include_headers_footers

    def get_styles_xml(self) -> etree._Element | None:
        with ZipFile(self.docx_path) as archive:
            try:
                data = archive.read("word/styles.xml")
            except KeyError:
                return None
        return etree.fromstring(data)

    def extract(self) -> list[Block]:
        blocks: list[Block] = []
        with ZipFile(self.docx_path) as archive:
            part_paths = self._part_paths(archive)
            for part_path in part_paths:
                root = etree.fromstring(archive.read(part_path))
                part_name = Path(part_path).name
                blocks.extend(self._extract_blocks_from_part(root, part_name))

        for idx, block in enumerate(blocks, start=1):
            block.block_id = f"B{idx:06d}"
        return blocks

    def _part_paths(self, archive: ZipFile) -> list[str]:
        names = set(archive.namelist())
        paths = ["word/document.xml"] if "word/document.xml" in names else []
        if "word/footnotes.xml" in names:
            paths.append("word/footnotes.xml")
        if "word/endnotes.xml" in names:
            paths.append("word/endnotes.xml")

        if self.include_headers_footers:
            headers = sorted(name for name in names if re.match(r"word/header\d+\.xml", name))
            footers = sorted(name for name in names if re.match(r"word/footer\d+\.xml", name))
            paths.extend(headers)
            paths.extend(footers)
        return paths

    def _extract_blocks_from_part(self, root: etree._Element, part_name: str) -> list[Block]:
        blocks: list[Block] = []
        w_ns = NAMESPACES["w"]
        p_tag = f"{{{w_ns}}}p"
        tc_tag = f"{{{w_ns}}}tc"
        txbx_tag = f"{{{w_ns}}}txbxContent"

        for element in root.iter():
            if element.tag == tc_tag:
                text = self._collect_text(element)
                if text:
                    blocks.append(self._make_block(part_name, BlockType.TABLE_CELL, text, element))
                continue

            if element.tag != p_tag:
                continue

            if self._has_ancestor_tag(element, txbx_tag):
                text = self._collect_text(element)
                if text:
                    blocks.append(
                        self._make_block(part_name, BlockType.TEXTBOX_PARAGRAPH, text, element)
                    )
                continue

            if self._has_ancestor_tag(element, tc_tag):
                continue

            text = self._collect_text(element)
            if text:
                blocks.append(self._make_block(part_name, self._paragraph_type(part_name), text, element))

        return blocks

    def _make_block(
        self,
        part_name: str,
        block_type: BlockType,
        text: str,
        paragraph: etree._Element,
    ) -> Block:
        para_id_attr = f"{{{NAMESPACES['w14']}}}paraId"
        style_nodes = paragraph.xpath("./w:pPr/w:pStyle/@w:val", namespaces=NAMESPACES)
        style_id = style_nodes[0] if style_nodes else None
        para_id = paragraph.attrib.get(para_id_attr)
        return Block(
            block_id="",
            part=part_name,
            block_type=block_type,
            raw_text=text,
            style_id=style_id,
            para_id=para_id,
        )

    @staticmethod
    def _collect_text(node: etree._Element) -> str:
        texts = node.xpath(".//w:t/text()", namespaces=NAMESPACES)
        return "".join(texts)

    @staticmethod
    def _has_ancestor_tag(node: etree._Element, tag: str) -> bool:
        current = node.getparent()
        while current is not None:
            if current.tag == tag:
                return True
            current = current.getparent()
        return False

    @staticmethod
    def _paragraph_type(part_name: str) -> BlockType:
        if part_name == "footnotes.xml":
            return BlockType.FOOTNOTE_PARAGRAPH
        if part_name == "endnotes.xml":
            return BlockType.ENDNOTE_PARAGRAPH
        if part_name.startswith("header"):
            return BlockType.HEADER_PARAGRAPH
        if part_name.startswith("footer"):
            return BlockType.FOOTER_PARAGRAPH
        return BlockType.PARAGRAPH
