from clutch.parsing import parse_python_code


def test_parse_python_code_extracts_line_aware_chunks() -> None:
    parsed = parse_python_code(
        "\n".join(
            [
                "class Cart:",
                "    def total(self):",
                "        return 0",
                "",
                "def helper():",
                "    return True",
            ]
        )
    )

    chunks = {(chunk.symbol_kind, chunk.symbol_name): chunk for chunk in parsed.chunks}

    assert parsed.language == "python"
    assert parsed.has_syntax_error is False
    assert chunks[("class", "Cart")].line_start == 1
    assert chunks[("class", "Cart")].line_end == 3
    assert chunks[("function", "total")].line_start == 2
    assert chunks[("function", "helper")].line_start == 5


def test_parse_python_code_falls_back_to_module_chunk() -> None:
    parsed = parse_python_code("value = 42\nprint(value)\n")

    assert len(parsed.chunks) == 1
    chunk = parsed.chunks[0]
    assert chunk.symbol_kind == "module"
    assert chunk.symbol_name == "<module>"
    assert chunk.line_start == 1
    assert chunk.line_end == 2
