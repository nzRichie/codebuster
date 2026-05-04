from core.normalizer.base import BaseNormalizer


CSHARP_KEYWORDS = {
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch",
    "char", "checked", "class", "const", "continue", "decimal", "default",
    "delegate", "do", "double", "else", "enum", "event", "explicit",
    "extern", "false", "finally", "fixed", "float", "for", "foreach",
    "goto", "if", "implicit", "in", "int", "interface", "internal", "is",
    "lock", "long", "namespace", "new", "null", "object", "operator",
    "out", "override", "params", "private", "protected", "public",
    "readonly", "ref", "return", "sbyte", "sealed", "short", "sizeof",
    "stackalloc", "static", "string", "struct", "switch", "this", "throw",
    "true", "try", "typeof", "uint", "ulong", "unchecked", "unsafe",
    "ushort", "using", "virtual", "void", "volatile", "while",
    # Contextual keywords that still carry useful structure.
    "add", "alias", "and", "ascending", "async", "await", "by",
    "descending", "dynamic", "equals", "file", "from", "get", "global",
    "group", "init", "into", "join", "let", "managed", "nameof", "not",
    "notnull", "on", "or", "orderby", "partial", "record", "remove",
    "required", "select", "set", "unmanaged", "var", "when",
    "where", "with", "yield",
}


class CSharpNormalizer(BaseNormalizer):
    extensions = [".cs"]

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

        if char == "@" and next_char == '"':
            _append(normalized_lines, line_index, "STR")
            i, line_index = _consume_verbatim_string(code, i + 2, line_index)
            continue

        if char == "$" and next_char == '"':
            _append(normalized_lines, line_index, "STR")
            i, line_index = _consume_string(code, i + 1, line_index)
            continue

        if char == "$" and next_char == "@":
            third_char = code[i + 2] if i + 2 < length else ""
            if third_char == '"':
                _append(normalized_lines, line_index, "STR")
                i, line_index = _consume_verbatim_string(code, i + 3, line_index)
                continue

        if char == '"' and _starts_raw_string(code, i):
            _append(normalized_lines, line_index, "STR")
            i, line_index = _consume_raw_string(code, i, line_index)
            continue

        if char == '"':
            _append(normalized_lines, line_index, "STR")
            i, line_index = _consume_string(code, i, line_index)
            continue

        if char == "'":
            _append(normalized_lines, line_index, "CHAR")
            i, line_index = _consume_char_literal(code, i, line_index)
            continue

        if char == "@" and _is_identifier_start(next_char):
            i = _consume_identifier(code, i + 1)
            _append(normalized_lines, line_index, "VAR")
            continue

        if _is_identifier_start(char):
            start = i
            i = _consume_identifier(code, i)
            word = code[start:i]
            _append(normalized_lines, line_index, word if word in CSHARP_KEYWORDS else "VAR")
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


def _consume_string(code: str, start: int, line_index: int) -> tuple[int, int]:
    i = start + 1
    while i < len(code):
        if code[i] == "\\":
            i += 2
            continue
        if code[i] == "\n":
            line_index += 1
            i += 1
            continue
        if code[i] == '"':
            return i + 1, line_index
        i += 1
    return i, line_index


def _consume_verbatim_string(code: str, start: int, line_index: int) -> tuple[int, int]:
    i = start
    while i < len(code):
        if code[i] == "\n":
            line_index += 1
            i += 1
            continue
        if code[i] == '"':
            if i + 1 < len(code) and code[i + 1] == '"':
                i += 2
                continue
            return i + 1, line_index
        i += 1
    return i, line_index


def _consume_raw_string(code: str, start: int, line_index: int) -> tuple[int, int]:
    quote_count = 0
    while start + quote_count < len(code) and code[start + quote_count] == '"':
        quote_count += 1

    delimiter = '"' * quote_count
    i = start + quote_count
    while i < len(code):
        if code.startswith(delimiter, i):
            return i + quote_count, line_index
        if code[i] == "\n":
            line_index += 1
        i += 1
    return i, line_index


def _consume_char_literal(code: str, start: int, line_index: int) -> tuple[int, int]:
    i = start + 1
    while i < len(code):
        if code[i] == "\\":
            i += 2
            continue
        if code[i] == "\n":
            line_index += 1
            i += 1
            continue
        if code[i] == "'":
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
    return char == "_" or char.isalpha()


def _is_identifier_part(char: str) -> bool:
    return char == "_" or char.isalnum()


def _starts_raw_string(code: str, start: int) -> bool:
    return code.startswith('"""', start)
