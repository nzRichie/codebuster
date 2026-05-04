import os
from dataclasses import dataclass


@dataclass
class FoundFile:
    path: str                  # absolute path to the source file
    folder: str                # immediate parent directory name (student identifier)
    comparison_group: str = "" # basename for exact matches, extension for type scans


def find_files(root_dir: str, target_names: list[str]) -> list[FoundFile]:
    """
    Walk root_dir recursively and collect every file whose basename matches one
    of the names in target_names, or whose extension matches an extension
    target such as ".py", "py", ".cs", or "cs".
    """
    exact_names, extensions = _parse_targets(target_names)
    results: list[FoundFile] = []

    for dirpath, dirs, files in os.walk(root_dir):
        dirs[:] = [dirname for dirname in dirs if not _is_ignored_metadata_dir(dirname)]

        for filename in files:
            if _is_generated_normalized_file(filename) or _is_ignored_metadata_file(filename):
                continue

            ext = os.path.splitext(filename)[1].lower()
            if filename in exact_names or ext in extensions:
                full_path = os.path.join(dirpath, filename)
                folder_name = os.path.basename(dirpath)
                group = filename if filename in exact_names else ext
                results.append(
                    FoundFile(
                        path=full_path,
                        folder=folder_name,
                        comparison_group=group,
                    )
                )

    return results


def _parse_targets(target_names: list[str]) -> tuple[set[str], set[str]]:
    exact_names: set[str] = set()
    extensions: set[str] = set()

    for raw_target in target_names:
        target = raw_target.strip()
        if not target:
            continue

        if _looks_like_extension(target):
            extension = target if target.startswith(".") else f".{target}"
            extensions.add(extension.lower())
        else:
            exact_names.add(target)

    return exact_names, extensions


def _looks_like_extension(target: str) -> bool:
    if target.startswith("."):
        return target.count(".") == 1 and len(target) > 1

    return "." not in target


def _is_generated_normalized_file(filename: str) -> bool:
    return filename.endswith(".normalized") or ".normalized." in filename


def _is_ignored_metadata_dir(dirname: str) -> bool:
    return dirname == "__MACOSX"


def _is_ignored_metadata_file(filename: str) -> bool:
    return filename.startswith("._") or filename == ".DS_Store"
