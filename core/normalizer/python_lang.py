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

    try:
        tokens = tokenize.generate_tokens(io.StringIO(code).readline)
        for tok in tokens:
            normalized = _normalize_token(tok)
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


def _normalize_token(tok: tokenize.TokenInfo) -> str:
    token_type = tok.type
    value = tok.string

    if token_type in IGNORED_TOKENS:
        return ""
    if token_type == token.NAME:
        return value if value in PYTHON_KEYWORDS else "VAR"
    if token_type == token.STRING:
        return "STR"
    if token_type == token.NUMBER:
        return "NUM"

    return value
