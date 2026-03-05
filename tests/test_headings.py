from __future__ import annotations

from lxml import etree

from prospectus_sentence_indexer.extract import NAMESPACES
from prospectus_sentence_indexer.headings import HeadingResolver
from prospectus_sentence_indexer.models import Block, BlockType

W_NS = NAMESPACES["w"]


def _styles_xml(body: str):
    return etree.fromstring(f"<w:styles xmlns:w=\"{W_NS}\">{body}</w:styles>")


def _block(text: str, style_id: str | None = None) -> Block:
    return Block(
        block_id="B000001",
        part="document.xml",
        block_type=BlockType.PARAGRAPH,
        raw_text=text,
        style_id=style_id,
    )


def test_parse_styles_outlineLvl() -> None:
    styles = _styles_xml(
        """
        <w:style w:type="paragraph" w:styleId="H1">
            <w:name w:val="Custom"/>
            <w:pPr><w:outlineLvl w:val="0"/></w:pPr>
        </w:style>
        """
    )
    resolver = HeadingResolver(styles)

    assert resolver.resolve_heading_level("H1") == 1


def test_parse_styles_heading_names() -> None:
    styles = _styles_xml(
        """
        <w:style w:type="paragraph" w:styleId="Heading2">
            <w:name w:val="Heading 2"/>
        </w:style>
        """
    )
    resolver = HeadingResolver(styles)

    assert resolver.resolve_heading_level("Heading2") == 2


def test_build_heading_path() -> None:
    styles = _styles_xml(
        """
        <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="Heading 1"/></w:style>
        <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="Heading 2"/></w:style>
        """
    )
    resolver = HeadingResolver(styles)
    blocks = [
        _block("1 Business", "Heading1"),
        _block("1.2 Products", "Heading2"),
        _block("Paragraph text", None),
    ]

    out = resolver.build_heading_paths(blocks)

    assert out[0].heading_path == "1 Business"
    assert out[1].heading_path == "1 Business > 1.2 Products"
    assert out[2].heading_path == "1 Business > 1.2 Products"


def test_heading_inheritance() -> None:
    styles = _styles_xml(
        """
        <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="Heading 1"/></w:style>
        """
    )
    resolver = HeadingResolver(styles)
    blocks = [_block("1 Business", "Heading1"), _block("Body.")]

    out = resolver.build_heading_paths(blocks)

    assert out[1].heading_level == 0
    assert out[1].heading_path == "1 Business"


def test_same_level_heading_replace() -> None:
    styles = _styles_xml(
        """
        <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="Heading 1"/></w:style>
        """
    )
    resolver = HeadingResolver(styles)
    blocks = [
        _block("1 Business", "Heading1"),
        _block("2 Risk Factors", "Heading1"),
        _block("Body."),
    ]

    out = resolver.build_heading_paths(blocks)

    assert out[1].heading_path == "2 Risk Factors"
    assert out[2].heading_path == "2 Risk Factors"


def test_style_level_override() -> None:
    styles = _styles_xml(
        """
        <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/></w:style>
        """
    )
    resolver = HeadingResolver(styles, style_level_overrides={"Title": 1})

    assert resolver.resolve_heading_level("Title", "Company Overview") == 1


def test_based_on_inheritance() -> None:
    styles = _styles_xml(
        """
        <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="Heading 2"/></w:style>
        <w:style w:type="paragraph" w:styleId="CustomSubhead"><w:basedOn w:val="Heading2"/></w:style>
        """
    )
    resolver = HeadingResolver(styles)

    assert resolver.resolve_heading_level("CustomSubhead", "Subsection") == 2


def test_text_fallback_numbered_heading() -> None:
    resolver = HeadingResolver(None)
    assert resolver.resolve_heading_level(None, "1.2 Products and Services") == 2


def test_text_fallback_uppercase_heading() -> None:
    resolver = HeadingResolver(None)
    assert resolver.resolve_heading_level(None, "RISK FACTORS") == 1
