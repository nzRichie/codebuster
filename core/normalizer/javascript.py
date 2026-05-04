from core.normalizer.base import BaseNormalizer


JAVASCRIPT_KEYWORDS = {
    "abstract", "arguments", "as", "async", "await", "boolean", "break",
    "case", "catch", "class", "const", "constructor", "continue", "debugger",
    "declare", "default", "delete", "do", "else", "enum", "export", "extends",
    "false", "finally", "for", "from", "function", "get", "if", "implements",
    "import", "in", "infer", "instanceof", "interface", "is", "keyof", "let",
    "module", "namespace", "never", "new", "null", "number", "object", "of",
    "package", "private", "protected", "public", "readonly", "require",
    "return", "satisfies", "set", "static", "string", "super", "switch",
    "symbol", "this", "throw", "true", "try", "type", "typeof", "undefined",
    "unknown", "var", "void", "while", "with", "yield",
}


class JavaScriptNormalizer(BaseNormalizer):
    extensions = [".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"]

    def normalize(self, code: str) -> str:
        return "".join(_normalized_tokens_by_line(code))

    def normalize_lines(self, code: str) -> list[str]:
        return _normalized_tokens_by_line(code)


def _normalized_tokens_by_line(code: str) -> list[str]:
    lines = code.splitlines()
    normalized_lines = [""] * len(lines)

    i = 0
    line_index = 0
    length = len(code)

    while i < length:
        char = code[i]
        next_char = code[i + 1] if i + 1 < length else ""

        if char == "\n":
            line_index += 1
            i += 1
            continue

        if char.isspace():
            i += 1
            continue

        if char == "/" and next_char == "/":
            i = _consume_line_comment(code, i)
            continue

        if char == "/" and next_char == "*":
            i, line_index = _consume_block_comment(code, i, line_index)
            continue

        if char in ('"', "'"):
            _append(normalized_lines, line_index, "STR")
            i, line_index = _consume_quoted_string(code, i, line_index)
            continue

        if char == "`":
            _append(normalized_lines, line_index, "STR")
            i, line_index = _consume_template_literal(code, i, line_index)
            continue

        if _is_identifier_start(char):
            start = i
            i = _consume_identifier(code, i)
            word = code[start:i]
            _append(
                normalized_lines,
                line_index,
                word if word in JAVASCRIPT_KEYWORDS else "VAR",
            )
            continue

        if char.isdigit():
            i = _consume_number(code, i)
            _append(normalized_lines, line_index, "NUM")
            continue

        _append(normalized_lines, line_index, char)
        i += 1

    return normalized_lines


def _append(lines: list[str], line_index: int, value: str) -> None:
    if 0 <= line_index < len(lines):
        lines[line_index] += value


def _consume_line_comment(code: str, start: int) -> int:
    i = start + 2
    while i < len(code) and code[i] != "\n":
        i += 1
    return i


def _consume_block_comment(code: str, start: int, line_index: int) -> tuple[int, int]:
    i = start + 2
    while i < len(code):
        if code[i] == "\n":
            line_index += 1
            i += 1
            continue
        if code[i] == "*" and i + 1 < len(code) and code[i + 1] == "/":
            return i + 2, line_index
        i += 1
    return i, line_index


def _consume_quoted_string(code: str, start: int, line_index: int) -> tuple[int, int]:
    quote = code[start]
    i = start + 1
    while i < len(code):
        if code[i] == "\\":
            i += 2
            continue
        if code[i] == "\n":
            line_index += 1
            i += 1
            continue
        if code[i] == quote:
            return i + 1, line_index
        i += 1
    return i, line_index


def _consume_template_literal(code: str, start: int, line_index: int) -> tuple[int, int]:
    i = start + 1
    while i < len(code):
        if code[i] == "\\":
            i += 2
            continue
        if code[i] == "\n":
            line_index += 1
            i += 1
            continue
        if code[i] == "`":
            return i + 1, line_index
        i += 1
    return i, line_index


def _consume_identifier(code: str, start: int) -> int:
    i = start + 1
    while i < len(code) and _is_identifier_part(code[i]):
        i += 1
    return i


def _consume_number(code: str, start: int) -> int:
    i = start + 1
    while i < len(code) and (code[i].isalnum() or code[i] in "._"):
        i += 1
    return i


def _is_identifier_start(char: str) -> bool:
    return char in "_$" or char.isalpha()


def _is_identifier_part(char: str) -> bool:
    return char in "_$" or char.isalnum()
