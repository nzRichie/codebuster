import os
import tempfile
import unittest

from core.comparator import compare_files
from core.normalizer.base import get_normalizer
from core.normalizer.csharp import CSharpNormalizer
from core.normalizer.javascript import JavaScriptNormalizer
from core.normalizer.python_lang import PythonNormalizer
from core.scanner import FoundFile, find_files


class ScannerTests(unittest.TestCase):
    def test_find_files_supports_names_extensions_and_ignores_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            student = os.path.join(root, "student-a")
            os.mkdir(student)
            for filename in (
                "Assignment1.java",
                "solution.py",
                "Program.cs",
                "app.jsx",
                "solution.normalized.py",
                "._Program.cs",
                "notes.txt",
            ):
                with open(os.path.join(student, filename), "w", encoding="utf-8") as fh:
                    fh.write("")

            macosx = os.path.join(root, "__MACOSX", "student-a")
            os.makedirs(macosx)
            with open(os.path.join(macosx, "Assignment1.java"), "w", encoding="utf-8") as fh:
                fh.write("")

            found = find_files(root, ["Assignment1.java", ".py", "cs", "jsx"])
            by_name = {os.path.basename(item.path): item for item in found}

            self.assertEqual(
                set(by_name),
                {"Assignment1.java", "solution.py", "Program.cs", "app.jsx"},
            )
            self.assertEqual(by_name["Assignment1.java"].comparison_group, "Assignment1.java")
            self.assertEqual(by_name["solution.py"].comparison_group, ".py")
            self.assertEqual(by_name["Program.cs"].comparison_group, ".cs")
            self.assertEqual(by_name["app.jsx"].comparison_group, ".jsx")


