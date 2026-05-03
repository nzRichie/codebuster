import os
import re
import csv
from difflib import SequenceMatcher

def find_files(root_dir, target_name="MergeRuns.java"):
    matches = []
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file == target_name:
                full_path = os.path.join(root, file)
                folder_name = os.path.basename(root)
                matches.append((full_path, folder_name))
    return matches

def normalize_java(code):
    # Remove comments
    code = re.sub(r'//.*?$|/\*.*?\*/', '', code,
                  flags=re.DOTALL | re.MULTILINE)

    # Replace identifiers (variable/function names)
    code = re.sub(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', 'VAR', code)

    # Remove whitespace
    code = re.sub(r'\s+', '', code)

    return code

def file_similarity(file1, file2):
    with open(file1, 'r', encoding='utf-8', errors='ignore') as f1, \
         open(file2, 'r', encoding='utf-8', errors='ignore') as f2:

        text1 = normalize_java(f1.read())
        text2 = normalize_java(f2.read())

    return SequenceMatcher(None, text1, text2).ratio()

def compare_all(files):
    results = []
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            file1, folder1 = files[i]
            file2, folder2 = files[j]

            sim = file_similarity(file1, file2)

            results.append({
                "student1": folder1,
                "student2": folder2,
                "file1": file1,
                "file2": file2,
                "similarity": round(sim, 4)
            })

    return results

def write_csv(results, output_file="merge_similarity_report.csv"):
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ["student1", "student2", "similarity", "file1", "file2"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()

        # Sort by similarity descending
        for row in sorted(results, key=lambda x: -x["similarity"]):
            writer.writerow(row)

if __name__ == "__main__":
    root = "./"  # change this
    
    files = find_files(root)
    results = compare_all(files)

    write_csv(results)

    print("CSV report generated: similarity_report.csv")