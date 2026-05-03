import re
from core.normalizer.base import BaseNormalizer

PYTHON_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
    "while", "with", "yield",
}


class PythonNormalizer(BaseNormalizer):
    extensions = [".py"]

    def normalize(self, code: str) -> str:
        # Strip inline comments
        code = re.sub(r'#.*?$', '', code, flags=re.MULTILINE)

        # Strip docstrings / triple-quoted strings
        code = re.sub(r'""".*?"""', '""', code, flags=re.DOTALL)
        code = re.sub(r"'''.*?'''", "''", code, flags=re.DOTALL)

        def _replace(m: re.Match) -> str:
            word = m.group(0)
            return word if word in PYTHON_KEYWORDS else "VAR"

        code = re.sub(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', _replace, code)

        code = re.sub(r'\s+', '', code)

        return code

    def normalize_lines(self, code: str) -> list[str]:
        # Remove triple-quoted strings from the full text first so that lines
        # which are entirely inside a docstring collapse to empty strings.
        code = re.sub(
            r'""".*?"""',
            lambda m: "\n" * m.group(0).count("\n"),
            code,
            flags=re.DOTALL,
        )
        code = re.sub(
            r"'''.*?'''",
            lambda m: "\n" * m.group(0).count("\n"),
            code,
            flags=re.DOTALL,
        )

        def _replace(m: re.Match) -> str:
            word = m.group(0)
            return word if word in PYTHON_KEYWORDS else "VAR"

        result = []
        for line in code.splitlines():
            line = re.sub(r'#.*?$', '', line)
            line = re.sub(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', _replace, line)
            line = re.sub(r'\s+', '', line)
            result.append(line)
        return result
