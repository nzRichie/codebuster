from abc import ABC, abstractmethod
import re


class BaseNormalizer(ABC):
    """
    Abstract base for language-specific code normalizers.
    Subclasses strip comments, whitespace, and replace identifiers
    so that structurally identical code looks identical regardless
    of variable naming or formatting choices.
    """

    # File extensions this normalizer handles, e.g. ['.java']
    extensions: list[str] = []

    @abstractmethod
    def normalize(self, code: str) -> str:
        """Return a normalized version of the source code."""
        ...

    def normalize_lines(self, code: str) -> list[str]:
        """Return one normalized string per original line.

        Lines that are entirely comments or whitespace normalize to ''.
        Subclasses should override this to apply full-text pre-processing
        (e.g. block-comment removal) before per-line normalization.
        """
        return [re.sub(r'\s+', '', line) for line in code.splitlines()]

    @classmethod
    def handles(cls, filename: str) -> bool:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in cls.extensions


def get_normalizer(filename: str) -> "BaseNormalizer":
    """
    Return the appropriate normalizer for the given filename, falling
    back to a plain whitespace-stripping normalizer if none matches.
    """
    from core.normalizer.csharp import CSharpNormalizer
    from core.normalizer.java import JavaNormalizer
    from core.normalizer.python_lang import PythonNormalizer

    for cls in (JavaNormalizer, PythonNormalizer, CSharpNormalizer):
        if cls.handles(filename):
            return cls()

    return GenericNormalizer()


class GenericNormalizer(BaseNormalizer):
    """Strips whitespace only — works for any plain-text file."""

    extensions = []

    def normalize(self, code: str) -> str:
        import re
        code = re.sub(r'\s+', '', code)
        return code
