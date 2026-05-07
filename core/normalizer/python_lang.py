import ast
import io
import keyword
import token
import tokenize

from core.normalizer.base import BaseNormalizer

PYTHON_KEYWORDS = set(keyword.kwlist) | set(keyword.softkwlist)
IGNORED_TOKENS = {
    token.COMMENT,
    token.ENCODING,
    token.ENDMARKER,
    token.INDENT,
    token.DEDENT,
    token.NEWLINE,
    token.NL,
}


class PythonNormalizer(BaseNormalizer):
    extensions = [".py"]

    def normalize(self, code: str) -> str:
        return "".join(_normalized_tokens_by_line(code))

    def normalize_lines(self, code: str) -> list[str]:
        return _normalized_tokens_by_line(code)


def _normalized_tokens_by_line(code: str) -> list[str]:
    lines = code.splitlines()
    normalized_lines = [""] * len(lines)
    ignored_string_ranges = _standalone_string_ranges(code)

    try:
        tokens = tokenize.generate_tokens(io.StringIO(code).readline)
        for tok in tokens:
            normalized = _normalize_token(tok, ignored_string_ranges)
            if not normalized:
                continue

            line_number = tok.start[0] - 1
            if 0 <= line_number < len(normalized_lines):
                normalized_lines[line_number] += normalized
    except (IndentationError, tokenize.TokenError):
        # Incomplete submissions should still be comparable up to the point
        # Python's tokenizer can understand.
        pass

    return normalized_lines


def _standalone_string_ranges(code: str) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    ranges = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue

        value = node.value
        if not (
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and value.end_lineno is not None
            and value.end_col_offset is not None
        ):
            continue

        ranges.append(
            (
                (value.lineno, value.col_offset),
                (value.end_lineno, value.end_col_offset),
            )
        )

    return ranges


def _normalize_token(
    tok: tokenize.TokenInfo,
    ignored_string_ranges: list[tuple[tuple[int, int], tuple[int, int]]],
) -> str:
    token_type = tok.type
    value = tok.string

    if token_type in IGNORED_TOKENS:
        return ""
    if token_type == token.NAME:
        return value if value in PYTHON_KEYWORDS else "VAR"
    if token_type == token.STRING:
        if _is_token_in_range(tok, ignored_string_ranges):
            return ""
        return "STR"
    if token_type == token.NUMBER:
        return "NUM"

    return value


def _is_token_in_range(
    tok: tokenize.TokenInfo,
    ranges: list[tuple[tuple[int, int], tuple[int, int]]],
) -> bool:
    return any(start <= tok.start and tok.end <= end for start, end in ranges)
