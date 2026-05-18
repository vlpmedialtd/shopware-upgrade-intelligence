"""Tree-sitter based PHP chunker.

Emits one chunk per method plus a class-header chunk with docblock + signature.
Yields roughly 3-4x more chunks than the regex class-level chunker but each chunk
is semantically tighter, which sharply improves retrieval for 'where is method X'
and 'what does method Y do' type questions.
"""

from __future__ import annotations

import re
from threading import Lock
from typing import Any

import tree_sitter_php
from tree_sitter import Language, Parser

from shopware_intel.ingest.chunk.base import Chunk

_PARSER: Parser | None = None
_PARSER_LOCK = Lock()

DEPRECATED_TAG_RE = re.compile(r"@deprecated\s+tag:(v6\.\d+\.\d+(?:\.\d+)?)")

MAX_BODY = 2000

TYPE_DECL_TYPES = frozenset(
    {"class_declaration", "interface_declaration", "trait_declaration", "enum_declaration"}
)


def _get_parser() -> Parser:
    global _PARSER
    with _PARSER_LOCK:
        if _PARSER is None:
            _PARSER = Parser(Language(tree_sitter_php.language_php()))
        return _PARSER


def _node_text(source: bytes, node: Any) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _find_namespace(root: Any, source: bytes) -> str:
    for child in root.children:
        if child.type == "namespace_definition":
            for sub in child.children:
                if sub.type == "namespace_name":
                    return _node_text(source, sub)
    return ""


def _find_deprecated(text: str) -> str | None:
    last = None
    for m in DEPRECATED_TAG_RE.finditer(text):
        last = m.group(1)
    return last


def _docblock_before(source: bytes, node: Any) -> str:
    """Walk previous siblings, skip attribute/modifier nodes, return the docblock if any."""
    sibling = node.prev_sibling
    while sibling is not None:
        if sibling.type == "comment":
            txt = _node_text(source, sibling)
            if txt.lstrip().startswith("/**"):
                return txt
            sibling = sibling.prev_sibling
            continue
        if sibling.type in (
            "attribute_list",
            "visibility_modifier",
            "static_modifier",
            "abstract_modifier",
            "final_modifier",
            "readonly_modifier",
        ):
            sibling = sibling.prev_sibling
            continue
        break
    return ""


def _line_of_byte(source: bytes, byte_offset: int) -> int:
    return source[:byte_offset].count(b"\n") + 1


def _emit_method_chunk(
    chunks: list[Chunk],
    source: bytes,
    method_node: Any,
    *,
    class_name: str,
    class_fqn: str,
    file_path: str,
    area: str,
) -> None:
    name_node = method_node.child_by_field_name("name")
    if name_node is None:
        for c in method_node.children:
            if c.type == "name":
                name_node = c
                break
    if name_node is None:
        return
    method_name = _node_text(source, name_node)
    fqn = f"{class_fqn}::{method_name}" if class_fqn else method_name
    doc = _docblock_before(source, method_node)
    body_text = _node_text(source, method_node)
    if len(body_text) > MAX_BODY:
        body_text = body_text[:MAX_BODY]
    content = (doc + "\n" + body_text).strip() if doc else body_text
    deprecated_in = _find_deprecated(doc) if doc else None
    chunks.append(
        Chunk(
            file_path=file_path,
            language="php",
            area=area,
            content=content[:MAX_BODY],
            start_line=_line_of_byte(source, method_node.start_byte),
            end_line=_line_of_byte(source, method_node.end_byte),
            symbol_kind="method",
            symbol_name=method_name,
            symbol_fqn=fqn,
            deprecated_in=deprecated_in,
            extra={"class": class_name} if class_name else {},
        )
    )


def _emit_class_header_chunk(
    chunks: list[Chunk],
    source: bytes,
    class_node: Any,
    *,
    namespace: str,
    file_path: str,
    area: str,
) -> tuple[str, str]:
    name_node = class_node.child_by_field_name("name")
    if name_node is None:
        for c in class_node.children:
            if c.type == "name":
                name_node = c
                break
    if name_node is None:
        return "", ""
    class_name = _node_text(source, name_node)
    fqn = f"{namespace}\\{class_name}" if namespace else class_name
    doc = _docblock_before(source, class_node)
    body = class_node.child_by_field_name("body")
    if body is None:
        for c in class_node.children:
            if c.type in ("declaration_list", "enum_declaration_list"):
                body = c
                break
    header_end = body.start_byte if body is not None else class_node.end_byte
    header = source[class_node.start_byte : header_end].decode("utf-8", errors="replace").rstrip()
    full = ((doc + "\n") if doc else "") + header
    deprecated_in = _find_deprecated(doc) if doc else None
    chunks.append(
        Chunk(
            file_path=file_path,
            language="php",
            area=area,
            content=full[:MAX_BODY],
            start_line=_line_of_byte(source, class_node.start_byte),
            end_line=_line_of_byte(source, class_node.end_byte),
            symbol_kind=class_node.type.replace("_declaration", ""),
            symbol_name=class_name,
            symbol_fqn=fqn,
            deprecated_in=deprecated_in,
        )
    )
    return class_name, fqn


def _walk_class_methods(class_node: Any) -> list[Any]:
    body = class_node.child_by_field_name("body")
    if body is None:
        for c in class_node.children:
            if c.type in ("declaration_list", "enum_declaration_list"):
                body = c
                break
    if body is None:
        return []
    return [child for child in body.children if child.type == "method_declaration"]


def chunk_php_ts(content: str, *, file_path: str, area: str) -> list[Chunk]:
    """Method-level PHP chunker. Returns class-header + per-method chunks per
    class/interface/trait/enum, or a single file-level chunk for procedural files."""
    source = content.encode("utf-8", errors="replace")
    parser = _get_parser()
    tree = parser.parse(source)
    root = tree.root_node
    namespace = _find_namespace(root, source)
    chunks: list[Chunk] = []

    found_any = False
    for child in root.children:
        if child.type in TYPE_DECL_TYPES:
            found_any = True
            class_name, class_fqn = _emit_class_header_chunk(
                chunks, source, child, namespace=namespace, file_path=file_path, area=area
            )
            for method in _walk_class_methods(child):
                _emit_method_chunk(
                    chunks,
                    source,
                    method,
                    class_name=class_name,
                    class_fqn=class_fqn,
                    file_path=file_path,
                    area=area,
                )

    if not found_any:
        chunks.append(
            Chunk(
                file_path=file_path,
                language="php",
                area=area,
                content=content[:MAX_BODY],
                start_line=1,
                end_line=content.count("\n") + 1,
                symbol_kind="file",
                symbol_name=file_path.rsplit("/", 1)[-1],
            )
        )

    return chunks
