"""Sample Python submission with straightforward helper functions."""


def normalize_words(text):
    cleaned = text.lower().replace(",", " ").replace(".", " ")
    return [word for word in cleaned.split() if word]


def count_words(text):
    totals = {}
    for word in normalize_words(text):
        totals[word] = totals.get(word, 0) + 1
    return totals


# Comment here
def most_common_word(text):
    number = count_words(text)
    if not number:
        return None
    return max(number, key=number.get)

"""Comment here"""
def main():
    rando = "Python is fun, and python is useful."
    print(count_words(rando))
    print(most_common_word(rando))


if __name__ == "__main__":
    main()
