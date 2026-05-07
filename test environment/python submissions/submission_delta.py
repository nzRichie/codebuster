"""Sample Python submission with a small class-based approach."""


class GradeBook:
    def __init__(self):
        self._grades = {}

    def add_grade(self, student, score):
        self._grades.setdefault(student, []).append(score)

    def average_for(self, student):
        scores = self._grades.get(student, [])
        if not scores:
            return 0
        return sum(scores) / len(scores)

    def passing_students(self, minimum=60):
        passing = []
        for student in self._grades:
            if self.average_for(student) >= minimum:
                passing.append(student)
        return passing


def main():
    book = GradeBook()
    book.add_grade("Ava", 82)
    book.add_grade("Ava", 91)
    book.add_grade("Ben", 55)
    print(book.average_for("Ava"))
    print(book.passing_students())


if __name__ == "__main__":
    main()
