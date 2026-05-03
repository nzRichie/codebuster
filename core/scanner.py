import os
from dataclasses import dataclass


@dataclass
class FoundFile:
    path: str        # absolute path to the source file
    folder: str      # immediate parent directory name (student identifier)


def find_files(root_dir: str, target_names: list[str]) -> list[FoundFile]:
    """
    Walk root_dir recursively and collect every file whose basename
    matches one of the names in target_names (case-sensitive).
    """
    target_set = set(target_names)
    results: list[FoundFile] = []

    for dirpath, _dirs, files in os.walk(root_dir):
        for filename in files:
            if filename in target_set:
                full_path = os.path.join(dirpath, filename)
                folder_name = os.path.basename(dirpath)
                results.append(FoundFile(path=full_path, folder=folder_name))

    return results
