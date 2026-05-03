import re
from core.normalizer.base import BaseNormalizer

# Keywords that should NOT be replaced with VAR so structural
# patterns (if/for/while/return etc.) remain visible in the diff.
JAVA_KEYWORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch",
    "char", "class", "const", "continue", "default", "do", "double",
    "else", "enum", "extends", "final", "finally", "float", "for",
    "goto", "if", "implements", "import", "instanceof", "int",
    "interface", "long", "native", "new", "package", "private",
    "protected", "public", "return", "short", "static", "strictfp",
    "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "void", "volatile", "while",
    # Common literals
    "true", "false", "null",
}


class JavaNormalizer(BaseNormalizer):
    extensions = [".java"]

    def normalize(self, code: str) -> str:
        # Strip line comments and block comments
        code = re.sub(r'//.*?$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)

        # Replace user-defined identifiers with VAR, leaving keywords intact
        def _replace(m: re.Match) -> str:
            word = m.group(0)
            return word if word in JAVA_KEYWORDS else "VAR"

        code = re.sub(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', _replace, code)

        # Collapse all whitespace
        code = re.sub(r'\s+', '', code)

        return code

    def normalize_lines(self, code: str) -> list[str]:
        # Remove block comments from the full text first so that lines which
        # are entirely inside a /* ... */ block collapse to empty strings.
        code = re.sub(
            r'/\*.*?\*/',
            lambda m: "\n" * m.group(0).count("\n"),
            code,
            flags=re.DOTALL,
        )

        def _replace(m: re.Match) -> str:
            word = m.group(0)
            return word if word in JAVA_KEYWORDS else "VAR"

        result = []
        for line in code.splitlines():
            line = re.sub(r'//.*?$', '', line)
            line = re.sub(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', _replace, line)
            line = re.sub(r'\s+', '', line)
            result.append(line)
        return result
