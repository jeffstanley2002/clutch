"""Python parsing backed by tree-sitter."""

from collections.abc import Iterator

import tree_sitter_python
from tree_sitter import Language, Node, Parser

from clutch.schemas import CodeChunk, ParsedCode, SymbolKind

DEFINITION_NODE_TYPES: dict[str, SymbolKind] = {
    "class_definition": "class",
    "function_definition": "function",
}


def parse_python_code(code: str, *, file_path: str = "pasted.py") -> ParsedCode:
    """Parse Python source into line-aware chunks."""

    parser = _build_parser()
    source_bytes = code.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    chunks = [
        _node_to_chunk(node, source_lines=code.splitlines(), file_path=file_path)
        for node in _iter_definition_nodes(root)
    ]

    if not chunks and code.strip():
        chunks.append(
            CodeChunk(
                file_path=file_path,
                language="python",
                symbol_name="<module>",
                symbol_kind="module",
                line_start=1,
                line_end=max(1, len(code.splitlines())),
                source_text=code,
            )
        )

    return ParsedCode(
        language="python",
        file_path=file_path,
        chunks=chunks,
        has_syntax_error=root.has_error,
    )


def _build_parser() -> Parser:
    parser = Parser()
    language = _python_language()

    if hasattr(parser, "set_language"):
        parser.set_language(language)
    else:
        parser.language = language

    return parser


def _python_language() -> Language:
    language = tree_sitter_python.language()
    if isinstance(language, Language):
        return language
    return Language(language)


def _iter_definition_nodes(root: Node) -> Iterator[Node]:
    stack = [root]
    seen_ranges: set[tuple[int, int]] = set()

    while stack:
        node = stack.pop()
        definition_node = _unwrap_definition_node(node)
        if definition_node is not None:
            node_range = (definition_node.start_byte, definition_node.end_byte)
            if node_range in seen_ranges:
                stack.extend(reversed(node.children))
                continue
            seen_ranges.add(node_range)
            yield definition_node

        stack.extend(reversed(node.children))


def _unwrap_definition_node(node: Node) -> Node | None:
    if node.type in DEFINITION_NODE_TYPES:
        return node

    if node.type != "decorated_definition":
        return None

    for child in node.children:
        if child.type in DEFINITION_NODE_TYPES:
            return child

    return None


def _node_to_chunk(
    node: Node, *, source_lines: list[str], file_path: str
) -> CodeChunk:
    line_start = node.start_point[0] + 1
    line_end = node.end_point[0] + 1
    name_node = node.child_by_field_name("name")
    name_bytes = name_node.text if name_node is not None else None
    symbol_name = name_bytes.decode("utf-8") if name_bytes else "<anonymous>"
    source_text = "\n".join(source_lines[line_start - 1 : line_end])

    return CodeChunk(
        file_path=file_path,
        language="python",
        symbol_name=symbol_name,
        symbol_kind=DEFINITION_NODE_TYPES[node.type],
        line_start=line_start,
        line_end=line_end,
        source_text=source_text,
    )
