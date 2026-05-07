"""Sample Python submission focused on list processing."""


def filter_even_numbers(values):
    evens = []
    for value in values:
        if value % 2 == 0:
            evens.append(value)
    return evens


def square_values(values):
    return [value * value for value in values]


def summarize_numbers(values):
    if not values:
        return {"count": 0, "total": 0, "average": 0}

    total = sum(values)
    return {
        "count": len(values),
        "total": total,
        "average": total / len(values),
    }


def main():
    numbers = [3, 6, 9, 12, 15, 18]
    evens = filter_even_numbers(numbers)
    print(square_values(evens))
    print(summarize_numbers(evens))


if __name__ == "__main__":
    main()
