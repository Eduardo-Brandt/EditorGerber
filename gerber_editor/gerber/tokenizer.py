"""Lossless tokenizer: byte offsets are stable through Latin-1 decoding."""

from dataclasses import dataclass

from gerber_editor.gerber.errors import GerberError


@dataclass(frozen=True)
class Token:
    raw: str
    command: str
    extended: bool
    start: int
    end: int


def tokenize(data: bytes) -> list[Token]:
    text = data.decode("latin-1")
    tokens = []
    position = 0
    while position < len(text):
        start = position
        while position < len(text) and text[position].isspace():
            position += 1
        if position == len(text):
            break
        extended = text[position] == "%"
        delimiter = "%" if extended else "*"
        end = text.find(delimiter, position + 1)
        if end < 0:
            raise GerberError(f"Comando sem terminador no byte {position}.")
        body = text[position + 1 : end] if extended else text[position:end]
        if extended and not body.endswith("*"):
            raise GerberError(f"Bloco % sem * final no byte {position}.")
        tokens.append(Token(text[start : end + 1], body, extended, start, end + 1))
        position = end + 1
    return tokens
