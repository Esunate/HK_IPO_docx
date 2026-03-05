from __future__ import annotations

import re

from lxml import etree

from .extract import NAMESPACES
from .models import Block


class HeadingResolver:
    def __init__(
        self,
        styles_xml: etree._Element | None,
        style_level_overrides: dict[str, int] | None = None,
        use_text_fallback: bool = True,
        max_heading_level: int = 9,
    ):
        self.styles_xml = styles_xml
        self.use_text_fallback = use_text_fallback
        self.max_heading_level = max_heading_level
        self._override_map = self._normalize_overrides(style_level_overrides or {})
        self._style_level_map = self._build_style_level_map(styles_xml)

    def resolve_heading_level(self, style_id: str | None, para_text: str = "") -> int:
        if style_id and style_id in self._style_level_map:
            return self._style_level_map[style_id]

        if self.use_text_fallback:
            return self._resolve_from_text(para_text)
        return 0

    def build_heading_paths(self, blocks: list[Block]) -> list[Block]:
        stack: list[tuple[int, str]] = []

        for block in blocks:
            level = block.heading_level
            if level == 0:
                level = self.resolve_heading_level(block.style_id, block.raw_text)

            if level > 0:
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, block.raw_text.strip()))
                block.heading_level = level
                block.heading_path = " > ".join(item[1] for item in stack)
            else:
                block.heading_path = " > ".join(item[1] for item in stack)

        return blocks

    def _build_style_level_map(self, styles_xml: etree._Element | None) -> dict[str, int]:
        if styles_xml is None:
            return {}

        style_nodes: dict[str, etree._Element] = {}
        for style in styles_xml.xpath(".//w:style", namespaces=NAMESPACES):
            style_id = style.get(f"{{{NAMESPACES['w']}}}styleId")
            if style_id:
                style_nodes[style_id] = style

        resolved: dict[str, int] = {}
        for style_id in style_nodes:
            level = self._resolve_style_level(style_id, style_nodes, resolved, set())
            if level > 0:
                resolved[style_id] = level
        return resolved

    def _resolve_style_level(
        self,
        style_id: str,
        style_nodes: dict[str, etree._Element],
        cache: dict[str, int],
        visiting: set[str],
    ) -> int:
        if style_id in cache:
            return cache[style_id]
        if style_id in visiting:
            return 0

        style = style_nodes.get(style_id)
        if style is None:
            return 0

        visiting.add(style_id)

        outline_vals = style.xpath("./w:pPr/w:outlineLvl/@w:val", namespaces=NAMESPACES)
        if outline_vals:
            level = self._clamp_level(int(outline_vals[0]) + 1)
            cache[style_id] = level
            visiting.remove(style_id)
            return level

        name_candidates = style.xpath("./w:name/@w:val", namespaces=NAMESPACES)
        alias_candidates = style.xpath("./w:aliases/@w:val", namespaces=NAMESPACES)
        style_name = " ".join(name_candidates + alias_candidates + [style_id])

        override_level = self._lookup_override(style_id, style_name)
        if override_level > 0:
            cache[style_id] = override_level
            visiting.remove(style_id)
            return override_level

        match = re.search(r"heading\s*(\d{1,2})", style_name, flags=re.IGNORECASE)
        if match:
            level = self._clamp_level(int(match.group(1)))
            cache[style_id] = level
            visiting.remove(style_id)
            return level

        based_on_ids = style.xpath("./w:basedOn/@w:val", namespaces=NAMESPACES)
        if based_on_ids:
            parent_level = self._resolve_style_level(based_on_ids[0], style_nodes, cache, visiting)
            if parent_level > 0:
                cache[style_id] = parent_level
                visiting.remove(style_id)
                return parent_level

        cache[style_id] = 0
        visiting.remove(style_id)
        return 0

    def _resolve_from_text(self, para_text: str) -> int:
        text = para_text.strip()
        if not text:
            return 0

        numbered = re.match(r"^(?:Section\s+)?(\d+(?:\.\d+){0,8})(?:[.)]|\s)", text, flags=re.IGNORECASE)
        if numbered:
            return self._clamp_level(numbered.group(1).count(".") + 1)

        letters = re.sub(r"[^A-Za-z]", "", text)
        words = text.split()
        if (
            len(text) <= 80
            and 2 <= len(words) <= 12
            and len(letters) >= 4
            and text == text.upper()
            and not re.search(r"[.!?]$", text)
        ):
            return 1

        return 0

    def _lookup_override(self, style_id: str, style_name: str) -> int:
        if style_id in self._override_map:
            return self._override_map[style_id]

        for token in style_name.split():
            if token in self._override_map:
                return self._override_map[token]

        lowered = style_name.lower()
        for key, level in self._override_map.items():
            if key.lower() == lowered:
                return level
        return 0

    def _normalize_overrides(self, mapping: dict[str, int]) -> dict[str, int]:
        out: dict[str, int] = {}
        for key, value in mapping.items():
            if not isinstance(key, str):
                continue
            try:
                level = self._clamp_level(int(value))
            except (TypeError, ValueError):
                continue
            out[key] = level
        return out

    def _clamp_level(self, level: int) -> int:
        if level <= 0:
            return 0
        return min(level, self.max_heading_level)
