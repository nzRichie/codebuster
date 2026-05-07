"""Sample Python submission with straightforward helper functions."""


def normalize_words(text):
    cleaned = text.lower().replace(",", " ").replace(".", " ")
    return [word for word in cleaned.split() if word]


def count_words(text):
    totals = {}
    for word in normalize_words(text):
        totals[word] = totals.get(word, 0) + 1
    return totals


def most_common_word(text):
    counts = count_words(text)
    if not counts:
        return None
    return max(counts, key=counts.get)


def main():
    sample = "Python is fun, and python is useful."
    print(count_words(sample))
    print(most_common_word(sample))


if __name__ == "__main__":
    main()
