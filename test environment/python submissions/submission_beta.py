"""Sample Python submission using a similar idea with different structure."""


PUNCTUATION = ",.;:!?"


def tokenize(sentence):
    lowered = sentence.casefold()
    for mark in PUNCTUATION:
        lowered = lowered.replace(mark, " ")
    return lowered.split()


def build_frequency_table(sentence):
    frequency = {}
    for token in tokenize(sentence):
        if token not in frequency:
            frequency[token] = 0
        frequency[token] += 1
    return frequency


def top_token(sentence):
    table = build_frequency_table(sentence)
    best_word = ""
    best_count = 0
    for word, count in table.items():
        if count > best_count:
            best_word = word
            best_count = count
    return best_word or None


if __name__ == "__main__":
    phrase = "Tests are useful! Useful tests catch bugs."
    print(build_frequency_table(phrase))
    print(top_token(phrase))