class ComparatorTests(unittest.TestCase):
    def test_extension_scan_compares_files_with_different_basenames(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            student_a = os.path.join(root, "student-a")
            student_b = os.path.join(root, "student-b")
            os.mkdir(student_a)
            os.mkdir(student_b)

            path_a = os.path.join(student_a, "answer.py")
            path_b = os.path.join(student_b, "submission.py")
            for path in (path_a, path_b):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("def solve(value):\n    return value + 1\n")

            _stats, comparisons = compare_files(
                [
                    FoundFile(path=path_a, folder="student-a", comparison_group=".py"),
                    FoundFile(path=path_b, folder="student-b", comparison_group=".py"),
                ]
            )

            self.assertEqual(len(comparisons), 1)
            self.assertEqual(comparisons[0].similarity, 1.0)

    def test_matching_filename_option_filters_extension_scan_pairs(self) -> None:
        examples = {
            ".java": "public class Answer { int solve(int value) { return value + 1; } }\n",
            ".cs": "class Answer { int Solve(int value) { return value + 1; } }\n",
            ".py": "def solve(value):\n    return value + 1\n",
            ".js": "function solve(value) { return value + 1; }\n",
            ".jsx": "const Answer = ({ value }) => <span>{value + 1}</span>;\n",
        }

        for extension, content in examples.items():
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as root:
                student_a = os.path.join(root, "student-a")
                student_b = os.path.join(root, "student-b")
                student_c = os.path.join(root, "student-c")
                os.mkdir(student_a)
                os.mkdir(student_b)
                os.mkdir(student_c)

                path_a = os.path.join(student_a, f"Answer{extension}")
                path_b = os.path.join(student_b, f"Solution{extension}")
                path_c = os.path.join(student_c, f"Answer{extension}")
                for path in (path_a, path_b, path_c):
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(content)

                _stats, comparisons = compare_files(
                    [
                        FoundFile(path=path_a, folder="student-a", comparison_group=extension),
                        FoundFile(path=path_b, folder="student-b", comparison_group=extension),
                        FoundFile(path=path_c, folder="student-c", comparison_group=extension),
                    ],
                    only_matching_filenames=True,
                )

                self.assertEqual(len(comparisons), 1)
                self.assertEqual(
                    {comparisons[0].file1.path, comparisons[0].file2.path},
                    {path_a, path_c},
                )

    def test_empty_normalized_files_are_not_returned_for_storage_or_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            student_a = os.path.join(root, "student-a")
            student_b = os.path.join(root, "student-b")
            student_c = os.path.join(root, "student-c")
            os.mkdir(student_a)
            os.mkdir(student_b)
            os.mkdir(student_c)

            empty_path = os.path.join(student_a, "answer.py")
            comment_only_path = os.path.join(student_b, "answer.py")
            real_path = os.path.join(student_c, "answer.py")

            with open(empty_path, "w", encoding="utf-8") as fh:
                fh.write("")
            with open(comment_only_path, "w", encoding="utf-8") as fh:
                fh.write("# no submission\n")
            with open(real_path, "w", encoding="utf-8") as fh:
                fh.write("def solve(value):\n    return value + 1\n")

            stats, comparisons = compare_files(
                [
                    FoundFile(path=empty_path, folder="student-a", comparison_group="answer.py"),
                    FoundFile(path=comment_only_path, folder="student-b", comparison_group="answer.py"),
                    FoundFile(path=real_path, folder="student-c", comparison_group="answer.py"),
                ]
            )

            self.assertEqual([stat.path for stat in stats], [real_path])
            self.assertEqual(comparisons, [])


class PythonNormalizerTests(unittest.TestCase):
    def test_python_normalizer_uses_tokens_for_comments_strings_and_identifiers(self) -> None:
        normalizer = PythonNormalizer()

        self.assertEqual(
            normalizer.normalize('value = "# not a comment"  # real comment\n'),
            "VAR=STR",
        )
        self.assertEqual(
            normalizer.normalize("def solve(value):\n    return value + 1\n"),
            normalizer.normalize("def solve(other):\n    return other + 2\n"),
        )


class CSharpNormalizerTests(unittest.TestCase):
    def test_csharp_normalizer_ignores_comments_without_cutting_strings(self) -> None:
        normalizer = CSharpNormalizer()

        self.assertEqual(
            normalizer.normalize('var url = "http://example"; // real comment\n'),
            "varVAR=STR;",
        )
        self.assertEqual(
            normalizer.normalize(
                "int Add(int value) { /* block comment */ return value + 1; }\n"
            ),
            normalizer.normalize(
                "int Sum(int number) { /* changed */ return number + 2; }\n"
            ),
        )


class JavaScriptNormalizerTests(unittest.TestCase):
    def test_javascript_normalizer_ignores_comments_without_cutting_strings(self) -> None:
        normalizer = JavaScriptNormalizer()

        self.assertEqual(
            normalizer.normalize('const url = "http://example"; // real comment\n'),
            "constVAR=STR;",
        )
        self.assertEqual(
            normalizer.normalize(
                "function add(value) { /* block comment */ return value + 1; }\n"
            ),
            normalizer.normalize(
                "function sum(amount) { /* changed */ return amount + 2; }\n"
            ),
        )

    def test_javascript_normalizer_handles_jsx_and_typescript_extensions(self) -> None:
        normalizer = JavaScriptNormalizer()

        self.assertEqual(
            normalizer.normalize("const View = ({ name }) => <h1>{name}</h1>;\n"),
            normalizer.normalize("const Page = ({ title }) => <h1>{title}</h1>;\n"),
        )
        self.assertEqual(
            normalizer.normalize("type Item = { count: number };\n"),
            "typeVAR={VAR:number};",
        )


class RegistryTests(unittest.TestCase):
    def test_registry_selects_language_normalizers_by_extension(self) -> None:
        self.assertIsInstance(get_normalizer("answer.py"), PythonNormalizer)
        self.assertIsInstance(get_normalizer("Program.cs"), CSharpNormalizer)
        self.assertIsInstance(get_normalizer("app.js"), JavaScriptNormalizer)
        self.assertIsInstance(get_normalizer("Component.jsx"), JavaScriptNormalizer)
        self.assertIsInstance(get_normalizer("module.mjs"), JavaScriptNormalizer)
        self.assertIsInstance(get_normalizer("component.tsx"), JavaScriptNormalizer)


if __name__ == "__main__":
    unittest.main()
