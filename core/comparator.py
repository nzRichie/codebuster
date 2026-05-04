import os
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable

from core.scanner import FoundFile
from core.normalizer.base import get_normalizer


@dataclass
class FileStats:
    path: str
    folder: str
    line_count: int
    word_count: int
    char_count: int
    normalized_path: str


@dataclass
class ComparisonResult:
    file1: FileStats
    file2: FileStats
    similarity: float   # 0.0 – 1.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalized_path(original_path: str) -> str:
    """Return the path where the normalized version of a file will be saved."""
    base, ext = os.path.splitext(original_path)
    return f"{base}.normalized{ext}"


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _file_stats(found: FoundFile, normalized_path: str) -> FileStats:
    raw = _read(found.path)
    return FileStats(
        path=found.path,
        folder=found.folder,
        line_count=raw.count("\n") + (1 if raw and not raw.endswith("\n") else 0),
        word_count=len(raw.split()),
        char_count=len(raw),
        normalized_path=normalized_path,
    )


def _comparison_group(found: FoundFile, only_matching_filenames: bool) -> str:
    if only_matching_filenames:
        return os.path.basename(found.path)
    return found.comparison_group or os.path.basename(found.path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_and_save(found: FoundFile) -> tuple[str, str]:
    """
    Normalize the file, save the result next to the original, and return
    (original_content, normalized_content).
    """
    normalizer = get_normalizer(os.path.basename(found.path))
    original = _read(found.path)
    normalized = normalizer.normalize(original)
    norm_path = _normalized_path(found.path)
    _write(norm_path, normalized)
    return original, normalized


def compare_files(
    files: list[FoundFile],
    progress_callback: Callable[[int, int], None] | None = None,
    only_matching_filenames: bool = False,
) -> tuple[list[FileStats], list[ComparisonResult]]:
    """
    Normalize every file (saving the result to disk), then pairwise-compare
    files that share a comparison group.

    If only_matching_filenames is true, files are grouped by basename even when
    they were discovered by extension.

    progress_callback(completed_pairs, total_pairs) is called after each pair.
    Returns (file_stats_list, comparison_results_list).
    """
    # Normalize all files first
    norm_cache: dict[str, str] = {}   # path -> normalized text
    stats_list: list[FileStats] = []
    comparable_files: list[FoundFile] = []

    for found in files:
        _orig, normalized = normalize_and_save(found)
        if not normalized:
            continue

        norm_cache[found.path] = normalized
        comparable_files.append(found)
        norm_path = _normalized_path(found.path)
        stats_list.append(_file_stats(found, norm_path))

    # Pairwise comparisons, grouped by target filename or extension unless the
    # caller asks to compare only files with matching basenames.
    files_by_name: dict[str, list[FoundFile]] = defaultdict(list)
    for found in comparable_files:
        group = _comparison_group(found, only_matching_filenames)
        files_by_name[group].append(found)

    total_pairs = sum(
        len(group) * (len(group) - 1) // 2
        for group in files_by_name.values()
    )
    done = 0
    results: list[ComparisonResult] = []

    stats_by_path = {s.path: s for s in stats_list}

    for group in files_by_name.values():
        n = len(group)
        for i in range(n):
            for j in range(i + 1, n):
                t1 = norm_cache[group[i].path]
                t2 = norm_cache[group[j].path]
                sim = SequenceMatcher(None, t1, t2).ratio()
                results.append(ComparisonResult(
                    file1=stats_by_path[group[i].path],
                    file2=stats_by_path[group[j].path],
                    similarity=round(sim, 6),
                ))
                done += 1
                if progress_callback:
                    progress_callback(done, total_pairs)

    results.sort(key=lambda r: -r.similarity)
    return stats_list, results
