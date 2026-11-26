"""Page number formats."""


def to_roman(number: int) -> str:
    """1 -> 'i', 4 -> 'iv', 14 -> 'xiv' (lower case, as in book front matter)."""
    if number <= 0:
        return str(number)
    values = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
              (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = []
    for value, letters in values:
        while number >= value:
            out.append(letters)
            number -= value
    return "".join(out)
